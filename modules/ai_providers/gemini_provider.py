"""
Gemini Provider.

LIBRARY USED: google-genai
------------------------------
This is Google's current officially-recommended Python SDK for the
Gemini API (the older `google-generativeai` package is being phased out
in favor of this one). Verified against Google's current documentation
at the time this was written — SDK/model names in this space change
frequently, so `gemini_model` is fully configurable via .env
(GEMINI_MODEL) rather than hardcoded, and should be re-checked against
Google's current model list periodically.

HOW JSON-ONLY OUTPUT IS ENFORCED
-------------------------------------
Beyond instructing the model via the system prompt (see
prompts/system_prompt.txt), this provider also sets
`response_mime_type="application/json"` in the request config. This is a
genuine API-level constraint (not just a polite request in the prompt),
which is why the design of AIService's response parsing still defensively
strips markdown code fences — belt-and-suspenders, in case a future model
version does not honor this constraint perfectly.

TEMPERATURE = 0
-----------------
Set to make responses as deterministic and literal as possible, since
this is a data-extraction task (find the answer in the provided text),
not a creative one. This reduces (but per the "never hallucinate"
system instruction, does not eliminate the need to explicitly check for)
the model inventing plausible-sounding but unsupported answers.

WHAT THIS PROVIDER DOES NOT DO
------------------------------------
No retry logic (that's AIService's job). No JSON parsing (also
AIService's job). This class's only responsibility is turning a
(system_instruction, user_prompt) pair into a raw text response, or
raising AIProviderError.
"""

from modules.ai_providers.base_provider import AIProviderError, BaseAIProvider
from modules.logger import get_logger

logger = get_logger(__name__)


class GeminiProvider(BaseAIProvider):
    """Sends requests to the Gemini API via Google's google-genai SDK."""

    def __init__(self, api_key: str, model: str):
        """
        Args:
            api_key: Gemini API key (from settings.gemini_api_key).
            model: Gemini model name (from settings.gemini_model).

        Raises:
            AIProviderError: If api_key is missing/empty, or the SDK
                client cannot be constructed.
        """
        if not api_key:
            raise AIProviderError(
                "Gemini API key is missing. Set GEMINI_API_KEY in .env (and AI_PROVIDER=gemini)."
            )

        try:
            # Imported here rather than at module top-level so that importing
            # this file doesn't hard-require the google-genai package to be
            # installed unless a GeminiProvider is actually constructed —
            # relevant since ClaudeProvider/OpenAIProvider users shouldn't
            # need Gemini's SDK installed at all.
            from google import genai
        except ImportError as exc:
            raise AIProviderError(
                "The 'google-genai' package is not installed. Run: pip install google-genai"
            ) from exc

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, system_instruction: str, user_prompt: str) -> str:
        """
        Args:
            system_instruction: Rules/output-format instructions.
            user_prompt: The specific question + document context.

        Returns:
            The raw text of Gemini's response.

        Raises:
            AIProviderError: If the API call fails or returns no text.
        """
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )
        except Exception as exc:
            # The SDK can raise several different exception types depending on
            # the failure (auth error, rate limit, network issue, invalid
            # model name, etc.). We normalize all of them to AIProviderError
            # so AIService only needs to handle one exception type.
            raise AIProviderError(f"Gemini API request failed: {exc}") from exc

        response_text = getattr(response, "text", None)
        if not response_text:
            raise AIProviderError("Gemini API returned an empty response.")

        return response_text
