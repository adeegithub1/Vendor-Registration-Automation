"""
Base AI Provider.

WHAT THIS MODULE IS RESPONSIBLE FOR
-------------------------------------
Defines the single interface every AI provider must implement:
`generate(system_instruction, user_prompt) -> str`. This is the entire
contract. Nothing in this codebase outside modules/ai_providers/ and
modules/ai_service.py knows or cares whether "the AI" is Gemini, Claude,
OpenAI, or a future local LLM — it only ever talks to this interface via
AIService.

WHY THIS IS AN ABSTRACT CLASS, NOT JUST A DUCK-TYPED CONVENTION
---------------------------------------------------------------------
Using Python's `abc` module means a provider that forgets to implement
`generate()` fails immediately and loudly at class-definition time (or
instantiation time), not with a confusing AttributeError deep inside a
batch run over 200 questions. This matters more here than usual, because
provider implementations may be written by different people at different
times (e.g. whoever eventually builds ClaudeProvider for real).

WHAT A PROVIDER IS *NOT* RESPONSIBLE FOR
--------------------------------------------
Retry logic, JSON parsing/validation, and prompt construction all live
in AIService and PromptBuilder, not here. A provider's only job is:
given a system instruction and a user prompt, return the raw text the
model responded with, or raise AIProviderError if the call failed.
"""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised by a provider when an AI request fails for any reason (network, auth, API error, etc.)."""


class BaseAIProvider(ABC):
    """Abstract interface every AI provider (Gemini, Claude, OpenAI, ...) must implement."""

    @abstractmethod
    def generate(self, system_instruction: str, user_prompt: str) -> str:
        """
        Send a request to the underlying AI model and return its raw text response.

        Args:
            system_instruction: The provider-level instructions (rules,
                output format requirements) — see prompts/system_prompt.txt.
            user_prompt: The specific question + context for this request
                — see prompts/user_prompt.txt.

        Returns:
            The raw text of the model's response (expected to be a JSON
            string, but this method does not parse or validate it — that
            is AIService's job).

        Raises:
            AIProviderError: If the request fails for any reason. Should
                NOT be caught here — let it propagate to AIService, which
                owns retry decisions.
        """
        raise NotImplementedError
