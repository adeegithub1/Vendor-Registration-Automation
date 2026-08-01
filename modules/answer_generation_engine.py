"""
Answer Generation Engine.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Orchestrates Phase 5 end-to-end for every question: find the matching
company document (KnowledgeMatcher), build the prompt (PromptBuilder),
request an answer (AIService), and turn the result into a validated
AnswerObject. Contains no AI-calling, matching, or prompt-building logic
itself — those all live in their own dedicated, injected components,
following the same dependency-injection pattern used by Phase 3's
DocumentManager and Phase 4's QuestionIntelligenceEngine.

NEVER HALLUCINATE, EVEN WHEN THE MATCHER FAILS
----------------------------------------------------
If KnowledgeMatcher finds no candidate document at all for a question,
this engine does NOT call the AI "just in case." No document means no
possible grounded answer, so it directly records NOT FOUND / confidence
0 — zero API calls made, and zero chance of the model guessing.

ERROR HANDLING
---------------
Per this phase's explicit requirement ("If AI request fails, retry 3
times, then continue with next question"): AIService already retries
internally. If it still fails after all retries, THIS engine catches
that final failure, logs it, and records a NOT FOUND answer for that
question so every question is still represented in the output — the
batch never stops because one question's AI call failed.
"""

import json
import time
from pathlib import Path
from typing import List

from modules.ai_service import AIService, AIServiceError
from modules.knowledge_matcher import KnowledgeMatcher
from modules.logger import get_logger
from modules.models import AnswerObject, QuestionObject
from modules.prompt_builder import PromptBuilder

logger = get_logger(__name__)

_NOT_FOUND_ANSWER = "NOT FOUND"


class AnswerGenerationEngine:
    """Generates an AnswerObject for every QuestionObject, tolerating per-question failures."""

    def __init__(self, ai_service: AIService, knowledge_matcher: KnowledgeMatcher, prompt_builder: PromptBuilder):
        self.ai_service = ai_service
        self.knowledge_matcher = knowledge_matcher
        self.prompt_builder = prompt_builder

    @staticmethod
    def _not_found_answer(question_id: int) -> AnswerObject:
        return AnswerObject(question_id=question_id, answer=_NOT_FOUND_ANSWER, confidence=0, source_document="")

    @staticmethod
    def _parsed_dict_to_answer_object(question_id: int, parsed: dict, fallback_source: str) -> AnswerObject:
        """
        Convert the AI's raw parsed JSON into a validated AnswerObject,
        defensively handling a model that returns slightly malformed
        fields (wrong type, missing field) rather than crashing.

        IMPORTANT: question_id is ALWAYS taken from the caller's known
        value (the question we actually asked about), never from the
        AI's echoed "question_id" field. We already have ground truth
        for which question this answer belongs to; trusting the model's
        echo instead would let a model error (or an off-by-one mistake
        in its response) silently attribute an answer to the wrong
        question. If the AI's echo doesn't match, that's logged as a
        warning (useful for spotting prompt/parsing issues) but never
        allowed to corrupt the stored result.
        """
        echoed_id = parsed.get("question_id")
        if echoed_id is not None and int(echoed_id) != question_id:
            logger.warning(
                f"AI echoed question_id={echoed_id} but the actual question was id={question_id}; "
                "using the known correct id."
            )

        try:
            return AnswerObject(
                question_id=question_id,
                answer=str(parsed.get("answer", _NOT_FOUND_ANSWER)) or _NOT_FOUND_ANSWER,
                confidence=max(0, min(100, int(parsed.get("confidence", 0)))),
                # DESIGN CHOICE: source_document always falls back to the
                # document that was actually matched and sent to the AI
                # (fallback_source), even when the answer is NOT FOUND.
                # This is deliberate: it preserves an audit trail of which
                # document WAS checked for this question, rather than
                # leaving reviewers to wonder whether any document was
                # consulted at all.
                source_document=str(parsed.get("source_document", fallback_source) or fallback_source),
            )
        except (TypeError, ValueError) as exc:
            logger.warning(f"AI response for question id={question_id} had unexpected fields ({exc}); using NOT FOUND.")
            return AnswerGenerationEngine._not_found_answer(question_id)

    def _generate_one(self, question_object: QuestionObject) -> "tuple[AnswerObject, int]":
        """
        Returns:
            (AnswerObject, api_call_count) for this one question.
        """
        match = self.knowledge_matcher.find_document(question_object.possible_document)
        if match is None:
            logger.info(
                f"No matching company document for question id={question_object.id} "
                f"(predicted: '{question_object.possible_document}') — skipping AI call, recording NOT FOUND."
            )
            return self._not_found_answer(question_object.id), 0

        document_text, source_filename = match
        user_prompt = self.prompt_builder.build_user_prompt(question_object, document_text, source_filename)

        parsed, api_calls = self.ai_service.request_json_answer(user_prompt)
        answer_object = self._parsed_dict_to_answer_object(question_object.id, parsed, source_filename)
        return answer_object, api_calls

    def generate_answers(self, question_objects: List[QuestionObject]) -> List[AnswerObject]:
        """
        Generate an answer for every question, tolerating individual failures.

        Args:
            question_objects: Questions loaded from temp/question_objects.json.

        Returns:
            List of AnswerObject, one per input question (including a
            NOT FOUND entry for any question that failed after retries —
            no question is ever silently dropped from the output).
        """
        start_time = time.perf_counter()
        logger.info(f"Questions to process: {len(question_objects)}")

        answers: List[AnswerObject] = []
        total_api_calls = 0
        failed_count = 0
        response_times: List[float] = []

        for question_object in question_objects:
            question_start = time.perf_counter()
            try:
                answer_object, api_calls = self._generate_one(question_object)
                total_api_calls += api_calls
                if api_calls > 0:
                    response_times.append(time.perf_counter() - question_start)
                answers.append(answer_object)
            except AIServiceError as exc:
                failed_count += 1
                total_api_calls += exc.attempts
                logger.error(f"Failed to generate answer for question id={question_object.id} after retries: {exc}")
                answers.append(self._not_found_answer(question_object.id))
            except Exception as exc:
                # Defense in depth: any other unexpected error for one
                # question should not abort the whole batch either.
                failed_count += 1
                logger.error(f"Unexpected error generating answer for question id={question_object.id}: {exc}")
                answers.append(self._not_found_answer(question_object.id))

        elapsed_seconds = time.perf_counter() - start_time
        average_response_time = sum(response_times) / len(response_times) if response_times else 0.0

        logger.info(
            "Answer generation summary | "
            f"Questions processed: {len(answers)} | API calls: {total_api_calls} | "
            f"Failed questions: {failed_count} | Processing time: {elapsed_seconds:.2f}s | "
            f"Average response time: {average_response_time:.2f}s"
        )

        return answers


def save_answers(answers: List[AnswerObject], output_path: Path) -> None:
    """
    Save generated answers to temp/generated_answers.json.

    Args:
        answers: Result of AnswerGenerationEngine.generate_answers().
        output_path: Full path to write to (parent folder created if missing).

    Raises:
        OSError: If the file cannot be written. Logged and re-raised.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        payload = [answer.model_dump() for answer in answers]
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
    except OSError as exc:
        logger.error(f"Failed to write generated answers JSON to {output_path}: {exc}")
        raise

    logger.info(f"Saved {len(answers)} answer(s) to {output_path}")
