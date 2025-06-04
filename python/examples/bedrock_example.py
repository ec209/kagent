"""Example usage of the Bedrock agent."""

import os
from dotenv import load_dotenv

from kagent.agents.bedrock_agent import BedrockAgent

def main():
    # Load environment variables from .env file
    load_dotenv()

    # Initialize the Bedrock agent
    agent = BedrockAgent(
        model_name="anthropic.claude-3-sonnet-20240229-v1:0",
        temperature=0.7,
    )

    # Example conversation
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "What is AWS Bedrock?"},
    ]

    # Generate a response
    response = agent.generate_response(messages)
    print("Response:", response)

    # Example of streaming response
    print("\nStreaming response:")
    for chunk in agent.stream_response(messages):
        print(chunk, end="", flush=True)

if __name__ == "__main__":
    main() 