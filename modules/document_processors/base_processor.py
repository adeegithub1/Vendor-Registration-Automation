"""
Base Document Processor.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Defines the contract every document processor must follow, and implements
everything that is IDENTICAL across all formats (measuring file size,
cleaning extracted text, assembling the final ProcessedDocument). This is
the "Template Method" design pattern: the base class controls the overall
algorithm (process()), and delegates only the format-specific step
(_extract()) to subclasses.

WHY THIS MATTERS FOR FUTURE OCR SUPPORT
-------------------------------------------
Adding an OCR processor for scanned images later means:
    class OCRProcessor(BaseDocumentProcessor):
        document_type = "IMAGE"
        def _extract(self, file_path):
            ... OCR-specific logic ...
            return RawExtraction(text=..., num_pages=1)

Nothing about file-size measurement, text cleaning, or result assembly
needs to be touched or duplicated — that's the whole point of putting
the common logic in one place.

ERROR HANDLING
---------------
process() does NOT swallow exceptions. If a document is corrupted or
unreadable, _extract() should raise an exception, and process() lets it
propagate. This is intentional: it's DocumentManager's job (not this
class's) to decide what happens when one document fails — e.g. logging it
and continuing to the next file. Keeping that decision in one place avoids
inconsistent error handling scattered across every processor.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from modules.models import ProcessedDocument
from modules.text_cleaner import clean_text


@dataclass
class RawExtraction:
    """
    What a subclass's _extract() method returns: the raw (uncleaned) text
    plus whatever format-specific metadata is available.
    """

    text: str
    num_pages: Optional[int] = None
    num_sheets: Optional[int] = None


class BaseDocumentProcessor(ABC):
    """
    Abstract base for all document processors.

    Subclasses must set the `document_type` class attribute and implement
    `_extract()`. Everything else (process()) is shared and should not be
    overridden.
    """

    #: Overridden by each subclass, e.g. "PDF", "WORD", "EXCEL".
    document_type: str = "UNKNOWN"

    def process(self, file_path: Path) -> ProcessedDocument:
        """
        Process a single document end-to-end: measure it, extract its
        text, clean that text, and return a structured result.

        Args:
            file_path: Path to the document on disk.

        Returns:
            A fully populated ProcessedDocument with status="success".

        Raises:
            FileNotFoundError: If file_path does not exist.
            Exception: Any exception raised by the subclass's _extract()
                (e.g. a corrupted file) propagates up unchanged, so the
                caller (DocumentManager) can decide how to handle it.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size_bytes = file_path.stat().st_size

        extraction = self._extract(file_path)
        cleaned_text = clean_text(extraction.text)

        return ProcessedDocument(
            filename=file_path.name,
            extension=file_path.suffix.lower(),
            document_type=self.document_type,
            file_size_bytes=file_size_bytes,
            num_pages=extraction.num_pages,
            num_sheets=extraction.num_sheets,
            total_characters=len(cleaned_text),
            extracted_text=cleaned_text,
            status="success",
            error_message=None,
        )

    @abstractmethod
    def _extract(self, file_path: Path) -> RawExtraction:
        """
        Format-specific extraction logic. Must be implemented by every
        subclass. Should raise an exception (any type) if the file cannot
        be read or parsed — do not catch errors here; let them propagate.

        Args:
            file_path: Path to the document on disk (already confirmed
                to exist by process()).

        Returns:
            A RawExtraction with the raw (uncleaned) text and any
            available page/sheet counts.
        """
        raise NotImplementedError
