"""Base model information definitions."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelInfo:
    """Information about a model."""

    name: str
    provider: str
    supports_function_calling: bool = False
    supports_streaming: bool = False
    max_tokens: Optional[int] = None
    description: Optional[str] = None 