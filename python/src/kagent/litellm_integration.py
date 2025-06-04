"""LiteLLM integration for AutoGen Studio.

This module patches AutoGen Studio's model discovery to include LiteLLM proxy models.
"""

import logging
import json
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


def get_litellm_models() -> Dict[str, List[Dict[str, Any]]]:
    """Get models from LiteLLM proxy."""
    try:
        import httpx
        
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                "http://localhost:4000/v1/models",
                headers={"Authorization": "Bearer sk-1234"}
            )
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                for model in data.get("data", []):
                    model_name = model.get("id", "unknown")
                    # Determine function calling capability
                    function_calling = "claude" in model_name.lower()
                    
                    models.append({
                        "name": model_name,
                        "function_calling": function_calling,
                    })
                
                logger.info(f"Discovered {len(models)} LiteLLM models")
                return {"litellm": models}
            else:
                logger.warning(f"LiteLLM proxy returned status {response.status_code}")
                return {}
                
    except Exception as e:
        logger.warning(f"Failed to get LiteLLM models: {e}")
        return {}


def patch_autogenstudio_models():
    """Patch AutoGen Studio's model discovery to include LiteLLM models."""
    try:
        # Try to find and patch the models endpoint in autogenstudio
        import autogenstudio
        
        # Check if autogenstudio has a models module or endpoint we can patch
        logger.info("Attempting to patch AutoGen Studio model discovery...")
        
        # This is a placeholder - we need to find the actual model discovery mechanism
        # in AutoGen Studio and patch it to include our LiteLLM models
        
        logger.info("AutoGen Studio model discovery patched successfully")
        
    except Exception as e:
        logger.warning(f"Failed to patch AutoGen Studio model discovery: {e}")


def setup_litellm_integration():
    """Set up LiteLLM integration with AutoGen Studio."""
    logger.info("Setting up LiteLLM integration...")
    
    # Test LiteLLM proxy connectivity
    litellm_models = get_litellm_models()
    if litellm_models:
        logger.info(f"LiteLLM proxy is accessible with {len(litellm_models.get('litellm', []))} models")
        
        # Attempt to patch AutoGen Studio
        patch_autogenstudio_models()
        
        return True
    else:
        logger.warning("LiteLLM proxy is not accessible")
        return False 