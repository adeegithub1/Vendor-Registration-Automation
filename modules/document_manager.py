"""
Document Manager.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
DocumentManager is the orchestrator for Phase 3: it scans a folder for
supported files, dispatches each one to the correct processor (via the
PROCESSOR_REGISTRY dict, injected at construction time), and collects the
results. It contains ZERO format-specific logic — that all lives in the
processors themselves.

WHY THE REGISTRY IS INJECTED, NOT IMPORTED DIRECTLY
--------------------------------------------------------
DocumentManager takes its processor_registry as a constructor argument
(defaulting to the real PROCESSOR_REGISTRY) rather than importing it
directly and using it internally. This is "Dependency Inversion" — it
means DocumentManager can be tested with a fake/mock registry without
touching real files, and makes the dependency explicit rather than hidden
inside the class.

ERROR HANDLING
---------------
This is the ONE place in Phase 3 that catches processor exceptions. If
processing a single file raises any exception, it's logged, recorded as a
failed ProcessedDocument, and the loop moves on to the next file — the
whole batch never stops because of one bad document.
"""

import time
from pathlib import Path
from typing import Dict, List, Type

from modules.document_processors import PROCESSOR_REGISTRY
from modules.document_processors.base_processor import BaseDocumentProcessor
from modules.logger import get_logger
from modules.models import ProcessedDocument

logger = get_logger(__name__)


class DocumentManager:
    """Scans a folder and processes every supported document within it."""

    def __init__(
        self,
        company_documents_dir: Path,
        processor_registry: Dict[str, Type[BaseDocumentProcessor]] = PROCESSOR_REGISTRY,
    ):
        """
        Args:
            company_documents_dir: Folder to scan for company documents.
            processor_registry: Maps lowercase file extension (e.g. ".pdf")
                to the processor class that handles it. Defaults to the
                real registry; can be overridden for testing.
        """
        self.company_documents_dir = company_documents_dir
        self.processor_registry = processor_registry

    def scan_documents(self) -> List[Path]:
        """
        Find every file in company_documents_dir whose extension has a
        registered processor. Never hardcodes filenames — automatically
        picks up whatever files are present at run time.

        Returns:
            Sorted list of matching file paths (sorted for deterministic,
            reproducible output between runs).

        Raises:
            FileNotFoundError: If company_documents_dir does not exist.
        """
        if not self.company_documents_dir.is_dir():
            raise FileNotFoundError(f"Company documents folder not found: {self.company_documents_dir}")

        supported_extensions = set(self.processor_registry.keys())
        matched_files: List[Path] = []

        for entry in sorted(self.company_documents_dir.iterdir()):
            if not entry.is_file():
                continue
            if entry.suffix.lower() in supported_extensions:
                matched_files.append(entry)
            else:
                logger.debug(f"Skipping unsupported file: {entry.name}")

        return matched_files

    def process_documents(self) -> List[ProcessedDocument]:
        """
        Scan and process every supported document, tolerating individual
        failures.

        Returns:
            List of ProcessedDocument (a mix of status="success" and
            status="failed" entries), in the same order as scan_documents().
        """
        start_time = time.perf_counter()
        files = self.scan_documents()
        logger.info(f"Documents found: {len(files)} (in {self.company_documents_dir})")

        results: List[ProcessedDocument] = []
        processed_count = 0
        failed_count = 0
        total_characters = 0

        for file_path in files:
            processor_class = self.processor_registry[file_path.suffix.lower()]
            processor = processor_class()

            try:
                document = processor.process(file_path)
                results.append(document)
                processed_count += 1
                total_characters += document.total_characters
                logger.info(f"Processed OK: {file_path.name} ({document.total_characters} characters extracted)")
            except Exception as exc:
                failed_count += 1
                logger.error(f"Failed to process {file_path.name}: {exc}")
                results.append(
                    ProcessedDocument(
                        filename=file_path.name,
                        extension=file_path.suffix.lower(),
                        document_type=getattr(processor_class, "document_type", "UNKNOWN"),
                        file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                        num_pages=None,
                        num_sheets=None,
                        total_characters=0,
                        extracted_text="",
                        status="failed",
                        error_message=str(exc),
                    )
                )

        elapsed_seconds = time.perf_counter() - start_time

        logger.info(
            "Extraction summary | "
            f"Found: {len(files)} | Processed: {processed_count} | Failed: {failed_count} | "
            f"Characters extracted: {total_characters} | Processing time: {elapsed_seconds:.2f}s"
        )

        return results
