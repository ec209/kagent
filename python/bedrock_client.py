#!/usr/bin/env python3
"""
Bedrock client using LiteLLM SDK for multi-tenant support.
This script handles Bedrock model invocation with per-request AWS credentials.
"""

import json
import sys
import os
from typing import Dict, List, Any, Optional
import argparse

try:
    import litellm
    from litellm import completion
except ImportError:
    print(json.dumps({"error": "litellm package not installed"}))
    sys.exit(1)


def invoke_bedrock_model(
    model: str,
    messages: List[Dict[str, str]],
    aws_access_key_id: str,
    aws_secret_access_key: str,
    aws_region_name: str,
    aws_session_token: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    stop_sequences: Optional[List[str]] = None,
    system_prompt: Optional[str] = None,
    stream: bool = False,
) -> Dict[str, Any]:
    """
    Invoke a Bedrock model using LiteLLM SDK with per-request credentials.
    
    Args:
        model: Bedrock model ID (e.g., "anthropic.claude-3-sonnet-20240229-v1:0")
        messages: List of message dicts with 'role' and 'content'
        aws_access_key_id: AWS access key ID for this request
        aws_secret_access_key: AWS secret access key for this request
        aws_region_name: AWS region name
        aws_session_token: Optional AWS session token
        max_tokens: Maximum tokens to generate
        temperature: Temperature for generation
        top_p: Top-p for generation
        stop_sequences: Stop sequences
        system_prompt: System prompt
        stream: Whether to stream response
    
    Returns:
        Dict containing the response or error
    """
    try:
        # Prepare the model name for LiteLLM (prefix with bedrock/)
        if not model.startswith("bedrock/"):
            litellm_model = f"bedrock/{model}"
        else:
            litellm_model = model
        
        # Prepare messages
        formatted_messages = []
        
        # Add system message if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        
        # Add user messages
        formatted_messages.extend(messages)
        
        # Prepare completion parameters
        completion_params = {
            "model": litellm_model,
            "messages": formatted_messages,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "aws_region_name": aws_region_name,
            "stream": stream,
        }
        
        # Add optional parameters
        if aws_session_token:
            completion_params["aws_session_token"] = aws_session_token
        if max_tokens:
            completion_params["max_tokens"] = max_tokens
        if temperature is not None:
            completion_params["temperature"] = temperature
        if top_p is not None:
            completion_params["top_p"] = top_p
        if stop_sequences:
            completion_params["stop"] = stop_sequences
        
        # Make the completion call
        response = completion(**completion_params)
        
        if stream:
            # For streaming, we'll need to handle this differently
            # For now, just return the first chunk
            try:
                first_chunk = next(response)
                return {
                    "success": True,
                    "response": {
                        "id": first_chunk.id,
                        "object": first_chunk.object,
                        "created": first_chunk.created,
                        "model": first_chunk.model,
                        "choices": [
                            {
                                "index": choice.index,
                                "delta": {
                                    "role": choice.delta.role,
                                    "content": choice.delta.content,
                                },
                                "finish_reason": choice.finish_reason,
                            }
                            for choice in first_chunk.choices
                        ],
                    },
                    "streaming": True,
                }
            except StopIteration:
                return {"success": False, "error": "No response from streaming"}
        else:
            # Non-streaming response
            return {
                "success": True,
                "response": {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "index": choice.index,
                            "message": {
                                "role": choice.message.role,
                                "content": choice.message.content,
                            },
                            "finish_reason": choice.finish_reason,
                        }
                        for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    } if response.usage else None,
                },
                "streaming": False,
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def main():
    """Main function to handle command line invocation."""
    parser = argparse.ArgumentParser(description="Invoke Bedrock model using LiteLLM")
    parser.add_argument("--model", required=True, help="Bedrock model ID")
    parser.add_argument("--messages", required=True, help="JSON string of messages")
    parser.add_argument("--aws-access-key-id", required=True, help="AWS access key ID")
    parser.add_argument("--aws-secret-access-key", required=True, help="AWS secret access key")
    parser.add_argument("--aws-region-name", required=True, help="AWS region name")
    parser.add_argument("--aws-session-token", help="AWS session token")
    parser.add_argument("--max-tokens", type=int, help="Maximum tokens")
    parser.add_argument("--temperature", type=float, help="Temperature")
    parser.add_argument("--top-p", type=float, help="Top-p")
    parser.add_argument("--stop-sequences", help="JSON array of stop sequences")
    parser.add_argument("--system-prompt", help="System prompt")
    parser.add_argument("--stream", action="store_true", help="Stream response")
    
    args = parser.parse_args()
    
    try:
        # Parse JSON arguments
        messages = json.loads(args.messages)
        stop_sequences = json.loads(args.stop_sequences) if args.stop_sequences else None
        
        # Invoke the model
        result = invoke_bedrock_model(
            model=args.model,
            messages=messages,
            aws_access_key_id=args.aws_access_key_id,
            aws_secret_access_key=args.aws_secret_access_key,
            aws_region_name=args.aws_region_name,
            aws_session_token=args.aws_session_token,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            stop_sequences=stop_sequences,
            system_prompt=args.system_prompt,
            stream=args.stream,
        )
        
        # Output the result
        print(json.dumps(result))
        
    except json.JSONDecodeError as e:
        error_result = {
            "success": False,
            "error": f"JSON parsing error: {str(e)}",
            "error_type": "JSONDecodeError",
        }
        print(json.dumps(error_result))
        sys.exit(1)
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        print(json.dumps(error_result))
        sys.exit(1)


if __name__ == "__main__":
    main() 