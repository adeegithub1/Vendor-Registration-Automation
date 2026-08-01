"""
AI Service.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
This is the ONLY module in the application that knows how to turn a
prompt into a parsed, validated JSON answer. Per this phase's explicit
architecture requirement, nothing else in the codebase talks to Gemini,
Claude, or OpenAI directly — everything goes through AIService, which
holds a BaseAIProvider (injected, see modules/ai_providers/).

    Application -> AIService -> BaseAIProvider -> (Gemini | Claude | OpenAI | ...)

WHAT LIVES HERE VS. IN THE PROVIDER
----------------------------------------
- Provider: "send this exact text to the model, return its raw text reply."
- AIService: retry logic, JSON parsing (with defensive markdown-fence
  stripping in case a provider doesn't perfectly honor the "no markdown"
  instruction), and counting how many actual API calls were made (needed
  for this phase's "API Calls" logging requirement).

RETRY LOGIC
------------
If a request fails (network error, API error, or the response isn't
valid JSON), AIService retries up to `max_retries` times with a fixed
delay between attempts, before giving up and raising AIServiceError.
The caller (AnswerGenerationEngine) is responsible for deciding what
happens next for that question (per this phase's requirement: continue
with the next question, recording a NOT FOUND answer rather than
crashing the whole batch).
"""

import json
import re
import time
from typing import Tuple

from modules.ai_providers.base_provider import AIProviderError, BaseAIProvider
from modules.logger import get_logger

logger = get_logger(__name__)

# Defensive cleanup: strips ```json ... ``` or ``` ... ``` fences, in case a
# model wraps its JSON in markdown despite being instructed not to.
_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class AIServiceError(Exception):
    """Raised when an AI request fails after all retry attempts are exhausted."""

    def __init__(self, message: str, attempts: int = 0):
        super().__init__(message)
        self.attempts = attempts


class AIService:
    """The application's single entry point for requesting an AI-generated answer."""

    def __init__(self, provider: BaseAIProvider, system_instruction: str, max_retries: int = 3, retry_delay_seconds: float = 2.0):
        """
        Args:
            provider: The concrete AI provider to use (injected — this
                class never constructs one itself).
            system_instruction: Loaded from prompts/system_prompt.txt.
            max_retries: How many attempts before giving up on a request.
            retry_delay_seconds: Delay between retry attempts.
        """
        self.provider = provider
        self.system_instruction = system_instruction
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

    @staticmethod
    def _parse_json_response(raw_text: str) -> dict:
        cleaned = raw_text.strip()
        cleaned = _MARKDOWN_FENCE_PATTERN.sub("", cleaned).strip()
        return json.loads(cleaned)

    def request_json_answer(self, user_prompt: str) -> Tuple[dict, int]:
        """
        Request an answer for one question, with retries.

        Args:
            user_prompt: The filled user prompt (from PromptBuilder).

        Returns:
            (parsed_json_dict, api_call_count) — api_call_count is how
            many actual attempts were made (1 if it succeeded on the
            first try, up to max_retries if earlier attempts failed).

        Raises:
            AIServiceError: If every attempt failed. The exception
                message includes the last underlying error.
        """
        last_error: Exception = AIServiceError("No attempts were made.")

        for attempt in range(1, self.max_retries + 1):
            try:
                raw_response = self.provider.generate(self.system_instruction, user_prompt)
                parsed = self._parse_json_response(raw_response)
                return parsed, attempt
            except (AIProviderError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(f"AI request attempt {attempt}/{self.max_retries} failed: {exc}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_seconds)

        raise AIServiceError(
            f"AI request failed after {self.max_retries} attempts: {last_error}",
            attempts=self.max_retries,
        ) from last_error
