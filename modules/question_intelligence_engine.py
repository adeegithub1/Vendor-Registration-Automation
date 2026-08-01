"""
Question Intelligence Engine.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Orchestrates the five classifiers (category, answer type, source,
priority, intent) to turn each Phase 2 QuestionItem into a fully
enriched QuestionObject. Contains no classification logic itself —
only the sequencing, error handling, and logging around calling the
classifiers.

WHY THE CLASSIFIERS ARE INJECTED (DEPENDENCY INVERSION)
-------------------------------------------------------------
Just like DocumentManager in Phase 3 took its processor registry as a
constructor argument instead of hardcoding processor classes internally,
QuestionIntelligenceEngine takes its five classifiers as constructor
arguments (each defaulting to the real implementation). This means:
  - Each classifier can be tested in isolation, or swapped for a mock,
    without touching this file.
  - If a future phase wants to swap in an AI-assisted classifier for
    one piece (e.g. category), only the constructor call changes here
    — the orchestration loop stays identical.

ERROR HANDLING
---------------
Mirrors DocumentManager's approach from Phase 3: if classifying one
question raises an exception, it's logged and that question is skipped
— the loop continues to the next question rather than aborting the
whole batch.
"""

import json
import time
from pathlib import Path
from typing import List

from modules.answer_type_classifier import AnswerTypeClassifier
from modules.category_classifier import OTHERS_CATEGORY, CategoryClassifier
from modules.intent_extractor import IntentExtractor
from modules.logger import get_logger
from modules.models import Location, QuestionObject
from modules.priority_classifier import PriorityClassifier
from modules.question_detector import QuestionItem
from modules.source_predictor import SourcePredictor

logger = get_logger(__name__)


class QuestionIntelligenceEngine:
    """Enriches raw detected questions into structured QuestionObjects."""

    def __init__(
        self,
        category_classifier: CategoryClassifier = None,
        answer_type_classifier: AnswerTypeClassifier = None,
        source_predictor: SourcePredictor = None,
        priority_classifier: PriorityClassifier = None,
        intent_extractor: IntentExtractor = None,
    ):
        # Defaults are constructed here (not as mutable default arguments
        # in the signature) to avoid the classic Python pitfall of shared
        # mutable default objects across instances.
        self.category_classifier = category_classifier or CategoryClassifier()
        self.answer_type_classifier = answer_type_classifier or AnswerTypeClassifier()
        self.source_predictor = source_predictor or SourcePredictor()
        self.priority_classifier = priority_classifier or PriorityClassifier()
        self.intent_extractor = intent_extractor or IntentExtractor()

    def _build_question_object(self, question_item: QuestionItem) -> QuestionObject:
        """Run all five classifiers for one question and assemble the result."""
        category = self.category_classifier.classify(question_item.question)
        answer_type = self.answer_type_classifier.classify(question_item.question)
        possible_document = self.source_predictor.predict(question_item.question, category)
        priority = self.priority_classifier.classify(question_item.question, category)
        intent = self.intent_extractor.extract(question_item.question)

        return QuestionObject(
            id=question_item.question_id,
            original_question=question_item.question,
            intent=intent,
            expected_answer_type=answer_type,
            possible_document=possible_document,
            category=category,
            priority=priority,
            location=Location(
                table=question_item.table,
                row=question_item.row,
                cell=question_item.answer_column,
            ),
        )

    def process_questions(self, question_items: List[QuestionItem]) -> List[QuestionObject]:
        """
        Classify every question, tolerating individual failures.

        Args:
            question_items: Questions loaded from temp/questions.json
                (via question_loader.load_questions).

        Returns:
            List of QuestionObject, one per successfully classified
            question (failed questions are logged and skipped, not
            included in the result).
        """
        start_time = time.perf_counter()
        logger.info(f"Questions loaded: {len(question_items)}")

        question_objects: List[QuestionObject] = []
        failed_count = 0
        others_count = 0
        categories_found = set()

        for question_item in question_items:
            try:
                question_object = self._build_question_object(question_item)
            except Exception as exc:
                failed_count += 1
                logger.error(f"Failed to classify question id={question_item.question_id}: {exc}")
                continue

            question_objects.append(question_object)
            categories_found.add(question_object.category)
            if question_object.category == OTHERS_CATEGORY:
                others_count += 1

        elapsed_seconds = time.perf_counter() - start_time

        logger.info(
            "Classification summary | "
            f"Loaded: {len(question_items)} | Classified: {len(question_objects)} | "
            f"Categories found: {sorted(categories_found)} | "
            f"Unknown (Others) questions: {others_count} | Failed: {failed_count} | "
            f"Processing time: {elapsed_seconds:.2f}s"
        )

        return question_objects


def save_question_objects(question_objects: List[QuestionObject], output_path: Path) -> None:
    """
    Save classified question objects to a JSON file.

    Args:
        question_objects: Result of QuestionIntelligenceEngine.process_questions().
        output_path: Full path to temp/question_objects.json (parent folder
            is created automatically if missing).

    Raises:
        OSError: If the file cannot be written (e.g. permissions issue,
            disk full). Logged and re-raised so the caller can decide
            how to handle it.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = [q.model_dump() for q in question_objects]
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error(f"Failed to write question objects JSON to {output_path}: {exc}")
        raise

    logger.info(f"Saved {len(question_objects)} question object(s) to {output_path}")
