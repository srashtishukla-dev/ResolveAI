
import os
from collections.abc import Callable
from typing import Protocol

from django.conf import settings


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider cannot generate a grounded answer."""


class LLMProviderUnavailableError(LLMProviderError):
    """Raised when the configured LLM provider is disabled or unavailable."""


class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate an answer from a fully constructed grounded prompt."""


class DisabledLLMProvider:
    def generate(self, prompt: str) -> str:
        raise LLMProviderUnavailableError(
            'The LLM provider is disabled. Configure RAG_LLM_PROVIDER to enable it.'
        )


class GeminiLLMProvider:
    """Generate grounded answers using Google's Gemini API."""

    def __init__(self):
        api_key = os.environ.get('GEMINI_API_KEY', '').strip()

        if not api_key:
            raise LLMProviderUnavailableError(
                'GEMINI_API_KEY is not configured.'
            )

        try:
            from google import genai

            self.client = genai.Client(api_key=api_key)
        except Exception as exc:
            raise LLMProviderUnavailableError(
                'Gemini client could not be initialized.'
            ) from exc

        self.model = os.environ.get(
            'GEMINI_MODEL',
            'gemini-2.5-flash',
        ).strip()

        if not self.model:
            raise LLMProviderUnavailableError(
                'GEMINI_MODEL is not configured.'
            )

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )

            answer = response.text

            if not answer or not answer.strip():
                raise LLMProviderError(
                    'Gemini returned an empty answer.'
                )

            return answer.strip()

        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(
                'Gemini could not generate an answer. Check the API configuration and try again.'
            ) from exc


_ProviderFactory = Callable[[], LLMProvider]

_PROVIDER_FACTORIES: dict[str, _ProviderFactory] = {
    'disabled': DisabledLLMProvider,
    'gemini': GeminiLLMProvider,
}


def register_llm_provider(name: str, factory: _ProviderFactory) -> None:
    """Register a provider factory for a configured provider name."""
    normalized_name = name.strip().lower()

    if not normalized_name:
        raise ValueError('Provider name must not be empty.')

    _PROVIDER_FACTORIES[normalized_name] = factory


def get_llm_provider() -> LLMProvider:
    """Return the provider configured by the existing RAG environment setting."""
    provider_name = str(
        settings.RAG_CONFIG.get('LLM_PROVIDER', 'disabled')
    ).strip().lower()

    factory = _PROVIDER_FACTORIES.get(provider_name)

    if factory is None:
        raise LLMProviderUnavailableError(
            'The configured LLM provider is unavailable.'
        )

    return factory()

