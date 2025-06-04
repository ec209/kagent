"""LiteLLM chat completion client."""

import os
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    FunctionExecutionResult,
    FunctionExecutionResultMessage,
    LLMMessage,
    ModelCapabilities,
    RequestUsage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
    FunctionCallMessage,
    ToolCallMessage,
    ToolCallResultMessage
)
from autogen_core import CancellationToken, Component
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, Field
from typing_extensions import Self


class LiteLLMChatCompletionClientConfig(BaseModel):
    """Configuration for LiteLLM chat completion client."""
    
    model: str = Field(description="Model name available in LiteLLM proxy")
    api_key: str = Field(default="sk-1234", description="API key for LiteLLM proxy")
    base_url: str = Field(default="http://localhost:4000/v1", description="Base URL for LiteLLM proxy")
    temperature: Optional[float] = Field(default=None, description="Temperature for sampling")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens to generate")
    timeout: Optional[float] = Field(default=None, description="Request timeout in seconds")


class LiteLLMChatCompletionClient(ChatCompletionClient, Component[LiteLLMChatCompletionClientConfig]):
    """Chat completion client for LiteLLM proxy accessing Bedrock models."""
    
    component_config_schema = LiteLLMChatCompletionClientConfig
    component_type = "model"
    component_provider_override = "autogen_ext.models.litellm.LiteLLMChatCompletionClient"

    def __init__(
        self,
        model: str,
        api_key: str = "sk-1234",
        base_url: str = "http://localhost:4000/v1",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Initialize the LiteLLM chat completion client.
        
        Args:
            model: Model name available in LiteLLM proxy
            api_key: API key for LiteLLM proxy
            base_url: Base URL for LiteLLM proxy
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
        """
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        
        # Initialize OpenAI client pointing to LiteLLM proxy
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
        )

    @property
    def capabilities(self) -> ModelCapabilities:
        """Return the capabilities of the model."""
        return ModelCapabilities(
            function_calling=True,
            vision=False,
            json_output=True,
        )

    @property
    def count_tokens(self) -> int:
        """Return the number of tokens used."""
        # For now, we don't implement token counting
        return 0

    def _convert_message(self, message: LLMMessage) -> Dict[str, Any]:
        """Convert LLM message to OpenAI format."""
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        elif isinstance(message, UserMessage):
            return {"role": "user", "content": message.content}
        elif isinstance(message, AssistantMessage):
            return {"role": "assistant", "content": message.content}
        elif isinstance(message, FunctionCallMessage):
            return {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": message.function_call.id,
                    "type": "function",
                    "function": {
                        "name": message.function_call.name,
                        "arguments": message.function_call.arguments,
                    }
                }]
            }
        elif isinstance(message, ToolCallMessage):
            return {
                "role": "assistant", 
                "content": None,
                "tool_calls": [{
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    }
                } for call in message.tool_calls]
            }
        elif isinstance(message, (FunctionExecutionResultMessage, ToolCallResultMessage)):
            if isinstance(message, FunctionExecutionResultMessage):
                return {
                    "role": "tool",
                    "tool_call_id": message.function_call_id,
                    "content": str(message.content),
                }
            else:
                # ToolCallResultMessage
                results = []
                for result in message.content:
                    results.append({
                        "role": "tool",
                        "tool_call_id": result.tool_call_id,
                        "content": str(result.content),
                    })
                return results
        else:
            raise ValueError(f"Unsupported message type: {type(message)}")

    async def create(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[Union[Any, Dict[str, Any]]] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CreateResult:
        """Create a chat completion."""
        # Convert messages
        openai_messages = []
        for message in messages:
            converted = self._convert_message(message)
            if isinstance(converted, list):
                openai_messages.extend(converted)
            else:
                openai_messages.append(converted)

        # Prepare request parameters
        request_params: Dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            **extra_create_args,
        }

        if self._temperature is not None:
            request_params["temperature"] = self._temperature
        if self._max_tokens is not None:
            request_params["max_tokens"] = self._max_tokens

        if tools:
            # Convert tools to OpenAI format
            openai_tools = []
            for tool in tools:
                if isinstance(tool, dict):
                    openai_tools.append(tool)
                else:
                    # Assume it's a tool object with required properties
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        }
                    })
            request_params["tools"] = openai_tools

        if json_output:
            request_params["response_format"] = {"type": "json_object"}

        # Make the API call
        response = await self._client.chat.completions.create(**request_params)

        # Convert response
        choice = response.choices[0]
        finish_reason = choice.finish_reason or "stop"

        # Extract content and tool calls
        content = choice.message.content or ""
        tool_calls = choice.message.tool_calls or []

        # Create usage info
        usage = RequestUsage(
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        return CreateResult(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            cached=False,
            logprobs=None,
        )

    async def create_stream(
        self,
        messages: Sequence[LLMMessage],
        tools: Sequence[Union[Any, Dict[str, Any]]] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[Union[str, CreateResult], None]:
        """Create a streaming chat completion."""
        # Convert messages
        openai_messages = []
        for message in messages:
            converted = self._convert_message(message)
            if isinstance(converted, list):
                openai_messages.extend(converted)
            else:
                openai_messages.append(converted)

        # Prepare request parameters
        request_params: Dict[str, Any] = {
            "model": self._model,
            "messages": openai_messages,
            "stream": True,
            **extra_create_args,
        }

        if self._temperature is not None:
            request_params["temperature"] = self._temperature
        if self._max_tokens is not None:
            request_params["max_tokens"] = self._max_tokens

        if tools:
            # Convert tools to OpenAI format
            openai_tools = []
            for tool in tools:
                if isinstance(tool, dict):
                    openai_tools.append(tool)
                else:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.parameters,
                        }
                    })
            request_params["tools"] = openai_tools

        if json_output:
            request_params["response_format"] = {"type": "json_object"}

        # Stream the response
        content_parts = []
        usage_info = None
        
        async for chunk in await self._client.chat.completions.create(**request_params):
            if chunk.choices:
                choice = chunk.choices[0]
                if choice.delta.content:
                    content = choice.delta.content
                    content_parts.append(content)
                    yield content
                
                if choice.finish_reason:
                    # End of stream, create final result
                    full_content = "".join(content_parts)
                    usage = RequestUsage(
                        prompt_tokens=chunk.usage.prompt_tokens if chunk.usage else 0,
                        completion_tokens=chunk.usage.completion_tokens if chunk.usage else 0,
                    ) if chunk.usage else RequestUsage(prompt_tokens=0, completion_tokens=0)
                    
                    yield CreateResult(
                        content=full_content,
                        finish_reason=choice.finish_reason,
                        usage=usage,
                        cached=False,
                        logprobs=None,
                    )

    def _to_config(self) -> LiteLLMChatCompletionClientConfig:
        """Convert to configuration."""
        return LiteLLMChatCompletionClientConfig(
            model=self._model,
            api_key=self._api_key,
            base_url=self._base_url,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            timeout=self._timeout,
        )

    @classmethod
    def _from_config(cls, config: LiteLLMChatCompletionClientConfig) -> Self:
        """Create from configuration."""
        return cls(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        ) 