"""Dynamic model provider that discovers models from LiteLLM proxy."""

import asyncio
import logging
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


async def discover_litellm_models(
    base_url: str = "http://localhost:4000/v1",
    api_key: str = "sk-1234",
    timeout: float = 5.0
) -> Dict[str, List[Dict[str, any]]]:
    """Discover models from LiteLLM proxy.
    
    Args:
        base_url: Base URL of LiteLLM proxy
        api_key: API key for LiteLLM proxy
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with provider name and list of models
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"}
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Convert OpenAI models response to our format
            if "data" in data:
                models = []
                for model in data["data"]:
                    model_name = model.get("id", "unknown")
                    # Determine function calling capability based on model name
                    function_calling = _supports_function_calling(model_name)
                    
                    models.append({
                        "name": model_name,
                        "function_calling": function_calling,
                    })
                
                return {"litellm": models}
            
            return {}
            
    except Exception as e:
        logger.warning(f"Failed to discover LiteLLM models: {e}")
        return {}


def _supports_function_calling(model_name: str) -> bool:
    """Determine if a model supports function calling based on its name."""
    # Claude models generally support function calling
    if "claude" in model_name.lower():
        return True
    # Titan models typically don't support function calling
    if "titan" in model_name.lower():
        return False
    # Llama models may or may not support function calling
    if "llama" in model_name.lower():
        return False
    
    # Default to True for unknown models
    return True


def get_litellm_models() -> Dict[str, List[Dict[str, any]]]:
    """Synchronous wrapper to get LiteLLM models."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, we can't use run()
            # Return empty dict and log a warning
            logger.warning("Cannot discover LiteLLM models in running event loop")
            return {}
        return asyncio.run(discover_litellm_models())
    except Exception as e:
        logger.warning(f"Failed to get LiteLLM models: {e}")
        return {}


# Enhanced model discovery that includes both static and dynamic models
def get_all_models() -> Dict[str, List[Dict[str, any]]]:
    """Get all available models including LiteLLM proxy models."""
    from autogen_ext.models import ALL_MODELS
    
    # Start with static Bedrock models
    all_models = {
        "bedrock": [
            {
                "name": model_name,
                "function_calling": model_info.get("function_calling", False),
            }
            for model_name, model_info in ALL_MODELS.items()
        ]
    }
    
    # Add LiteLLM proxy models
    litellm_models = get_litellm_models()
    all_models.update(litellm_models)
    
    return all_models 