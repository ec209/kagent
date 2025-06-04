"""Tests for the BedrockAgent."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autogen_agentchat.messages import TextMessage
from autogen_core import CancellationToken

from kagent.agents import BedrockAgent


@pytest.fixture
def mock_litellm():
    """Mock LiteLLM completion function."""
    with patch("litellm.completion") as mock:
        mock.return_value = [
            MagicMock(choices=[MagicMock(delta=MagicMock(content="Hello"))]),
            MagicMock(choices=[MagicMock(delta=MagicMock(content=" World"))]),
        ]
        yield mock


@pytest.fixture
def bedrock_agent():
    """Create a BedrockAgent instance for testing."""
    os.environ["AWS_REGION_NAME"] = "us-west-2"
    os.environ["AWS_ACCESS_KEY_ID"] = "test-key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test-secret"
    return BedrockAgent(name="test-agent")


@pytest.mark.asyncio
async def test_bedrock_agent_initialization():
    """Test BedrockAgent initialization."""
    agent = BedrockAgent(
        name="test-agent",
        model_name="anthropic.claude-3-sonnet-20240229-v1:0",
        temperature=0.5,
    )
    assert agent.name == "test-agent"
    assert agent.model_name == "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
    assert agent.temperature == 0.5


@pytest.mark.asyncio
async def test_bedrock_agent_missing_credentials():
    """Test BedrockAgent initialization with missing credentials."""
    with pytest.raises(ValueError, match="AWS credentials must be provided"):
        BedrockAgent(name="test-agent")


@pytest.mark.asyncio
async def test_bedrock_agent_generate_response(bedrock_agent, mock_litellm):
    """Test BedrockAgent response generation."""
    messages = [TextMessage(content="Hello", source="user")]
    cancellation_token = CancellationToken()

    response = await bedrock_agent.on_messages(messages, cancellation_token)
    assert response.chat_message.content == "Hello World"
    assert response.chat_message.source == "test-agent"


@pytest.mark.asyncio
async def test_bedrock_agent_stream_response(bedrock_agent, mock_litellm):
    """Test BedrockAgent streaming response."""
    messages = [TextMessage(content="Hello", source="user")]
    cancellation_token = CancellationToken()

    chunks = []
    async for event in bedrock_agent.on_messages_stream(messages, cancellation_token):
        if hasattr(event, "content"):
            chunks.append(event.content)

    assert chunks == ["Hello", " World"]


@pytest.mark.asyncio
async def test_bedrock_agent_state_management(bedrock_agent):
    """Test BedrockAgent state management."""
    # Save state
    state = await bedrock_agent.save_state()
    assert isinstance(state, dict)
    assert "model_context_state" in state

    # Load state
    await bedrock_agent.load_state(state)
    # No assertions needed as load_state doesn't return anything 