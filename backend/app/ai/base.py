"""Provider abstraction for AI optimization reasoning."""

from typing import Protocol


class LLMProvider(Protocol):
    """Minimal provider contract used by AIOptimizer."""

    def generate_analysis(self, prompt: str) -> str:
        """Return a JSON-encoded optimization analysis."""