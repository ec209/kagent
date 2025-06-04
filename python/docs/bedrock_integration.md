# AWS Bedrock Integration

This document describes how to use AWS Bedrock models with kagent.

## Prerequisites

1. AWS Account with Bedrock access
2. AWS credentials configured (either through environment variables or AWS CLI configuration)
3. Required Python packages installed:
   ```bash
   pip install litellm boto3 python-dotenv
   ```

## Environment Variables

Set the following environment variables in your `.env` file or system environment:

```bash
AWS_REGION_NAME=your-aws-region
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
```

## Usage

### Basic Usage

```python
from kagent.agents.bedrock_agent import BedrockAgent

# Initialize the agent
agent = BedrockAgent(
    model_name="anthropic.claude-3-sonnet-20240229-v1:0",
    temperature=0.7,
)

# Generate a response
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "What is AWS Bedrock?"},
]

response = agent.generate_response(messages)
print(response)
```

### Streaming Responses

```python
# Stream the response
for chunk in agent.stream_response(messages):
    print(chunk, end="", flush=True)
```

### Available Models

The following Bedrock models are supported:

- Anthropic Claude 3 Sonnet: `anthropic.claude-3-sonnet-20240229-v1:0`
- Anthropic Claude 3 Haiku: `anthropic.claude-3-haiku-20240307-v1:0`
- Anthropic Claude 2.1: `anthropic.claude-v2:1`
- Amazon Titan: `amazon.titan-text-express-v1`
- Cohere Command: `cohere.command-text-v14`
- Meta Llama 2: `meta.llama2-13b-chat-v1`
- Mistral: `mistral.mistral-7b-instruct-v0:2`

## Error Handling

The Bedrock agent includes error handling for common issues:

- Missing AWS credentials
- Invalid model names
- API errors

Example error handling:

```python
try:
    response = agent.generate_response(messages)
except ValueError as e:
    print(f"Configuration error: {e}")
except RuntimeError as e:
    print(f"API error: {e}")
```

## Advanced Configuration

You can configure additional parameters when initializing the agent:

```python
agent = BedrockAgent(
    model_name="anthropic.claude-3-sonnet-20240229-v1:0",
    aws_region_name="us-west-2",  # Optional: override region
    aws_access_key_id="your-key",  # Optional: override access key
    aws_secret_access_key="your-secret",  # Optional: override secret key
    temperature=0.7,
    max_tokens=1000,
)
```

## Example

See the complete example in `examples/bedrock_example.py` for a working implementation. 