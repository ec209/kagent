# Implementing AWS Bedrock Support

The backend controller has been properly configured to support Bedrock models, but the models don't appear in the UI because the autogen_ext Python package doesn't have a proper implementation for Bedrock models.

## Required Changes

1. Create a new directory structure in the autogen_ext package:
   ```
   autogen_ext/models/bedrock/
   ├── __init__.py
   ├── _client.py
   └── _model_info.py
   ```

2. Implement the `_model_info.py` file with the available Bedrock models:
   ```python
   """Information about AWS Bedrock models."""
   
   BEDROCK_MODELS = {
       "anthropic.claude-3-opus-20240229-v1:0": {
           "name": "anthropic.claude-3-opus-20240229-v1:0",
           "function_calling": True,
       },
       "anthropic.claude-3-sonnet-20240229-v1:0": {
           "name": "anthropic.claude-3-sonnet-20240229-v1:0",
           "function_calling": True,
       },
       "anthropic.claude-3-haiku-20240307-v1:0": {
           "name": "anthropic.claude-3-haiku-20240307-v1:0", 
           "function_calling": True,
       },
       "anthropic.claude-2.1:0": {
           "name": "anthropic.claude-2.1:0",
           "function_calling": False,
       },
       "amazon.titan-text-express-v1": {
           "name": "amazon.titan-text-express-v1",
           "function_calling": False,
       },
       "meta.llama2-13b-chat-v1": {
           "name": "meta.llama2-13b-chat-v1",
           "function_calling": False,
       },
   }
   
   # Function to get model info by name
   def get_model_info(model_name):
       """Get model info for AWS Bedrock models."""
       return BEDROCK_MODELS.get(model_name)
   
   # Function to list all Bedrock models
   def list_models():
       """List all AWS Bedrock models."""
       return list(BEDROCK_MODELS.values())
   ```

3. Implement the `_client.py` file with the Bedrock client:
   ```python
   """AWS Bedrock client implementation."""
   import json
   from typing import Any, Dict, List, Optional, Union
   
   try:
       import boto3
   except ImportError:
       boto3 = None
   
   from autogen_ext.models._utils.completion_utils import get_response_unsafe, APIStatus
   from ._model_info import get_model_info
   
   class BedrockChatCompletionClient:
       """Chat completion client for AWS Bedrock."""
       
       def __init__(
           self,
           api_key: str,
           secret_key: str,
           region: str,
           model: str,
           model_info: Optional[Dict[str, Any]] = None,
           **kwargs,
       ):
           """Initialize the BedrockChatCompletionClient."""
           if boto3 is None:
               raise ImportError(
                   "The boto3 package is required to use the BedrockChatCompletionClient. "
                   "Please install it with `pip install boto3`."
               )
           
           self.api_key = api_key
           self.secret_key = secret_key
           self.region = region
           self.model = model
           self.model_info = model_info or get_model_info(model) or {}
           self.kwargs = kwargs
           
           # Initialize the Bedrock runtime client
           self.client = boto3.client(
               service_name="bedrock-runtime",
               region_name=self.region,
               aws_access_key_id=self.api_key,
               aws_secret_access_key=self.secret_key,
           )
       
       def create(self, messages: List[Dict[str, str]], **kwargs):
           """Create a chat completion."""
           # Implementation will depend on the model provider (Anthropic, Amazon, etc.)
           # This is a simplified implementation focused on Anthropic Claude models
           
           combined_kwargs = {**self.kwargs, **kwargs}
           max_tokens = combined_kwargs.get("max_tokens", 1000)
           temperature = combined_kwargs.get("temperature", 0.7)
           top_p = combined_kwargs.get("top_p", 0.9)
           
           # Prepare the prompt format based on the model provider
           if self.model.startswith("anthropic."):
               # Convert messages to Claude format
               prompt = self._convert_messages_to_claude_format(messages)
               
               # Prepare request body for Anthropic Claude
               body = {
                   "anthropic_version": "bedrock-2023-05-31",
                   "max_tokens": max_tokens,
                   "temperature": temperature,
                   "top_p": top_p,
                   "messages": prompt,
               }
           else:
               # Default format for other models (simplified)
               prompt = self._convert_messages_to_text(messages)
               
               # Generic request body
               body = {
                   "inputText": prompt,
                   "textGenerationConfig": {
                       "maxTokenCount": max_tokens,
                       "temperature": temperature,
                       "topP": top_p,
                   },
               }
           
           try:
               response = self.client.invoke_model(
                   modelId=self.model,
                   body=json.dumps(body),
               )
               
               # Parse the response based on the model provider
               if self.model.startswith("anthropic."):
                   response_body = json.loads(response["body"].read())
                   content = response_body.get("content", [])
                   if content and isinstance(content, list) and len(content) > 0:
                       text = content[0].get("text", "")
                   else:
                       text = ""
               else:
                   response_body = json.loads(response["body"].read())
                   text = response_body.get("results", [{}])[0].get("outputText", "")
               
               # Create a response in a format compatible with other clients
               completion = {
                   "id": "bedrock-" + self.model,
                   "object": "chat.completion",
                   "created": int(response["responseMetadata"]["HTTPHeaders"]["date"]),
                   "model": self.model,
                   "choices": [
                       {
                           "index": 0,
                           "message": {"role": "assistant", "content": text},
                           "finish_reason": "stop",
                       }
                   ],
                   "usage": {
                       "prompt_tokens": -1,  # Not provided by Bedrock
                       "completion_tokens": -1,  # Not provided by Bedrock
                       "total_tokens": -1,  # Not provided by Bedrock
                   },
               }
               
               return APIStatus(success=True), completion
           
           except Exception as e:
               return APIStatus(success=False, message=str(e)), None
       
       def _convert_messages_to_claude_format(self, messages):
           """Convert standard chat messages to Claude format."""
           claude_messages = []
           
           for message in messages:
               role = message["role"]
               content = message["content"]
               
               if role == "system":
                   # For Claude, system messages are typically added to the first user message
                   # We'll handle this separately
                   system_content = content
               elif role == "user":
                   claude_messages.append({"role": "user", "content": content})
               elif role == "assistant":
                   claude_messages.append({"role": "assistant", "content": content})
           
           # Add system message to the first user message if present
           if claude_messages and "system_content" in locals():
               first_user_idx = next((i for i, msg in enumerate(claude_messages) if msg["role"] == "user"), None)
               if first_user_idx is not None:
                   claude_messages[first_user_idx]["content"] = f"{system_content}\n\n{claude_messages[first_user_idx]['content']}"
           
           return claude_messages
       
       def _convert_messages_to_text(self, messages):
           """Convert standard chat messages to plain text format."""
           text = ""
           
           for message in messages:
               role = message["role"]
               content = message["content"]
               
               if role == "system":
                   text += f"System: {content}\n\n"
               elif role == "user":
                   text += f"Human: {content}\n\n"
               elif role == "assistant":
                   text += f"Assistant: {content}\n\n"
           
           text += "Assistant: "
           return text
   ```

4. Update the `__init__.py` file to expose the client:
   ```python
   """AWS Bedrock models support for Autogen."""
   
   from ._client import BedrockChatCompletionClient
   from ._model_info import list_models, get_model_info
   
   __all__ = ["BedrockChatCompletionClient", "list_models", "get_model_info"]
   ```

5. Update the models endpoint to include Bedrock models: 
   - The models API endpoint should be updated to include Bedrock models in its response
   - Ensure that the API correctly converts the provider name "Bedrock" to "bedrock" in the response

## Implementation

After making these changes to the autogen_ext package, rebuild and redeploy the controller:

```bash
cd /Users/taegi.kim/vts/misc/kagent
VERSION=5305f75-dirty make helm-version
kubectl -n kagent rollout restart deployment kagent
```

This should allow Bedrock models to appear in the UI's model selection dropdown. 