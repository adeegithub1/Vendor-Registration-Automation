"""
Answer Loader.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Reads temp/generated_answers.json (produced by Phase 5's
answer_generation_engine.py) and validates it back into a list of
AnswerObject models. Mirrors question_loader.py and
question_object_loader.py's approach — one small loader per JSON
artifact, reusing the shared Pydantic model rather than parsing into
raw dicts.
"""

import json
from pathlib import Path
from typing import List

from pydantic import ValidationError

from modules.logger import get_logger
from modules.models import AnswerObject

logger = get_logger(__name__)


class AnswerLoadError(Exception):
    """Raised when generated_answers.json cannot be found, parsed, or validated."""


def load_answers(generated_answers_json_path: Path) -> List[AnswerObject]:
    """
    Load and validate generated_answers.json.

    Args:
        generated_answers_json_path: Path to temp/generated_answers.json.

    Returns:
        List of validated AnswerObject instances.

    Raises:
        AnswerLoadError: If the file is missing, not valid JSON, or its
            contents don't match the expected schema.
    """
    if not generated_answers_json_path.exists():
        message = (
            f"generated_answers.json not found at {generated_answers_json_path}. "
            "Run Phase 5 first: python app.py --generate-answers"
        )
        logger.error(message)
        raise AnswerLoadError(message)

    try:
        with generated_answers_json_path.open("r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as exc:
        message = f"generated_answers.json is not valid JSON: {generated_answers_json_path} | {exc}"
        logger.error(message)
        raise AnswerLoadError(message) from exc

    try:
        answers = [AnswerObject.model_validate(item) for item in raw_data]
    except ValidationError as exc:
        message = f"generated_answers.json does not match the expected format: {exc}"
        logger.error(message)
        raise AnswerLoadError(message) from exc

    logger.info(f"Loaded {len(answers)} answer(s) from {generated_answers_json_path}")
    return answers
