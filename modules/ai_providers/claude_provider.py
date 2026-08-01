"""
Claude Provider (Version 1 stub).

WHY THIS CLASS EXISTS IN AN UNFINISHED STATE
-------------------------------------------------
Per this phase's explicit scope, only GeminiProvider has a working
implementation in Version 1. ClaudeProvider exists now so that:
  1. PROVIDER_REGISTRY can list it (proving the registry pattern actually
     supports multiple providers, not just one hardcoded case).
  2. Implementing it later is purely additive — write the real
     generate() method body, install the `anthropic` package, done.
     No changes needed anywhere else in the application.

This is a genuine stub, not a fake/partial implementation: calling
generate() raises NotImplementedError with a clear message, rather than
silently returning a placeholder answer that could be mistaken for a
real one.
"""

from modules.ai_providers.base_provider import BaseAIProvider


class ClaudeProvider(BaseAIProvider):
    """Not implemented in Version 1. Reserved for a future Claude-based provider."""

    def __init__(self, api_key: str, model: str):
        # Constructor accepts the same shape of arguments as GeminiProvider
        # (api_key, model) so that swapping providers later requires no
        # change to how the provider is constructed elsewhere in the app —
        # only the class being instantiated changes.
        self.api_key = api_key
        self.model = model

    def generate(self, system_instruction: str, user_prompt: str) -> str:
        raise NotImplementedError(
            "ClaudeProvider is not implemented in Version 1. "
            "To enable it: implement this method using the 'anthropic' package, "
            "then set AI_PROVIDER=claude in .env."
        )
