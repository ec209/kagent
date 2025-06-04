"""API endpoints for model management."""

from fastapi import APIRouter

# Import both static models and dynamic discovery
from autogen_ext.models import ALL_MODELS
from autogen_ext.models._dynamic_provider import get_litellm_models

router = APIRouter()


@router.get("/models")
async def list_models():
    """List all supported models."""
    # Start with static Bedrock models
    provider_models = {
        "bedrock": [
            {
            "name": model_name,
                "function_calling": model_info.get("function_calling", False),
            }
            for model_name, model_info in ALL_MODELS.items()
        ]
    }
    
    # Add LiteLLM proxy models dynamically
    litellm_models = get_litellm_models()
    provider_models.update(litellm_models)
    
    return provider_models 