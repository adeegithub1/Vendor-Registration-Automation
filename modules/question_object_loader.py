"""
Question Object Loader.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Reads temp/question_objects.json (produced by Phase 4's
question_intelligence_engine.py) and validates it back into a list of
QuestionObject models. Mirrors modules/question_loader.py's approach from
Phase 4 (which does the same thing for Phase 2's questions.json) — one
small loader per JSON artifact, each reusing the shared Pydantic model
rather than re-parsing into raw dicts.
"""

import json
from pathlib import Path
from typing import List

from pydantic import ValidationError

from modules.logger import get_logger
from modules.models import QuestionObject

logger = get_logger(__name__)


class QuestionObjectLoadError(Exception):
    """Raised when question_objects.json cannot be found, parsed, or validated."""


def load_question_objects(question_objects_json_path: Path) -> List[QuestionObject]:
    """
    Load and validate question_objects.json.

    Args:
        question_objects_json_path: Path to temp/question_objects.json.

    Returns:
        List of validated QuestionObject instances.

    Raises:
        QuestionObjectLoadError: If the file is missing, not valid JSON,
            or its contents don't match the expected schema.
    """
    if not question_objects_json_path.exists():
        message = (
            f"question_objects.json not found at {question_objects_json_path}. "
            "Run Phase 4 first: python app.py --classify-questions"
        )
        logger.error(message)
        raise QuestionObjectLoadError(message)

    try:
        with question_objects_json_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as exc:
        message = f"question_objects.json is not valid JSON: {question_objects_json_path} | {exc}"
        logger.error(message)
        raise QuestionObjectLoadError(message) from exc

    try:
        question_objects = [QuestionObject.model_validate(item) for item in raw_data]
    except ValidationError as exc:
        message = f"question_objects.json does not match the expected format: {exc}"
        logger.error(message)
        raise QuestionObjectLoadError(message) from exc

    logger.info(f"Loaded {len(question_objects)} question object(s) from {question_objects_json_path}")
    return question_objects
