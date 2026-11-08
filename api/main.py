from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from compiler.coverage import Coverage
from compiler.examples import RuleExample, examples_for
from compiler.pipeline import CompileResult, compile_grant_pdf
from compiler.policy import (
    AnswerError,
    PolicyDraft,
    Question,
    apply_answers,
    draft_policy,
    open_question_rule_ids,
)
from contracts.models import BudgetState, EnforcementResult, Expense, Ruleset, SpendRule
from enforce.engine import evaluate_expense
from fixtures.sample_data import SAMPLE_BUDGET, SAMPLE_EXPENSES, SAMPLE_PAGES, SAMPLE_RULESET
from shared.llm import LLMError, Transport, anthropic_transport, is_configured

app = FastAPI(title="Fineprint API", version="0.3.0")

DEMO_PDF = Path(__file__).resolve().parents[1] / "fixtures" / "grants" / "demo_grant.pdf"

# Swapped for a fake in tests.
LLM_TRANSPORT: Transport = anthropic_transport

# In-memory rulebook store, keyed by ruleset id (grant id or policy draft id).
# Persistence is a separate task (b/persistence).
RULESETS: dict[str, Ruleset] = {SAMPLE_RULESET.grant_id: SAMPLE_RULESET}
DRAFTS: dict[str, PolicyDraft] = {}

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
    return {"status": "ok", "service": "Fineprint API", "llm_configured": is_configured()}


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


def _compile_response(result: CompileResult) -> CompileResponse:
    RULESETS[result.ruleset.grant_id] = result.ruleset
    return CompileResponse(
        ruleset=result.ruleset,
        rejected=result.rejected,
        flagged=result.flagged,
        coverage=result.coverage,
        total_extracted=len(result.ruleset.rules) + len(result.rejected),
        verified_count=len(result.ruleset.rules),
        rejected_count=len(result.rejected),
        proposer=result.proposer,
    )


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

    return _compile_response(compile_grant_pdf(content, grant_name=file.filename))


# --- Company policy assistant -------------------------------------------------


def _store_draft(draft: PolicyDraft) -> PolicyDraft:
    DRAFTS[draft.draft_id] = draft
    RULESETS[draft.draft_id] = draft.ruleset
    return draft


@app.post("/api/policy/draft", response_model=PolicyDraft)
def policy_draft(req: PolicyDraftRequest) -> PolicyDraft:
    """Turn plain-English company rules into proposed rules plus multiple-choice questions."""
    if not is_configured() and LLM_TRANSPORT is anthropic_transport:
        raise HTTPException(status_code=503, detail="The policy assistant needs ANTHROPIC_API_KEY")
    try:
        draft = draft_policy(req.text, name=req.name, transport=LLM_TRANSPORT)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return _store_draft(draft)


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
    draft = DRAFTS.get(ruleset_id)
    return draft.questions if draft else []


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
    blocked: set[str] = open_question_rule_ids(draft) if draft else set()
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
    return updated
