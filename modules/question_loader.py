"""
Question Loader.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Reads temp/questions.json (produced by Phase 2's question_detector.py) and
validates it back into a list of QuestionItem objects. Reusing
QuestionItem — rather than defining a second, near-identical model for
"a question read back from disk" — means there is exactly one schema for
"what a detected question looks like" in the whole project.
"""

import json
from pathlib import Path
from typing import List

from pydantic import ValidationError

from modules.logger import get_logger
from modules.question_detector import QuestionItem

logger = get_logger(__name__)


class QuestionLoadError(Exception):
    """Raised when questions.json cannot be found, parsed, or validated."""


def load_questions(questions_json_path: Path) -> List[QuestionItem]:
    """
    Load and validate questions.json.

    Args:
        questions_json_path: Path to temp/questions.json.

    Returns:
        List of validated QuestionItem objects.

    Raises:
        QuestionLoadError: If the file is missing, not valid JSON, or its
            contents don't match the expected QuestionItem schema.
    """
    if not questions_json_path.exists():
        message = (
            f"questions.json not found at {questions_json_path}. "
            "Run Phase 2 first: python app.py --read-docx <questionnaire.docx>"
        )
        logger.error(message)
        raise QuestionLoadError(message)

    try:
        with questions_json_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as exc:
        message = f"questions.json is not valid JSON: {questions_json_path} | {exc}"
        logger.error(message)
        raise QuestionLoadError(message) from exc

    try:
        questions = [QuestionItem.model_validate(item) for item in raw_data]
    except ValidationError as exc:
        message = f"questions.json does not match the expected format: {exc}"
        logger.error(message)
        raise QuestionLoadError(message) from exc

    logger.info(f"Loaded {len(questions)} question(s) from {questions_json_path}")
    return questions
