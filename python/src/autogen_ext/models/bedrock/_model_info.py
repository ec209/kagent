"""Model information for AWS Bedrock models.

Note: Bedrock models should be used via LiteLLM proxy for proper integration.
See: https://microsoft.github.io/autogen/0.2/docs/topics/non-openai-models/local-litellm-ollama/
"""

from typing import Dict, List

# Bedrock models available via LiteLLM proxy
# These should be configured as LiteLLM proxy endpoints, not direct Bedrock calls
BEDROCK_MODELS: Dict[str, Dict[str, any]] = {
    # Anthropic models via Bedrock
    "anthropic.claude-3-sonnet-20240229-v1:0": {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/anthropic.claude-3-sonnet-20240229-v1:0",
    },
    "anthropic.claude-3-haiku-20240307-v1:0": {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/anthropic.claude-3-haiku-20240307-v1:0",
    },
    "anthropic.claude-3-opus-20240229-v1:0": {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/anthropic.claude-3-opus-20240229-v1:0",
    },
    # Amazon models via Bedrock
    "amazon.titan-text-express-v1": {
        "vision": False,
        "function_calling": False,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/amazon.titan-text-express-v1",
    },
    "amazon.titan-text-lite-v1": {
        "vision": False,
        "function_calling": False,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/amazon.titan-text-lite-v1",
    },
    # Meta models via Bedrock
    "meta.llama2-13b-chat-v1": {
        "vision": False,
        "function_calling": False,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/meta.llama2-13b-chat-v1",
    },
    "meta.llama2-70b-chat-v1": {
        "vision": False,
        "function_calling": False,
        "json_output": True,
        "structured_output": False,
        "multiple_system_messages": False,
        "provider": "bedrock",
        "litellm_model": "bedrock/meta.llama2-70b-chat-v1",
    },
}

# List of all Bedrock models
BEDROCK_MODEL_LIST: List[str] = list(BEDROCK_MODELS.keys()) 