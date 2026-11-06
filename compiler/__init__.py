"""COMPILE path: grant PDF -> typed rule IR with verified clause citations. Owner: A."""

from compiler.citation import verify_citation
from compiler.extractor import ExtractedPage, extract_pdf_pages
from compiler.pipeline import compile_grant_pdf

__all__ = [
    "ExtractedPage",
    "compile_grant_pdf",
    "extract_pdf_pages",
    "verify_citation",
]
