"""
AI Providers package.

THE PROVIDER REGISTRY
------------------------
PROVIDER_REGISTRY maps a provider name string (from settings.ai_provider,
e.g. "gemini") to the class implementing it. This is the exact same
pattern as Phase 3's PROCESSOR_REGISTRY (extension -> processor class):
the rest of the application depends only on this dict, never on a
specific provider class directly.

ADDING A FUTURE LOCAL LLM PROVIDER
---------------------------------------
    from modules.ai_providers.local_llm_provider import LocalLLMProvider
    PROVIDER_REGISTRY["local"] = LocalLLMProvider

No other file in the application needs to change.

WHY create_provider() EXISTS
---------------------------------
Constructing a provider needs different arguments depending on which one
it is (an API key + model name, in every current case, but a future
local LLM provider might need e.g. a file path instead). Centralizing
"given the app's settings, build me the configured provider" in one
function keeps that provider-specific construction logic out of
app.py and out of AIService.
"""

from typing import Dict, Type

from modules.ai_providers.base_provider import AIProviderError, BaseAIProvider
from modules.ai_providers.claude_provider import ClaudeProvider
from modules.ai_providers.gemini_provider import GeminiProvider
from modules.ai_providers.openai_provider import OpenAIProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseAIProvider]] = {
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def create_provider(provider_name: str, api_key: str, model: str) -> BaseAIProvider:
    """
    Build a configured provider instance for the given provider name.

    Args:
        provider_name: Key into PROVIDER_REGISTRY, e.g. "gemini".
        api_key: The API key for that provider.
        model: The model name for that provider.

    Returns:
        A constructed, ready-to-use BaseAIProvider.

    Raises:
        AIProviderError: If provider_name isn't registered, or the
            provider's own constructor rejects the given arguments
            (e.g. a missing API key).
    """
    provider_class = PROVIDER_REGISTRY.get(provider_name)
    if provider_class is None:
        available = ", ".join(sorted(PROVIDER_REGISTRY.keys()))
        raise AIProviderError(f"Unknown AI provider '{provider_name}'. Available providers: {available}")

    return provider_class(api_key=api_key, model=model)
