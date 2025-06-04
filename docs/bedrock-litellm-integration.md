# AWS Bedrock Integration via LiteLLM

This document explains how to use AWS Bedrock models with Kagent using the recommended LiteLLM proxy approach.

## Overview

Instead of direct Bedrock integration, Kagent uses [LiteLLM](https://docs.litellm.ai/) as a proxy to provide OpenAI-compatible API access to Bedrock models. This approach follows the [AutoGen recommended pattern](https://microsoft.github.io/autogen/0.2/docs/topics/non-openai-models/local-litellm-ollama/) for non-OpenAI models.

## Architecture

```
Kagent/AutoGen → LiteLLM Proxy → AWS Bedrock
```

1. **LiteLLM Proxy** runs on port 4000 and handles Bedrock authentication and API translation
2. **Kagent Engine** runs on port 8081 and connects to LiteLLM proxy as if it were OpenAI
3. **AWS Bedrock** provides the actual model inference

## Configuration

### 1. AWS Credentials

Set your AWS credentials as environment variables:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-west-2  # or your preferred region
```

### 2. Model Configuration in Kagent UI

When creating a model configuration in the Kagent UI:

1. **Provider**: Select "OpenAI" (since LiteLLM provides OpenAI-compatible API)
2. **Base URL**: `http://localhost:4000` (LiteLLM proxy endpoint)
3. **API Key**: `sk-1234` (dummy key, as configured in LiteLLM)
4. **Model**: Use the Bedrock model ID (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)

### 3. Available Models

The following Bedrock models are available via LiteLLM proxy:

#### Anthropic Claude Models
- `anthropic.claude-3-sonnet-20240229-v1:0` (Function calling: ✅)
- `anthropic.claude-3-haiku-20240307-v1:0` (Function calling: ✅)
- `anthropic.claude-3-opus-20240229-v1:0` (Function calling: ✅)

#### Amazon Titan Models
- `amazon.titan-text-express-v1` (Function calling: ❌)
- `amazon.titan-text-lite-v1` (Function calling: ❌)

#### Meta Llama Models
- `meta.llama2-13b-chat-v1` (Function calling: ❌)
- `meta.llama2-70b-chat-v1` (Function calling: ❌)

## Example Model Configuration YAML

```yaml
apiVersion: kagent.dev/v1alpha1
kind: ModelConfig
metadata:
  name: bedrock-claude-sonnet
  namespace: default
spec:
  provider: OpenAI  # LiteLLM provides OpenAI-compatible API
  model: anthropic.claude-3-sonnet-20240229-v1:0
  baseUrl: http://localhost:4000
  apiKey: sk-1234  # Dummy key as configured in LiteLLM
  maxTokens: 2048
  temperature: 0.7
```

## Troubleshooting

### 1. Check LiteLLM Proxy Status

```bash
curl http://localhost:4000/health
```

### 2. List Available Models

```bash
curl http://localhost:4000/v1/models
```

### 3. Test Model Access

```bash
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-1234" \
  -d '{
    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 4. Common Issues

- **Authentication Errors**: Verify AWS credentials are set correctly
- **Region Errors**: Ensure the AWS region supports the requested Bedrock models
- **Model Access**: Verify your AWS account has access to the specific Bedrock models
- **Proxy Connection**: Check that LiteLLM proxy is running on port 4000

## Benefits of LiteLLM Approach

1. **Standard Integration**: Uses the recommended AutoGen pattern for non-OpenAI models
2. **OpenAI Compatibility**: No need for custom client implementations
3. **Easy Configuration**: Standard model configuration in Kagent UI
4. **Robust Error Handling**: LiteLLM handles Bedrock-specific error cases
5. **Future-Proof**: Easy to add new Bedrock models as they become available

## References

- [AutoGen Non-OpenAI Models Guide](https://microsoft.github.io/autogen/0.2/docs/topics/non-openai-models/local-litellm-ollama/)
- [LiteLLM Bedrock Provider Documentation](https://docs.litellm.ai/docs/providers/bedrock)
- [AWS Bedrock Model IDs](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html) 