"""Bedrock agent implementation for autogen-ext."""

import os
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence

import boto3
from litellm import completion
from pydantic import BaseModel, Field

from autogen_agentchat.agents._base_chat_agent import BaseChatAgent
from autogen_agentchat.base import Response
from autogen_agentchat.messages import (
    AgentEvent,
    BaseChatMessage,
    ChatMessage,
    ModelClientStreamingChunkEvent,
    TextMessage,
)
from autogen_agentchat.state import BaseState
from autogen_core import CancellationToken, Component, ComponentModel
from autogen_core.model_context import ChatCompletionContext, UnboundedChatCompletionContext


class BedrockAgentState(BaseState):
    """State for a Bedrock agent."""

    model_context_state: Mapping[str, Any] = Field(default_factory=dict)
    type: str = Field(default="BedrockAgentState")


class BedrockAgentConfig(BaseModel):
    """The declarative configuration for a BedrockAgent."""

    name: str
    model_name: str = Field(default="anthropic.claude-3-sonnet-20240229-v1:0")
    aws_region_name: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    temperature: float = Field(default=0.7)
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    stop_sequences: Optional[List[str]] = None
    model_context: ComponentModel | None = None
    description: str | None = None


class BedrockAgent(BaseChatAgent, Component[BedrockAgentConfig]):
    """Agent implementation for AWS Bedrock models."""

    component_config_schema = BedrockAgentConfig
    component_provider_override = "autogen_ext.agents.bedrock.BedrockAgent"

    DEFAULT_DESCRIPTION = "An agent that uses AWS Bedrock models to generate responses."

    def __init__(
        self,
        name: str,
        model_name: str = "anthropic.claude-3-sonnet-20240229-v1:0",
        aws_region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
        model_context: ChatCompletionContext | None = None,
        *,
        description: str = DEFAULT_DESCRIPTION,
    ) -> None:
        """Initialize the Bedrock agent.

        Args:
            name: The name of the agent
            model_name: The Bedrock model to use
            aws_region_name: AWS region name (defaults to AWS_REGION_NAME env var)
            aws_access_key_id: AWS access key ID (defaults to AWS_ACCESS_KEY_ID env var)
            aws_secret_access_key: AWS secret access key (defaults to AWS_SECRET_ACCESS_KEY env var)
            temperature: Model temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            top_p: Top-p sampling parameter
            top_k: Top-k sampling parameter
            stop_sequences: List of stop sequences
            model_context: The model context to use for preparing responses
            description: The description of the agent
        """
        super().__init__(name=name, description=description)
        self.model_name = f"bedrock/{model_name}"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.stop_sequences = stop_sequences
        self._model_context = model_context or UnboundedChatCompletionContext()

        # Set AWS credentials from environment variables if not provided
        self.aws_region_name = aws_region_name or os.getenv("AWS_REGION_NAME")
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")

        if not all([self.aws_region_name, self.aws_access_key_id, self.aws_secret_access_key]):
            raise ValueError(
                "AWS credentials must be provided either through parameters or environment variables: "
                "AWS_REGION_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY"
            )

    @property
    def produced_message_types(self) -> Sequence[type[ChatMessage]]:
        return (TextMessage,)

    async def on_messages(self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken) -> Response:
        # Call the stream method and collect the messages.
        response: Response | None = None
        async for msg in self.on_messages_stream(messages, cancellation_token):
            if isinstance(msg, Response):
                response = msg
        assert response is not None
        return response

    async def on_messages_stream(
        self, messages: Sequence[ChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[AgentEvent | ChatMessage | Response, None]:
        try:
            # Convert messages to the format expected by LiteLLM
            llm_messages = []
            for msg in messages:
                if isinstance(msg, TextMessage):
                    llm_messages.append({"role": "user", "content": msg.content})
                elif isinstance(msg, BaseChatMessage):
                    llm_messages.append({"role": "assistant", "content": msg.content})

            # Prepare model parameters
            model_params = {
                "model": self.model_name,
                "messages": llm_messages,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "aws_region_name": self.aws_region_name,
                "aws_access_key_id": self.aws_access_key_id,
                "aws_secret_access_key": self.aws_secret_access_key,
                "stream": True,
            }

            # Add optional parameters if they are set
            if self.top_p is not None:
                model_params["top_p"] = self.top_p
            if self.top_k is not None:
                model_params["top_k"] = self.top_k
            if self.stop_sequences:
                model_params["stop"] = self.stop_sequences

            # Generate response
            response = completion(**model_params)
            content = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    content += chunk_content
                    yield ModelClientStreamingChunkEvent(content=chunk_content)

            # Create final response
            text_message = TextMessage(content=content, source=self.name)
            yield Response(chat_message=text_message)

        except Exception as e:
            raise RuntimeError(f"Error generating response from Bedrock: {str(e)}")

    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        await self._model_context.reset()

    async def save_state(self) -> Mapping[str, Any]:
        model_context_state = await self._model_context.save_state()
        state = BedrockAgentState(model_context_state=model_context_state)
        return state.model_dump()

    async def load_state(self, state: Mapping[str, Any]) -> None:
        bedrock_agent_state = BedrockAgentState.model_validate(state)
        await self._model_context.load_state(bedrock_agent_state.model_context_state)

    def _to_config(self) -> BedrockAgentConfig:
        return BedrockAgentConfig(
            name=self.name,
            model_name=self.model_name.replace("bedrock/", ""),
            aws_region_name=self.aws_region_name,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            top_k=self.top_k,
            stop_sequences=self.stop_sequences,
            model_context=self._model_context.dump_component(),
            description=self.description,
        )

    @classmethod
    def _from_config(cls, config: BedrockAgentConfig) -> "BedrockAgent":
        model_context = (
            ChatCompletionContext.load_component(config.model_context)
            if config.model_context is not None
            else UnboundedChatCompletionContext()
        )
        return cls(
            name=config.name,
            model_name=config.model_name,
            aws_region_name=config.aws_region_name,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p,
            top_k=config.top_k,
            stop_sequences=config.stop_sequences,
            model_context=model_context,
            description=config.description or cls.DEFAULT_DESCRIPTION,
        ) 