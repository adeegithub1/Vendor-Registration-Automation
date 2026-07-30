"""
Document Processors package.

THE PROCESSOR REGISTRY
-------------------------
PROCESSOR_REGISTRY is the single source of truth mapping a file extension
to the processor class responsible for it. DocumentManager depends only on
this dict — it never contains any "if extension == '.pdf'" style logic
itself.

WHY THIS MATTERS FOR FUTURE OCR SUPPORT
-------------------------------------------
Adding support for scanned images later is a two-line change, made
entirely in this file, with ZERO changes required to DocumentManager:

    from modules.document_processors.ocr_processor import OCRProcessor
    PROCESSOR_REGISTRY[".png"] = OCRProcessor
    PROCESSOR_REGISTRY[".jpg"] = OCRProcessor

This is the Open/Closed Principle in action: the system is open to
extension (new formats) but closed to modification (existing code doesn't
need to change to support them).
"""

from typing import Dict, Type

from modules.document_processors.base_processor import BaseDocumentProcessor
from modules.document_processors.excel_processor import ExcelProcessor
from modules.document_processors.pdf_processor import PDFProcessor
from modules.document_processors.word_processor import WordProcessor

PROCESSOR_REGISTRY: Dict[str, Type[BaseDocumentProcessor]] = {
    ".pdf": PDFProcessor,
    ".docx": WordProcessor,
    ".xlsx": ExcelProcessor,
}
