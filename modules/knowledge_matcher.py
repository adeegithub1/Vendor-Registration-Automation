"""
Knowledge Matcher.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Given a QuestionObject's `possible_document` prediction (from Phase 4,
e.g. "Bank Details"), finds the best-matching entry in
temp/knowledge_index.json and loads that ONE document's extracted text
from temp/documents/<slug>.json.

WHY ONLY ONE DOCUMENT, EVER
--------------------------------
Per this phase's explicit requirement ("Do NOT send every document. Only
send the predicted relevant document"), this module never returns more
than one document's text. This keeps prompts small (cost, latency) and
is also a safety property: the AI physically cannot pull an answer from
an unrelated document if that document's text was never in the prompt.

MATCHING ALGORITHM
---------------------
Both the predicted document name (e.g. "Bank Details") and each indexed
document's actual filename (e.g. "Bank Details.xlsx") are broken into
lowercase alphanumeric word tokens, and scored by token overlap (same
technique used for filename collision-safety in Phase 3's
KnowledgeExporter, applied here for matching instead of slugifying). The
indexed document with the highest overlap score wins. If no indexed
document shares even one token with the prediction, there is no match —
find_document() returns None, and the caller (AnswerGenerationEngine)
skips the AI call entirely rather than guessing which document to send.

FAILED DOCUMENTS ARE EXCLUDED
----------------------------------
Only knowledge_index.json entries with status "success" are considered
for matching — Phase 3 documents that failed to extract have no usable
text and are correctly never selected.

CACHING
--------
Document JSON files are read from disk once per run and cached in
memory (a single questionnaire commonly has many questions whose
predicted document is the same file, e.g. many "Bank Details" questions
should all be answered from the one Bank Details document).
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from modules.logger import get_logger

logger = get_logger(__name__)

_WORD_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set:
    return set(_WORD_TOKEN_PATTERN.findall(text.lower()))


class KnowledgeMatcher:
    """Finds and loads the single best-matching company document for a predicted document name."""

    def __init__(self, knowledge_index_path: Path, project_root: Path):
        """
        Args:
            knowledge_index_path: Path to temp/knowledge_index.json.
            project_root: Project root, used to resolve the
                project-root-relative paths stored in the index.
        """
        self.project_root = project_root
        self._index_entries: List[dict] = self._load_index(knowledge_index_path)
        self._document_text_cache: Dict[str, str] = {}

    @staticmethod
    def _load_index(knowledge_index_path: Path) -> List[dict]:
        if not knowledge_index_path.exists():
            logger.warning(
                f"knowledge_index.json not found at {knowledge_index_path}. "
                "No company documents will be matched (run Phase 3 first: "
                "python app.py --extract-knowledge)."
            )
            return []

        try:
            with knowledge_index_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to load knowledge_index.json: {exc}. No company documents will be matched.")
            return []

        entries = data.get("documents", [])
        successful_entries = [entry for entry in entries if entry.get("status") == "success"]
        logger.info(
            f"Knowledge index loaded: {len(entries)} document(s) total, "
            f"{len(successful_entries)} usable (status=success)."
        )
        return successful_entries

    def _load_document_text(self, relative_path: str) -> Optional[str]:
        if relative_path in self._document_text_cache:
            return self._document_text_cache[relative_path]

        full_path = self.project_root / relative_path
        if not full_path.exists():
            logger.warning(f"Indexed document file missing on disk: {full_path}")
            return None

        try:
            with full_path.open("r", encoding="utf-8") as f:
                document_data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to load document JSON {full_path}: {exc}")
            return None

        text = document_data.get("extracted_text", "")
        self._document_text_cache[relative_path] = text
        return text

    def find_document(self, possible_document: str) -> Optional[Tuple[str, str]]:
        """
        Find the best-matching indexed document for a predicted document name.

        Args:
            possible_document: The Phase 4 prediction, e.g. "Bank Details".

        Returns:
            (document_text, source_filename) for the best match, or None
            if no indexed document shares any keyword with the prediction,
            or its text file could not be loaded.
        """
        if not self._index_entries:
            return None

        target_tokens = _tokenize(possible_document)
        if not target_tokens:
            return None

        best_entry: Optional[dict] = None
        best_score = 0

        for entry in self._index_entries:
            filename_tokens = _tokenize(entry.get("filename", ""))
            score = len(target_tokens & filename_tokens)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry is None:
            return None

        document_text = self._load_document_text(best_entry["path"])
        if document_text is None:
            return None

        return document_text, best_entry["filename"]
