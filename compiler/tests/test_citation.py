from compiler.citation import verify_citation


def test_verify_citation_exact_match() -> None:
    pages = {
        1: "Fineprint Grant Agreement. Page 1 intro.",
        2: "Section 4. Domestic travel necessary to carry out the project is an allowable cost.",
    }

    quote = "Domestic travel necessary to carry out the project is an allowable cost."
    citation = verify_citation(pages, page_number=2, candidate_quote=quote)

    assert citation is not None
    assert citation.page == 2
    assert citation.quote == quote
    assert citation.char_start == 11
    assert citation.char_end == 11 + len(quote)
    assert citation.prefix == "Section 4. "


def test_verify_citation_whitespace_normalization() -> None:
    pages = {
        1: "Costs of alcoholic beverages\n  are unallowable under this award.",
    }

    quote = "Costs of alcoholic beverages are unallowable under this award."
    citation = verify_citation(pages, page_number=1, candidate_quote=quote)

    assert citation is not None
    assert citation.page == 1
    assert "Costs of alcoholic beverages" in citation.quote


def test_verify_citation_rejects_hallucination() -> None:
    pages = {
        1: "All equipment over $500 requires inventory tagging.",
    }

    # Quote not in text
    quote = "All equipment over $5,000 requires prior sponsor approval."
    citation = verify_citation(pages, page_number=1, candidate_quote=quote)

    assert citation is None


def test_verify_citation_wrong_page() -> None:
    pages = {
        1: "Section 1.",
        2: "Section 2. Travel is allowable.",
    }

    quote = "Travel is allowable."
    # Candidate specified page 1, but text is on page 2
    citation = verify_citation(pages, page_number=1, candidate_quote=quote)
    assert citation is None
