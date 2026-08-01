"""
OpenAI Provider (Version 1 stub).

See modules/ai_providers/claude_provider.py's docstring — the same
reasoning applies here. Not implemented in Version 1; exists to prove
and preserve the provider-swapping architecture.
"""

from modules.ai_providers.base_provider import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """Not implemented in Version 1. Reserved for a future OpenAI-based provider."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, system_instruction: str, user_prompt: str) -> str:
        raise NotImplementedError(
            "OpenAIProvider is not implemented in Version 1. "
            "To enable it: implement this method using the 'openai' package, "
            "then set AI_PROVIDER=openai in .env."
        )
