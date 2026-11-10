import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, StrictInt

from compiler.budget import BudgetItem
from compiler.coverage import Coverage
from compiler.examples import RuleExample, examples_for
from compiler.extractor import UnreadablePdfError, extract_pdf_pages
from compiler.pipeline import CompileResult, compile_grant_pdf, use_llm
from compiler.policy import (
    AnswerError,
    Option,
    PolicyDraft,
    Question,
    apply_answers,
    draft_from_items,
    draft_policy,
    draft_policy_pages,
)
from compiler.policy_chat import PolicySession, ReplyError, reply, start_session
from compiler.policy_offline import read_policy
from contracts.models import (
    KNOWN_CATEGORIES,
    BudgetLine,
    BudgetState,
    EnforcementResult,
    Expense,
    Ruleset,
    SpendRule,
)
from enforce.engine import evaluate_expense
from enforce.rules import budget_line_for
from fixtures.sample_data import SAMPLE_BUDGET, SAMPLE_EXPENSES, SAMPLE_PAGES, SAMPLE_RULESET
from shared.llm import LLMError, Transport, anthropic_transport, is_configured

app = FastAPI(title="Fineprint API", version="0.3.0")

DEMO_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "grants" / "demo_grant.pdf"
PLAYGROUND_HTML = Path(__file__).resolve().parent / "static" / "playground.html"
CHAT_HTML = Path(__file__).resolve().parent / "static" / "chat.html"
APP_HTML = Path(__file__).resolve().parent / "static" / "app.html"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SAMPLE_POLICIES = {"northwind": FIXTURES / "policies" / "northwind_te_policy.pdf"}
SAMPLE_BATCH = FIXTURES / "expenses" / "enterprise_batch.json"
# Budget lines from the demo grant's approved budget.
DEMO_BUDGET = BudgetState.model_validate(
    {
        "lines": {
            "travel_domestic": {
                "category": "travel_domestic",
                "allocated_cents": 800000,
                "spent_cents": 320000,
            },
            "equipment": {"category": "equipment", "allocated_cents": 2000000, "spent_cents": 0},
        }
    }
)

# Swapped for a fake in tests.
LLM_TRANSPORT: Transport = anthropic_transport

# In-memory rulebook store, keyed by ruleset id (grant id or policy draft id).
# Persistence is a separate task (b/persistence).
RULESETS: dict[str, Ruleset] = {SAMPLE_RULESET.grant_id: SAMPLE_RULESET}
DRAFTS: dict[str, PolicyDraft] = {}
SESSIONS: dict[str, PolicySession] = {}
# Earlier states of each chat, newest last, so "Undo last answer" can step back.
UNDO: dict[str, list[PolicySession]] = {}
GRANTS: dict[str, "CompileResponse"] = {}  # compile details (coverage etc.) by grant id
SAMPLE_IDS = {SAMPLE_RULESET.grant_id}  # bundled fixture, hidden from the app
# Live budget per grant (read from the agreement or entered), spent on ALLOWED.
BUDGETS: dict[str, BudgetState] = {}
# Where each budget line came from, per grant: the cited budget item, or None if entered by hand.
BUDGET_SOURCES: dict[str, dict[str, BudgetItem | None]] = {}
EXPENSE_LOG: list["LoggedExpense"] = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class EnforceRequest(BaseModel):
    expense: Expense
    budget_state: BudgetState
    # Either send rulesets inline, or name stored ones. Several are checked together.
    ruleset: Ruleset | None = None
    ruleset_ids: list[str] = Field(default_factory=list[str])


class CompileResponse(BaseModel):
    ruleset: Ruleset
    rejected: list[dict[str, Any]]
    flagged: list[dict[str, Any]]
    coverage: Coverage
    total_extracted: int
    verified_count: int
    rejected_count: int
    proposer: str
    budget: list[BudgetItem] = Field(default_factory=list[BudgetItem])


class PolicyDraftRequest(BaseModel):
    text: str
    name: str = "Company expense policy"


class AnswersRequest(BaseModel):
    answers: dict[str, str]


class ApproveRequest(BaseModel):
    rule_ids: list[str] = Field(default_factory=list[str])  # empty = all eligible


class RuleCard(BaseModel):
    rule: SpendRule
    examples: list[RuleExample]
    open_questions: list[Question]
    can_approve: bool


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "Fineprint API",
        "llm_configured": is_configured(),
        "llm_enabled": use_llm(),
    }


@app.get("/api/categories")
def categories() -> list[str]:
    return list(KNOWN_CATEGORIES)


@app.get("/playground", response_class=HTMLResponse)
def playground() -> str:
    """Bare-bones test page for the policy assistant and enforcement."""
    return PLAYGROUND_HTML.read_text(encoding="utf-8")


@app.get("/api/fixtures")
def get_fixtures() -> dict[str, Any]:
    return {
        "ruleset": SAMPLE_RULESET.model_dump(mode="json"),
        "budget": SAMPLE_BUDGET.model_dump(mode="json"),
        "expenses": SAMPLE_EXPENSES,
        "pages": SAMPLE_PAGES,
    }


def _get_ruleset(ruleset_id: str) -> Ruleset:
    rs = RULESETS.get(ruleset_id)
    if rs is None:
        raise HTTPException(status_code=404, detail=f"No ruleset '{ruleset_id}'")
    return rs


@app.post("/api/enforce", response_model=EnforcementResult)
def enforce_endpoint(req: EnforceRequest) -> EnforcementResult:
    rulesets = [_get_ruleset(i) for i in req.ruleset_ids]
    if req.ruleset is not None:
        rulesets.append(req.ruleset)
    if not rulesets:
        raise HTTPException(status_code=400, detail="Send a ruleset or ruleset_ids")
    return evaluate_expense(expense=req.expense, ruleset=rulesets, budget_state=req.budget_state)


def _store_budget(grant_id: str, items: list[BudgetItem]) -> None:
    """Budget lines from the agreement; keeps spend already recorded on a re-upload."""
    old = BUDGETS.get(grant_id, BudgetState())
    lines = dict(old.lines)
    sources = BUDGET_SOURCES.setdefault(grant_id, {})
    for item in items:
        spent = old.lines[item.line].spent_cents if item.line in old.lines else 0
        lines[item.line] = BudgetLine(
            category=item.line, allocated_cents=item.allocated_cents, spent_cents=spent
        )
        sources[item.line] = item
    BUDGETS[grant_id] = BudgetState(lines=lines)


def _compile_response(result: CompileResult) -> CompileResponse:
    RULESETS[result.ruleset.grant_id] = result.ruleset
    _store_budget(result.ruleset.grant_id, result.budget)
    response = CompileResponse(
        ruleset=result.ruleset,
        rejected=result.rejected,
        flagged=result.flagged,
        coverage=result.coverage,
        total_extracted=len(result.ruleset.rules) + len(result.rejected),
        verified_count=len(result.ruleset.rules),
        rejected_count=len(result.rejected),
        proposer=result.proposer,
        budget=result.budget,
    )
    GRANTS[result.ruleset.grant_id] = response
    return response


@app.post("/api/compile/demo", response_model=CompileResponse)
def compile_demo() -> CompileResponse:
    """Compile the bundled fictional demo grant (fixtures/grants/demo_grant.pdf)."""
    return _compile_response(
        compile_grant_pdf(DEMO_PDF.read_bytes(), "Community Climate Research Award (demo)")
    )


@app.post("/api/compile", response_model=CompileResponse)
async def compile_endpoint(file: UploadFile = File(...)) -> CompileResponse:  # noqa: B008
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        return _compile_response(compile_grant_pdf(content, grant_name=file.filename))
    except UnreadablePdfError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Company policy assistant -------------------------------------------------


def _store_draft(draft: PolicyDraft) -> PolicyDraft:
    DRAFTS[draft.draft_id] = draft
    RULESETS[draft.draft_id] = draft.ruleset
    return draft


@app.post("/api/policy/draft", response_model=PolicyDraft)
def policy_draft(req: PolicyDraftRequest) -> PolicyDraft:
    """Turn plain-English company rules into proposed rules plus multiple-choice questions.

    Uses Claude when a key is set and enabled (or a test transport is installed);
    otherwise, or if Claude fails, the offline reader.
    """
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Policy text is empty")
    if LLM_TRANSPORT is not anthropic_transport or use_llm():
        try:
            return _store_draft(draft_policy(text, name=req.name, transport=LLM_TRANSPORT))
        except LLMError as e:
            fallback = f"offline (Claude unavailable: {e})"
            pages = {1: text}
            return _store_draft(draft_from_items(pages, req.name, read_policy(pages), fallback))
    pages = {1: text}
    return _store_draft(draft_from_items(pages, req.name, read_policy(pages), "offline"))


@app.get("/api/policy/{draft_id}", response_model=PolicyDraft)
def policy_get(draft_id: str) -> PolicyDraft:
    draft = DRAFTS.get(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail=f"No policy draft '{draft_id}'")
    return draft


@app.post("/api/policy/{draft_id}/answers", response_model=PolicyDraft)
def policy_answers(draft_id: str, req: AnswersRequest) -> PolicyDraft:
    """Apply one-tap answers to open questions."""
    draft = policy_get(draft_id)
    try:
        return _store_draft(apply_answers(draft, req.answers))
    except AnswerError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Review: rule cards and approval -------------------------------------------


def _open_questions(ruleset_id: str) -> list[Question]:
    """Unanswered questions for a ruleset, from a policy draft or a setup chat."""
    draft = DRAFTS.get(ruleset_id)
    questions = list(draft.questions) if draft else []
    session = SESSIONS.get(ruleset_id)
    if session:
        for gap in session.gaps:
            if gap.resolved or gap.kind in ("final", "conflict"):
                continue
            for rule_id in [gap.rule_id] if gap.rule_id else gap.rule_ids:
                questions.append(
                    Question(
                        id=gap.id,
                        rule_id=rule_id,
                        field=gap.field or gap.kind,
                        question=gap.prompt,
                        options=[Option(label=o.label, value=o.value) for o in gap.options],
                    )
                )
    return questions


@app.get("/api/rulesets/{ruleset_id}", response_model=Ruleset)
def ruleset_get(ruleset_id: str) -> Ruleset:
    return _get_ruleset(ruleset_id)


@app.get("/api/rulesets/{ruleset_id}/cards", response_model=list[RuleCard])
def ruleset_cards(ruleset_id: str) -> list[RuleCard]:
    """Each rule with auto-generated example verdicts and any open questions."""
    rs = _get_ruleset(ruleset_id)
    questions = _open_questions(ruleset_id)
    cards: list[RuleCard] = []
    for rule in rs.rules:
        open_qs = [q for q in questions if q.rule_id == rule.id]
        cards.append(
            RuleCard(
                rule=rule,
                examples=[] if open_qs else examples_for(rule),
                open_questions=open_qs,
                can_approve=not open_qs,
            )
        )
    return cards


@app.post("/api/rulesets/{ruleset_id}/approve", response_model=Ruleset)
def ruleset_approve(ruleset_id: str, req: ApproveRequest) -> Ruleset:
    """Approve rules so they're enforced. Rules with open questions are skipped."""
    rs = _get_ruleset(ruleset_id)
    draft = DRAFTS.get(ruleset_id)
    blocked = {q.rule_id for q in _open_questions(ruleset_id)}
    wanted = set(req.rule_ids) or {r.id for r in rs.rules}
    unknown = wanted - {r.id for r in rs.rules}
    if unknown:
        raise HTTPException(status_code=404, detail=f"Unknown rules: {sorted(unknown)}")
    rules = [
        r.model_copy(update={"status": "approved"}) if r.id in wanted and r.id not in blocked else r
        for r in rs.rules
    ]
    updated = rs.model_copy(update={"rules": rules})
    RULESETS[ruleset_id] = updated
    if draft:
        DRAFTS[ruleset_id] = draft.model_copy(update={"ruleset": updated})
    session = SESSIONS.get(ruleset_id)
    if session:  # keep the chat's copy in sync so later answers don't undo approvals
        SESSIONS[ruleset_id] = session.model_copy(update={"ruleset": updated})
        UNDO.pop(ruleset_id, None)  # approving is a commit point; undo can't revert it
    return updated


# --- Policy setup chat ----------------------------------------------------------


@app.get("/chat", response_class=HTMLResponse)
def chat_page() -> str:
    """Chat-style test page: upload a policy, close the gaps, test expenses."""
    return CHAT_HTML.read_text(encoding="utf-8")


class ReplyRequest(BaseModel):
    gap_id: str | None = None
    value: str | None = None
    text: str | None = None


def _pages_from_upload(filename: str, content: bytes) -> dict[int, str]:
    if filename.lower().endswith(".pdf"):
        try:
            pages = {p.page_number: p.raw_text for p in extract_pdf_pages(content)}
        except UnreadablePdfError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    elif filename.lower().endswith((".txt", ".md")):
        pages = {1: content.decode("utf-8", errors="replace")}
    else:
        raise HTTPException(status_code=400, detail="Upload a PDF, .txt or .md file")
    pages = {n: t for n, t in pages.items() if t.strip()}
    if not pages:
        raise HTTPException(status_code=400, detail="No readable text in that file")
    return pages


def _draft(pages: dict[int, str], name: str) -> PolicyDraft:
    if LLM_TRANSPORT is not anthropic_transport or use_llm():
        try:
            return draft_policy_pages(pages, name, transport=LLM_TRANSPORT)
        except LLMError as e:
            return draft_from_items(
                pages, name, read_policy(pages), f"offline (Claude unavailable: {e})"
            )
    return draft_from_items(pages, name, read_policy(pages), "offline")


@app.post("/api/chat/start", response_model=PolicySession)
async def chat_start(
    file: UploadFile | None = File(None),  # noqa: B008
    sample: str | None = Form(None),
    text: str | None = Form(None),
    name: str = Form("Company expense policy"),
    link_demo_grant: bool = Form(False),
    grant_ids: str = Form(""),
) -> PolicySession:
    """Start a setup chat from an uploaded policy, a bundled sample, or typed rules."""
    if file is not None and file.filename:
        pages = _pages_from_upload(file.filename, await file.read())
        source = file.filename
    elif sample in SAMPLE_POLICIES:
        path = SAMPLE_POLICIES[sample]
        pages = _pages_from_upload(path.name, path.read_bytes())
        source = path.name
    elif text and text.strip():
        pages, source = {1: text.strip()}, "your rules"
    else:
        raise HTTPException(status_code=400, detail="Upload a policy, pick a sample, or type rules")

    grants: list[Ruleset] = [_get_ruleset(g) for g in grant_ids.split(",") if g.strip()]
    if link_demo_grant and not grants:
        compiled = _compile_response(
            compile_grant_pdf(DEMO_PDF.read_bytes(), "Community Climate Research Award (demo)")
        )
        grants.append(ruleset_approve(compiled.ruleset.grant_id, ApproveRequest()))

    session = start_session(_draft(pages, name), source, grants)
    UNDO.pop(session.session_id, None)
    SESSIONS[session.session_id] = session
    RULESETS[session.session_id] = session.ruleset
    return session


def _get_session(session_id: str) -> PolicySession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No chat session '{session_id}'")
    return session


@app.get("/api/chat/{session_id}", response_model=PolicySession)
def chat_get(session_id: str) -> PolicySession:
    return _get_session(session_id)


@app.post("/api/chat/{session_id}/reply", response_model=PolicySession)
def chat_reply(session_id: str, req: ReplyRequest) -> PolicySession:
    before = _get_session(session_id)
    try:
        session = reply(before, req.gap_id, req.value, req.text)
    except ReplyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    UNDO.setdefault(session_id, []).append(before)
    SESSIONS[session_id] = session
    RULESETS[session_id] = session.ruleset
    return session


@app.post("/api/chat/{session_id}/undo", response_model=PolicySession)
def chat_undo(session_id: str) -> PolicySession:
    """Step back one answer (including any rule it created or changed)."""
    _get_session(session_id)
    history = UNDO.get(session_id) or []
    if not history:
        raise HTTPException(status_code=400, detail="Nothing to undo")
    session = history.pop()
    SESSIONS[session_id] = session
    RULESETS[session_id] = session.ruleset
    return session


class BatchRequest(BaseModel):
    ruleset_ids: list[str]
    expenses: list[Expense] | None = None  # None = bundled enterprise sample batch
    budget_state: BudgetState | None = None


class BatchItem(BaseModel):
    expense: Expense
    result: EnforcementResult


@app.get("/api/samples/expenses", response_model=list[Expense])
def sample_expenses() -> list[Expense]:
    data = json.loads(SAMPLE_BATCH.read_text(encoding="utf-8"))
    return [Expense.model_validate(e) for e in data["expenses"]]


@app.post("/api/batch", response_model=list[BatchItem])
def batch(req: BatchRequest) -> list[BatchItem]:
    """Check many expenses at once, each against all the given rulebooks."""
    rulesets = [_get_ruleset(i) for i in req.ruleset_ids]
    if not rulesets:
        raise HTTPException(status_code=400, detail="Send at least one ruleset id")
    expenses = req.expenses if req.expenses is not None else sample_expenses()
    budget = req.budget_state or DEMO_BUDGET
    return [
        BatchItem(expense=e, result=evaluate_expense(e, rulesets, budget, BUDGETS))
        for e in expenses
    ]


# --- Full app: state, expense log, live budget ----------------------------------


@app.get("/app", response_class=HTMLResponse)
def app_page() -> str:
    """The full Fineprint app: overview, grants, policy chat, rulebook, expenses."""
    return APP_HTML.read_text(encoding="utf-8")


class RulesetSummary(BaseModel):
    id: str
    name: str
    kind: str  # "grant" or "policy"
    rules: int
    approved: int
    open_items: int


class LoggedExpense(BaseModel):
    expense: Expense
    result: EnforcementResult
    ruleset_ids: list[str]
    recorded_spend: bool
    spent_on: str | None = None


class BudgetLineView(BaseModel):
    line: str
    label: str
    allocated_cents: int
    spent_cents: int
    remaining_cents: int
    source: str  # "p. 5: “Domestic travel: $8,000”" or "entered by you"


class GrantBudget(BaseModel):
    grant_id: str
    name: str
    lines: list[BudgetLineView]
    # Budget lines the grant's rules refer to but the agreement didn't give an amount for.
    missing: list[str]


class AppState(BaseModel):
    rulesets: list[RulesetSummary]
    budgets: list[GrantBudget]
    expenses_checked: int
    verdicts: dict[str, int]
    llm_enabled: bool


def _summaries() -> list[RulesetSummary]:
    out: list[RulesetSummary] = []
    for rid, rs in RULESETS.items():
        if rid in SAMPLE_IDS:
            continue
        session = SESSIONS.get(rid)
        open_items = (
            sum(1 for g in session.gaps if not g.resolved and g.kind != "final") if session else 0
        )
        out.append(
            RulesetSummary(
                id=rid,
                name=rs.grant_name,
                kind="policy" if rid in SESSIONS or rid in DRAFTS else "grant",
                rules=len(rs.rules),
                approved=sum(r.status == "approved" for r in rs.rules),
                open_items=open_items,
            )
        )
    return out


@app.get("/api/state", response_model=AppState)
def app_state() -> AppState:
    verdicts = {"ALLOWED": 0, "NEEDS_REVIEW": 0, "BLOCKED": 0}
    for item in EXPENSE_LOG:
        verdicts[item.result.verdict.value] += 1
    return AppState(
        rulesets=_summaries(),
        budgets=[_grant_budget(s.id) for s in _summaries() if s.kind == "grant"],
        expenses_checked=len(EXPENSE_LOG),
        verdicts=verdicts,
        llm_enabled=use_llm(),
    )


LINE_NAMES = {"travel_domestic": "Domestic travel", "travel_foreign": "Foreign travel"}


def _grant_budget(grant_id: str) -> GrantBudget:
    rs = _get_ruleset(grant_id)
    budget = BUDGETS.get(grant_id, BudgetState())
    sources = BUDGET_SOURCES.get(grant_id, {})
    views: list[BudgetLineView] = []
    for key, line in budget.lines.items():
        item = sources.get(key)
        views.append(
            BudgetLineView(
                line=key,
                label=item.label
                if item
                else LINE_NAMES.get(key, key.replace("_", " ").capitalize()),
                allocated_cents=line.allocated_cents,
                spent_cents=line.spent_cents,
                remaining_cents=max(0, line.allocated_cents - line.spent_cents),
                source=f"p. {item.citation.page}: “{item.citation.quote}”"
                if item
                else "entered by you",
            )
        )
    needed = {
        str(r.params["budget_line"])
        for r in rs.rules
        if r.rule_type == "budget_limit" and r.params.get("budget_line")
    }
    return GrantBudget(
        grant_id=grant_id,
        name=rs.grant_name,
        lines=views,
        missing=sorted(needed - set(budget.lines)),
    )


@app.get("/api/grants/{grant_id}/budget", response_model=GrantBudget)
def grant_budget(grant_id: str) -> GrantBudget:
    return _grant_budget(grant_id)


class BudgetLineRequest(BaseModel):
    line: str
    allocated_cents: StrictInt = Field(gt=0)


@app.post("/api/grants/{grant_id}/budget", response_model=GrantBudget)
def grant_budget_set(grant_id: str, req: BudgetLineRequest) -> GrantBudget:
    """Enter (or correct) one budget line by hand, e.g. when the agreement doesn't list it."""
    _get_ruleset(grant_id)
    budget = BUDGETS.setdefault(grant_id, BudgetState())
    spent = budget.lines[req.line].spent_cents if req.line in budget.lines else 0
    budget.lines[req.line] = BudgetLine(
        category=req.line, allocated_cents=req.allocated_cents, spent_cents=spent
    )
    BUDGET_SOURCES.setdefault(grant_id, {})[req.line] = None
    return _grant_budget(grant_id)


@app.get("/api/grants/{grant_id}", response_model=CompileResponse)
def grant_details(grant_id: str) -> CompileResponse:
    info = GRANTS.get(grant_id)
    if info is None:
        raise HTTPException(status_code=404, detail=f"No grant '{grant_id}'")
    return info.model_copy(update={"ruleset": _get_ruleset(grant_id)})


class CheckRequest(BaseModel):
    expense: Expense
    ruleset_ids: list[str] | None = None  # None = every rulebook with approved rules
    record: bool = True  # add to the log, and spend the budget if ALLOWED


def _check(expense: Expense, ruleset_ids: list[str] | None, record: bool) -> LoggedExpense:
    ids = ruleset_ids
    if ids is None:
        ids = [s.id for s in _summaries() if s.approved]
    if not ids:
        raise HTTPException(status_code=400, detail="No approved rules yet")
    grant_ids = [i for i in ids if i not in SESSIONS and i not in DRAFTS]
    result = evaluate_expense(
        expense,
        [_get_ruleset(i) for i in ids],
        BudgetState(),
        {g: BUDGETS.get(g, BudgetState()) for g in grant_ids},
    )
    spent_on: str | None = None
    # Allowed spend comes off the budget of the one grant it was checked against.
    if record and len(grant_ids) == 1 and result.verdict.value == "ALLOWED":
        budget = BUDGETS.get(grant_ids[0], BudgetState())
        line_key = budget_line_for(expense.category)
        line = budget.lines.get(line_key)
        if line is not None:
            budget.lines[line_key] = line.model_copy(
                update={"spent_cents": line.spent_cents + expense.amount_cents}
            )
            spent_on = f"{_get_ruleset(grant_ids[0]).grant_name}: {line_key}"
    item = LoggedExpense(
        expense=expense,
        result=result,
        ruleset_ids=ids,
        recorded_spend=spent_on is not None,
        spent_on=spent_on,
    )
    if record:
        EXPENSE_LOG.insert(0, item)
    return item


@app.post("/api/expenses/check", response_model=LoggedExpense)
def expenses_check(req: CheckRequest) -> LoggedExpense:
    return _check(req.expense, req.ruleset_ids, req.record)


class SampleBatchRequest(BaseModel):
    ruleset_ids: list[str] | None = None


@app.post("/api/expenses/sample-batch", response_model=list[LoggedExpense])
def expenses_sample_batch(req: SampleBatchRequest) -> list[LoggedExpense]:
    """Run the bundled enterprise expenses through the live rulebook and budget."""
    return [_check(e, req.ruleset_ids, True) for e in sample_expenses()]


@app.get("/api/expenses", response_model=list[LoggedExpense])
def expenses_log() -> list[LoggedExpense]:
    return EXPENSE_LOG


@app.post("/api/reset")
def reset() -> dict[str, str]:
    """Clear all grants, policies, expenses and budget spend (fresh demo)."""
    for rid in [r for r in RULESETS if r not in SAMPLE_IDS]:
        del RULESETS[rid]
    DRAFTS.clear()
    SESSIONS.clear()
    UNDO.clear()
    GRANTS.clear()
    EXPENSE_LOG.clear()
    BUDGETS.clear()
    BUDGET_SOURCES.clear()
    return {"status": "reset"}
