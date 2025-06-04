#!/bin/bash

# Start LiteLLM proxy in the background for Bedrock integration
echo "Starting LiteLLM proxy for Bedrock integration..."
uv run litellm --config /app/python/litellm_config.yaml --port 4000 --host 0.0.0.0 &

# Wait a moment for LiteLLM to start
sleep 5

# Test LiteLLM proxy connectivity
echo "Testing LiteLLM proxy connectivity..."
curl -s http://localhost:4000/v1/models -H "Authorization: Bearer sk-1234" | head -c 100
echo ""

# Start the main kagent engine
echo "Starting kagent engine..."
exec uv run kagent-engine serve --host 0.0.0.0 --port 8081