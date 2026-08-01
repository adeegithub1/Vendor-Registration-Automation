"""
Knowledge Exporter.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Takes the list of ProcessedDocument results from DocumentManager and:
  1. Saves EACH document to its own JSON file under temp/documents/
     (never one giant combined file, per the project requirements).
  2. Builds and saves temp/knowledge_index.json, a lightweight manifest
     listing every document and where its full JSON file lives.

FILENAME GENERATION ("SLUGIFYING")
--------------------------------------
Source filenames like "Company Profile.pdf" or "GST Certificate (Final).pdf"
aren't safe/clean as JSON filenames. _slugify() converts a filename to a
lowercase, underscore-separated slug (e.g. "company_profile",
"gst_certificate_final"). If two different source files would produce the
same slug (e.g. "GST.pdf" and "gst.docx" both slugify to "gst"), a numeric
suffix is appended (gst_2, gst_3, ...) so no document ever silently
overwrites another's output file.
"""

import json
import re
from pathlib import Path
from typing import List, Set

from modules.logger import get_logger
from modules.models import KnowledgeIndexEntry, ProcessedDocument

logger = get_logger(__name__)

_SLUG_INVALID_CHARS_PATTERN = re.compile(r"[^a-z0-9]+")


class KnowledgeExporter:
    """Exports ProcessedDocument results to individual JSON files plus a knowledge index."""

    def __init__(self, documents_dir: Path, index_path: Path, project_root: Path):
        """
        Args:
            documents_dir: Folder where individual document JSON files are written
                (e.g. temp/documents/).
            index_path: Full path to the knowledge_index.json manifest file.
            project_root: Project root, used to store index paths as clean,
                portable relative paths (e.g. "temp/documents/gst.json")
                rather than absolute machine-specific paths.
        """
        self.documents_dir = documents_dir
        self.index_path = index_path
        self.project_root = project_root

    @staticmethod
    def _slugify(name_without_extension: str) -> str:
        """Convert a filename stem into a lowercase, underscore-separated, filesystem-safe slug."""
        slug = _SLUG_INVALID_CHARS_PATTERN.sub("_", name_without_extension.lower()).strip("_")
        return slug or "document"

    @staticmethod
    def _make_unique(base_slug: str, used_slugs: Set[str]) -> str:
        """Append a numeric suffix if base_slug was already used by an earlier document."""
        if base_slug not in used_slugs:
            used_slugs.add(base_slug)
            return base_slug

        counter = 2
        while f"{base_slug}_{counter}" in used_slugs:
            counter += 1
        unique_slug = f"{base_slug}_{counter}"
        used_slugs.add(unique_slug)
        return unique_slug

    def export(self, documents: List[ProcessedDocument]) -> List[KnowledgeIndexEntry]:
        """
        Write each document to its own JSON file and build the index entries.
        Does NOT write knowledge_index.json itself — call save_index() with
        the returned entries to do that (kept separate so callers can
        inspect/modify entries before saving, if needed).

        Args:
            documents: Results from DocumentManager.process_documents().

        Returns:
            List of KnowledgeIndexEntry describing what was written.
        """
        self.documents_dir.mkdir(parents=True, exist_ok=True)

        used_slugs: Set[str] = set()
        index_entries: List[KnowledgeIndexEntry] = []

        for sequence_id, document in enumerate(documents, start=1):
            stem = Path(document.filename).stem
            slug = self._make_unique(self._slugify(stem), used_slugs)
            document_json_path = self.documents_dir / f"{slug}.json"

            try:
                with document_json_path.open("w", encoding="utf-8") as f:
                    json.dump(document.model_dump(), f, indent=2, ensure_ascii=False)
            except OSError as exc:
                logger.error(f"Failed to write JSON for '{document.filename}' to {document_json_path}: {exc}")
                continue

            relative_path = document_json_path.relative_to(self.project_root).as_posix()
            index_entries.append(
                KnowledgeIndexEntry(
                    id=sequence_id,
                    filename=document.filename,
                    type=document.document_type,
                    path=relative_path,
                    status=document.status,
                )
            )
            logger.info(f"Saved document JSON: {document.filename} -> {relative_path}")

        return index_entries

    def save_index(self, entries: List[KnowledgeIndexEntry]) -> None:
        """
        Write temp/knowledge_index.json from the given entries.

        Args:
            entries: Result of a prior call to export().
        """
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"documents": [entry.model_dump() for entry in entries]}

        try:
            with self.index_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error(f"Failed to write knowledge index to {self.index_path}: {exc}")
            raise

        logger.info(f"Saved knowledge index with {len(entries)} entries to {self.index_path}")

    def export_all(self, documents: List[ProcessedDocument]) -> List[KnowledgeIndexEntry]:
        """Convenience method: export() followed by save_index() in one call."""
        entries = self.export(documents)
        self.save_index(entries)
        return entries
