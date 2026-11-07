import hashlib
from typing import Any

from compiler.citation import verify_citation
from compiler.extractor import extract_pdf_pages
from compiler.propose import propose_rules
from contracts.models import Ruleset, SpendRule


def compile_pages(
    pages: dict[int, str],
    grant_id: str,
    grant_name: str,
) -> tuple[Ruleset, list[dict[str, Any]]]:
    """Propose rules from page text and keep only those whose citation verifies.

    Returns the verified Ruleset and the rejected candidates with reasons.
    Rule ids are deterministic so recompiling the same document is reproducible.
    """
    proposal = propose_rules(pages)
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


def compile_grant_pdf(
    pdf_bytes: bytes,
    grant_name: str = "Uploaded Grant Agreement",
) -> tuple[Ruleset, list[dict[str, Any]]]:
    """Compile a grant PDF into verified SpendRules."""
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(pdf_bytes)}
    grant_id = f"grant_{hashlib.sha256(pdf_bytes).hexdigest()[:12]}"
    return compile_pages(pages, grant_id=grant_id, grant_name=grant_name)
