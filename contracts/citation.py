from typing import Self

from pydantic import Field, model_validator

from contracts.base import ContractModel


class SourceDocument(ContractModel):
    """The grant agreement a ruleset was compiled from."""

    document_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int = Field(ge=1)


class ClauseCitation(ContractModel):
    """A verbatim span of the source PDF that justifies a rule.

    `char_start`/`char_end` index into the extracted text of `page` (1-based page,
    0-based half-open char range). The citation verifier checks that
    page_text[char_start:char_end] == quote; rules that fail are rejected.
    """

    document_id: str = Field(min_length=1)
    page: int = Field(ge=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=1)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def _span_matches_quote_length(self) -> Self:
        if self.char_end - self.char_start != len(self.quote):
            raise ValueError("char_end - char_start must equal len(quote)")
        return self
