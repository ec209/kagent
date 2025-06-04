"""Model definitions for all providers."""

from autogen_ext.models._model_info import ModelInfo

# Import model definitions from all providers
from autogen_ext.models.bedrock import BEDROCK_MODELS, BEDROCK_MODEL_LIST

# Combine all model definitions
ALL_MODELS = {
    **BEDROCK_MODELS,
}

# List of all available models
ALL_MODEL_LIST = list(ALL_MODELS.keys())

__all__ = [
    "ModelInfo",
    "ALL_MODELS",
    "ALL_MODEL_LIST",
    "BEDROCK_MODELS",
    "BEDROCK_MODEL_LIST",
] 