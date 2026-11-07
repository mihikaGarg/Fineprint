from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from compiler.pipeline import compile_grant_pdf
from contracts.models import BudgetState, EnforcementResult, Expense, Ruleset
from enforce.engine import evaluate_expense
from fixtures.sample_data import SAMPLE_BUDGET, SAMPLE_EXPENSES, SAMPLE_PAGES, SAMPLE_RULESET

app = FastAPI(title="Fineprint API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class EnforceRequest(BaseModel):
    expense: Expense
    ruleset: Ruleset
    budget_state: BudgetState


class CompileResponse(BaseModel):
    ruleset: Ruleset
    rejected: list[dict[str, Any]]
    total_extracted: int
    verified_count: int
    rejected_count: int
    proposer: str


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Fineprint API"}


@app.get("/api/fixtures")
def get_fixtures() -> dict[str, Any]:
    return {
        "ruleset": SAMPLE_RULESET.model_dump(mode="json"),
        "budget": SAMPLE_BUDGET.model_dump(mode="json"),
        "expenses": SAMPLE_EXPENSES,
        "pages": SAMPLE_PAGES,
    }


@app.post("/api/enforce", response_model=EnforcementResult)
def enforce_endpoint(req: EnforceRequest) -> EnforcementResult:
    return evaluate_expense(
        expense=req.expense,
        ruleset=req.ruleset,
        budget_state=req.budget_state,
    )


@app.post("/api/compile", response_model=CompileResponse)
async def compile_endpoint(file: UploadFile = File(...)) -> CompileResponse:  # noqa: B008
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    ruleset, rejected, proposer = compile_grant_pdf(content, grant_name=file.filename)

    return CompileResponse(
        ruleset=ruleset,
        rejected=rejected,
        total_extracted=len(ruleset.rules) + len(rejected),
        verified_count=len(ruleset.rules),
        rejected_count=len(rejected),
        proposer=proposer,
    )
