# Kagent Slack Bot Integration

This Slack bot integrates with kagent to provide AI-powered Kubernetes assistance directly in your Slack workspace.

## Features

- 🤖 **Direct Slack Integration**: Ask questions about your Kubernetes cluster directly in Slack
- 🔧 **Uses kagent CLI**: Leverages the existing kagent CLI for consistent behavior
- 🎯 **Smart Responses**: Automatically formats kubectl output and responses for Slack
- 👥 **Multi-User Support**: Each Slack user gets their own kagent session
- 🔒 **Secure**: Uses Slack's Socket Mode for secure real-time communication

## Setup

### 1. Create Slack App

1. Go to [Slack API](https://api.slack.com/apps) and create a new app
2. Choose "From scratch" and select your workspace
3. Go to **OAuth & Permissions** and add these Bot Token Scopes:
   - `app_mentions:read`
   - `chat:write`
   - `im:read`
   - `im:write`
4. Install the app to your workspace and copy the **Bot User OAuth Token**

### 2. Enable Socket Mode

1. Go to **Socket Mode** in your Slack app settings
2. Enable Socket Mode and create an App-Level Token with `connections:write` scope
3. Copy the **App-Level Token**

### 3. Get Signing Secret

1. Go to **Basic Information** in your Slack app settings
2. Copy the **Signing Secret**

### 4. Deploy with Helm

```bash
# Build and load the Slack bot image
make build-slack-bot
make minikube-load-images

# Deploy with Slack integration enabled
helm upgrade kagent ./helm/kagent -n kagent \
  --set slackBot.enabled=true \
  --set slackBot.botToken="xoxb-your-bot-token" \
  --set slackBot.signingSecret="your-signing-secret" \
  --set slackBot.appToken="xapp-your-app-token"
```

## Usage

### In Slack Channels
Mention the bot with your question:
```
@kagent What pods are running in the kagent namespace?
```

### In Direct Messages
Just ask your question directly:
```
Show me all services in the default namespace
```

### Example Questions
- "What pods are running in the kagent namespace?"
- "Show me the logs for the kagent pod"
- "List all services in the default namespace"
- "What's the status of the kagent deployment?"
- "Help me troubleshoot why my pod is not starting"

## Architecture

```
Slack → Slack Bot Container → kagent CLI → kagent API → AI Agents → Kubernetes
```

The Slack bot:
1. Receives messages from Slack via Socket Mode
2. Spawns the kagent CLI with the user's question
3. Processes and formats the response for Slack
4. Updates the message with the AI agent's response

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token | Required |
| `SLACK_SIGNING_SECRET` | Slack app signing secret | Required |
| `SLACK_APP_TOKEN` | App-Level Token for Socket Mode | Required |
| `KAGENT_API_URL` | kagent API endpoint | `http://localhost:8081` |
| `KAGENT_CLI_PATH` | Path to kagent CLI binary | `/usr/local/bin/kagent` |
| `PORT` | Port for health checks | `3000` |

### Helm Values

```yaml
slackBot:
  enabled: true
  image:
    registry: cr.kagent.dev
    repository: kagent-dev/kagent/slack-bot
    tag: "latest"
  secretName: "kagent-slack"
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 200m
      memory: 256Mi
  # Slack credentials (alternatively use existing secret)
  botToken: "xoxb-your-bot-token"
  signingSecret: "your-signing-secret"
  appToken: "xapp-your-app-token"
```

## Deployment Options

### Option 1: Integrated Container (Recommended)
Deploy as a sidecar container in the kagent pod (current implementation):
- ✅ Shares the same network namespace
- ✅ Easy to manage and deploy
- ✅ Consistent with kagent architecture

### Option 2: Separate Deployment
Deploy as a separate Kubernetes deployment:
- ✅ Independent scaling
- ✅ Separate resource management
- ❌ More complex networking setup

### Option 3: External Service
Deploy outside Kubernetes (e.g., on a VM or serverless):
- ✅ Independent of Kubernetes cluster
- ❌ Requires external network access to kagent
- ❌ More complex setup

## Troubleshooting

### Check Slack Bot Logs
```bash
kubectl logs -n kagent deployment/kagent -c slack-bot -f
```

### Test Health Endpoint
```bash
kubectl port-forward -n kagent svc/kagent 3000:3000
curl http://localhost:3000/health
```

### Verify kagent CLI Access
```bash
kubectl exec -n kagent deployment/kagent -c slack-bot -- kagent --help
```

### Common Issues

1. **Bot not responding**: Check if Socket Mode is enabled and App-Level Token is correct
2. **Permission errors**: Ensure bot has required OAuth scopes
3. **kagent CLI errors**: Check if kagent API is accessible and credentials are configured
4. **Timeout errors**: Increase timeout or check if AI models are responding

## Security Considerations

- Store Slack tokens in Kubernetes secrets
- Use least-privilege OAuth scopes
- Consider network policies to restrict access
- Monitor bot usage and responses
- Regularly rotate Slack tokens 