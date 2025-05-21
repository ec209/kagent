# Using AWS Bedrock with Kagent

This guide explains how to set up and use AWS Bedrock models with Kagent.

## Prerequisites

Before you begin, make sure you have:

1. An AWS account with access to AWS Bedrock service
2. Appropriate IAM permissions to use Bedrock models
3. AWS Access Key ID and Secret Access Key with Bedrock permissions
4. Kagent installed and configured

## Supported Models

AWS Bedrock provides access to various foundation models from different providers:

- **Anthropic Claude** (claude-3-opus, claude-3-sonnet, claude-3-haiku)
- **Amazon Titan** (text and multimodal models)
- **Meta Llama 2** (various sizes)
- **AI21 Labs Jurassic** models
- **Cohere Command** models
- And more

For a complete list of model IDs, refer to the [AWS Bedrock model IDs documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html).

## Creating a Bedrock Model Config

### Using the UI

1. Navigate to the Models section in the Kagent UI
2. Click "New Model"
3. Fill in the required fields:
   - **Name**: A unique name for your model configuration
   - **Provider**: Select "AWS Bedrock"
   - **Model**: Enter the Bedrock model ID (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)
   - **API Key**: Your AWS Access Key ID
   - **Secret Key**: Your AWS Secret Access Key
4. Complete the additional parameters:
   - **Region**: The AWS region where Bedrock is available (e.g., `us-west-2`)
   - **Max Tokens**: Maximum output tokens (e.g., 2048)
   - **Temperature**: Control randomness (0.0-1.0)
   - **Top P**: Nucleus sampling value (0.0-1.0)
5. Click "Create" to save the model configuration

### Using YAML

```yaml
apiVersion: kagent.dev/v1alpha1
kind: ModelConfig
metadata:
  name: bedrock-claude-sonnet
  namespace: default
spec:
  apiKeySecretKey: apikey
  apiKeySecretRef: aws-api-key-secret
  model: anthropic.claude-3-sonnet-20240229-v1:0
  bedrock:
    region: us-west-2
    maxTokens: 2048
    temperature: "0.7"
    topP: "0.95"
    topK: 50
    stopSequences:
      - "\n\nHuman:"
  provider: Bedrock
```

## Creating an Agent with Bedrock Model

Once you've created a model configuration, you can create an agent that uses Bedrock:

```yaml
apiVersion: kagent.dev/v1alpha1
kind: Agent
metadata:
  name: bedrock-agent
  namespace: default
spec:
  description: "AI agent using AWS Bedrock Claude"
  displayName: "Bedrock Claude Agent"
  modelConfigRef: bedrock-claude-sonnet
  systemMessage: |
    You are a helpful AI assistant powered by AWS Bedrock Claude model.
    You are knowledgeable, accurate, and friendly.
    When you don't know something, you admit it rather than making up information.
```

## Using Bedrock with the Python Client

You can also use AWS Bedrock models with the Python client:

```python
import os
import autogen
from autogen_ext.models.bedrock import BedrockChatCompletionClient

# Set your AWS credentials
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "your-access-key-id")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "your-secret-access-key")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

# Initialize the Bedrock client
config = {
    "api_key": AWS_ACCESS_KEY_ID,  # Access Key ID
    "secret_key": AWS_SECRET_ACCESS_KEY,  # Secret Access Key
    "region": AWS_REGION,  # AWS Region
    "model": "anthropic.claude-3-sonnet-20240229-v1:0",  # Model ID
    "max_tokens": 1000,
    "temperature": 0.7,
    "top_p": 0.9,
}

# Create the client
bedrock_client = BedrockChatCompletionClient(**config)

# Create an assistant using the Bedrock client
assistant = autogen.AssistantAgent(
    name="bedrock_assistant",
    llm_config={"config_list": [config], "client": bedrock_client},
    system_message="You are a helpful AI assistant powered by Claude on AWS Bedrock.",
)

# Create a user proxy
user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="TERMINATE",
    max_consecutive_auto_reply=0,
)

# Start the conversation
user_proxy.initiate_chat(
    assistant, 
    message="Tell me about AWS Bedrock and its capabilities for AI applications."
)
```

## Tips for Using AWS Bedrock

1. **Region Selection**: Make sure to select a region where AWS Bedrock is available
2. **IAM Permissions**: Ensure your IAM user/role has appropriate permissions to invoke Bedrock models
3. **Cost Management**: Be aware of the costs associated with different Bedrock models
4. **Model Selection**: Different models have different capabilities and costs; choose based on your needs
5. **Secret Management**: Store your AWS credentials securely using Kubernetes secrets

## Troubleshooting

Common issues and solutions:

- **Authentication Errors**: Verify your AWS Access Key ID and Secret Access Key are correct
- **Permission Errors**: Check IAM permissions for Bedrock model access
- **Region Errors**: Ensure you're using a region where Bedrock and the specific model are available
- **Quota Limits**: AWS may have quota limits on Bedrock model usage 