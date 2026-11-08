import io

from pydantic import BaseModel
from pypdf import PdfReader


class UnreadablePdfError(ValueError):
    pass


class ExtractedPage(BaseModel):
    page_number: int
    raw_text: str
    char_count: int
    is_ocr: bool = False


def extract_pdf_pages(pdf_bytes: bytes) -> list[ExtractedPage]:
    """Extract page text from PDF bytes with character offsets and page numbers.

    Returns 1-indexed ExtractedPage objects.
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        raw_pages = list(reader.pages)
    except Exception as e:  # pypdf raises many error types for damaged files
        raise UnreadablePdfError("Couldn't read that PDF; it may be damaged or not a PDF") from e
    pages: list[ExtractedPage] = []

    for i, page in enumerate(raw_pages, start=1):
        text = page.extract_text() or ""
        # Normalize carriage returns while preserving indices
        normalized_text = text.replace("\r\n", "\n")
        pages.append(
            ExtractedPage(
                page_number=i,
                raw_text=normalized_text,
                char_count=len(normalized_text),
                is_ocr=False,
            )
        )

    return pages
