import hashlib
import logging
import os
from collections.abc import Callable
from typing import Any

from compiler.citation import verify_citation
from compiler.extractor import extract_pdf_pages
from compiler.llm_propose import make_llm_proposer
from compiler.propose import Proposal, propose_rules
from contracts.models import Ruleset, SpendRule
from shared.llm import LLMError, is_configured

logger = logging.getLogger("fineprint.compiler")

Proposer = Callable[[dict[int, str]], Proposal]


def compile_pages(
    pages: dict[int, str],
    grant_id: str,
    grant_name: str,
    proposer: Proposer = propose_rules,
) -> tuple[Ruleset, list[dict[str, Any]]]:
    """Propose rules from page text and keep only those whose citation verifies.

    Returns the verified Ruleset and the rejected candidates with reasons.
    Rule ids are deterministic so recompiling the same document is reproducible.
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
            )
        )

    return Ruleset(grant_id=grant_id, grant_name=grant_name, rules=verified_rules), rejected


def use_llm() -> bool:
    """LLM proposer when a key is set, unless FINEPRINT_PROPOSER=keyword."""
    return is_configured() and os.environ.get("FINEPRINT_PROPOSER", "auto") != "keyword"


def compile_grant_pdf(
    pdf_bytes: bytes,
    grant_name: str = "Uploaded Grant Agreement",
) -> tuple[Ruleset, list[dict[str, Any]], str]:
    """Compile a grant PDF into verified SpendRules.

    Returns the ruleset, rejected candidates, and which proposer produced them.
    If the LLM call fails, falls back to the keyword proposer and says so.
    """
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(pdf_bytes)}
    grant_id = f"grant_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"

    if use_llm():
        try:
            ruleset, rejected = compile_pages(pages, grant_id, grant_name, make_llm_proposer())
            return ruleset, rejected, "llm"
        except LLMError as e:
            logger.warning("LLM proposer failed, using keyword proposer: %s", e)
            ruleset, rejected = compile_pages(pages, grant_id, grant_name)
            return ruleset, rejected, f"keyword (LLM unavailable: {e})"

    ruleset, rejected = compile_pages(pages, grant_id, grant_name)
    return ruleset, rejected, "keyword"
