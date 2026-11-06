import uuid
from typing import Any

from compiler.citation import verify_citation
from compiler.extractor import extract_pdf_pages
from contracts.models import Ruleset, SpendRule
from shared.llm import propose_rules_from_text


def compile_grant_pdf(
    pdf_bytes: bytes,
    grant_name: str = "Uploaded Grant Agreement",
) -> tuple[Ruleset, list[dict[str, Any]]]:
    """Compile a grant PDF into verified SpendRules.

    Returns:
    - verified Ruleset
    - list of rejected candidate rules with rejection reasons
    """
    extracted_pages = extract_pdf_pages(pdf_bytes)
    pages = {p.page_number: p.raw_text for p in extracted_pages}

    candidates = propose_rules_from_text(pages)
    verified_rules: list[SpendRule] = []
    rejected_candidates: list[dict[str, Any]] = []

    for cand in candidates:
        page_num = cand.get("page", 1)
        quote = cand.get("quote", "")

        citation = verify_citation(pages, page_number=page_num, candidate_quote=quote)
        if citation is None:
            rejected_candidates.append(
                {
                    "candidate": cand,
                    "reason": f"Verbatim quote '{quote}' could not be verified on page {page_num}",
                }
            )
            continue

        verified_rules.append(
            SpendRule(
                id=f"rule_{uuid.uuid4().hex[:8]}",
                name=cand.get("name", "Extracted Rule"),
                rule_type=cand.get("rule_type", "unknown"),
                citation=citation,
                params=cand.get("params", {}),
            )
        )

    grant_id = f"grant_{uuid.uuid4().hex[:8]}"
    ruleset = Ruleset(
        grant_id=grant_id,
        grant_name=grant_name,
        rules=verified_rules,
    )

    return ruleset, rejected_candidates
