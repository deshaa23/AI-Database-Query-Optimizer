"""LLM provider implementations for optimization reasoning."""

from typing import Any

from app.core.config import Settings, get_settings


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot produce a response."""


class AIConfigurationError(AIProviderError):
    """Raised when AI provider configuration is missing or unsupported."""


class AIValidationError(AIProviderError):
    """Raised when provider output fails structured or grounding validation."""


class OpenAIProvider:
    """OpenAI-compatible provider using JSON structured output."""

    def __init__(self, settings: Settings | None = None, client: Any | None = None) -> None:
        self._settings = settings or get_settings()
        if self._settings.ai_provider.lower() != "openai":
            raise AIConfigurationError("AI_PROVIDER must be set to 'openai'.")
        if not self._settings.ai_model:
            raise AIConfigurationError("AI_MODEL must be configured for the AI provider.")
        if not self._settings.openai_api_key and client is None:
            raise AIConfigurationError("OPENAI_API_KEY is required for the OpenAI provider.")

        if client is not None:
            self._client = client
        else:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise AIProviderError("The official OpenAI SDK is not installed.") from exc
            self._client = OpenAI(api_key=self._settings.openai_api_key)

    def generate_analysis(self, prompt: str) -> str:
        """Request one JSON analysis and convert provider failures to app errors."""

        try:
            response = self._client.chat.completions.create(
                model=self._settings.ai_model,
                messages=[
                    {
                        "role": "system",
                        "content": _SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                raise AIProviderError("The AI provider returned an empty response.")
            return content
        except AIProviderError:
            raise
        except Exception as exc:
            raise AIProviderError("The AI provider was unavailable.") from exc


class MockLLMProvider:
    """Deterministic, offline provider used by tests."""

    def __init__(self, response: str | dict[str, Any]) -> None:
        self._response = response
        self.prompts: list[str] = []

    def generate_analysis(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if isinstance(self._response, str):
            return self._response

        import json

        return json.dumps(self._response)


_SYSTEM_PROMPT = """You are a PostgreSQL performance engineer. Reason only from the supplied execution-plan evidence and deterministic recommendations. Treat recommendations as candidates, not guaranteed improvements. Do not invent indexes, tables, columns, row counts, timings, database configuration, or query behavior. Do not invent executable SQL: preserve deterministic suggested SQL exactly, and output null when no deterministic SQL exists. Never recommend destructive SQL. Distinguish observations, recommendations, and validation. Discuss write overhead, storage cost, index maintenance, selectivity, and impact on other queries when relevant. Prefer EXPLAIN ANALYZE validation. Never claim a percentage improvement without measured benchmark evidence. Return only the requested JSON object."""