"""
PDF Processor.

LIBRARY USED: PyMuPDF (imported as `fitz`)
--------------------------------------------
PyMuPDF is a fast, well-maintained library for reading PDF files. We use
it here purely for text extraction: `page.get_text()` returns the plain
text content of a page in reading order for PDFs that contain actual text
(as opposed to scanned image-only PDFs, which have no embedded text layer
and will correctly extract as empty — OCR support for those is a planned
future phase, not this one).
"""

from pathlib import Path

import fitz  # PyMuPDF

from modules.document_processors.base_processor import BaseDocumentProcessor, RawExtraction


class PDFProcessor(BaseDocumentProcessor):
    """Extracts text and page count from .pdf files."""

    document_type = "PDF"

    def _extract(self, file_path: Path) -> RawExtraction:
        try:
            pdf_document = fitz.open(str(file_path))
        except Exception as exc:
            raise RuntimeError(f"Failed to open PDF file (it may be corrupted or password-protected): {exc}") from exc

        try:
            num_pages = pdf_document.page_count
            page_texts = [page.get_text() for page in pdf_document]
        finally:
            # Always close the file handle, even if extraction fails partway through.
            pdf_document.close()

        full_text = "\n\n".join(page_texts)
        return RawExtraction(text=full_text, num_pages=num_pages, num_sheets=None)
