#!/usr/bin/env python3
"""
Example of using AWS Bedrock models with Kagent client.
This demonstrates how to connect to AWS Bedrock and use Claude or other models.

Prerequisites:
- AWS account with Bedrock access
- AWS Access Key ID and Secret Access Key with Bedrock permissions
- Install requirements: pip install autogen-ext boto3
"""

import os
import autogen
from autogen_ext.models.bedrock import BedrockChatCompletionClient

# Set your AWS credentials
# You can also use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "your-access-key-id")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "your-secret-access-key")
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")

# Initialize the Bedrock client
# Available models: 
# - anthropic.claude-3-sonnet-20240229-v1:0
# - anthropic.claude-3-haiku-20240307-v1:0
# - anthropic.claude-3-opus-20240229-v1:0
# - amazon.titan-text-express-v1
# - meta.llama2-13b-chat-v1
# See: https://docs.aws.amazon.com/bedrock/latest/userguide/model-ids.html
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

# Example with a follow-up question
user_proxy.send(
    "Can you explain how AWS Bedrock compares to other AI providers like OpenAI or Anthropic direct?"
) 