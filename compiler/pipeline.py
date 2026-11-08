import hashlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from compiler.citation import verify_citation
from compiler.coverage import Coverage, build_coverage
from compiler.extractor import extract_pdf_pages
from compiler.llm_propose import make_llm_proposer
from compiler.propose import Proposal, propose_rules
from contracts.models import Ruleset, RuleStatus, SpendRule
from shared.llm import LLMError, is_configured

logger = logging.getLogger("fineprint.compiler")

Proposer = Callable[[dict[int, str]], Proposal]


@dataclass
class CompileResult:
    ruleset: Ruleset
    rejected: list[dict[str, Any]]
    flagged: list[dict[str, Any]]
    coverage: Coverage
    proposer: str = "keyword"


def compile_pages_full(
    pages: dict[int, str],
    grant_id: str,
    grant_name: str,
    proposer: Proposer = propose_rules,
    status: RuleStatus = "proposed",
) -> CompileResult:
    """Propose rules from page text and keep only those whose citation verifies.

    Rule ids are deterministic so recompiling the same document is reproducible.
    Rules come out `proposed` (not enforced) until a person approves them.
    Defaults to the offline keyword proposer; pass an LLM proposer explicitly.
    """
    proposal = proposer(pages)
    verified_rules: list[SpendRule] = []
    rejected = list(proposal.rejected)

    for cand in proposal.candidates:
        citation = verify_citation(pages, page_number=cand.page, candidate_quote=cand.quote)
        if citation is None:
            rejected.append(
                {
                    "candidate": {
                        "page": cand.page,
                        "quote": cand.quote,
                        "rule_type": cand.rule_type,
                    },
                    "reason": f"Quote could not be verified on page {cand.page}",
                }
            )
            continue

        verified_rules.append(
            SpendRule(
                id=f"rule_{len(verified_rules) + 1:02d}_{cand.rule_type}",
                name=cand.name,
                rule_type=cand.rule_type,
                citation=citation,
                params=cand.params,
                source="grant",
                status=status,
            )
        )

    ruleset = Ruleset(grant_id=grant_id, grant_name=grant_name, rules=verified_rules)
    return CompileResult(
        ruleset=ruleset,
        rejected=rejected,
        flagged=proposal.flagged,
        coverage=build_coverage(pages, ruleset, rejected, proposal.flagged),
    )


def compile_pages(
    pages: dict[int, str],
    grant_id: str,
    grant_name: str,
    proposer: Proposer = propose_rules,
    status: RuleStatus = "proposed",
) -> tuple[Ruleset, list[dict[str, Any]]]:
    """Like compile_pages_full, returning just the ruleset and rejected candidates."""
    result = compile_pages_full(pages, grant_id, grant_name, proposer, status)
    return result.ruleset, result.rejected


def use_llm() -> bool:
    """LLM proposer when a key is set, unless FINEPRINT_PROPOSER=keyword."""
    return is_configured() and os.environ.get("FINEPRINT_PROPOSER", "auto") != "keyword"


def compile_grant_pdf(
    pdf_bytes: bytes,
    grant_name: str = "Uploaded Grant Agreement",
) -> CompileResult:
    """Compile a grant PDF into proposed SpendRules.

    `proposer` on the result says which proposer produced them. If the LLM
    call fails, falls back to the keyword proposer and says so.
    """
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(pdf_bytes)}
    grant_id = f"grant_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

    if use_llm():
        try:
            result = compile_pages_full(pages, grant_id, grant_name, make_llm_proposer())
            result.proposer = "llm"
            return result
        except LLMError as e:
            logger.warning("LLM proposer failed, using keyword proposer: %s", e)
            result = compile_pages_full(pages, grant_id, grant_name)
            result.proposer = f"keyword (LLM unavailable: {e})"
            return result

    return compile_pages_full(pages, grant_id, grant_name)
