# Enhanced Bedrock Provider Implementation

## Overview

This document describes the enhanced AWS Bedrock provider implementation that addresses the key user experience improvements:

1. **Separate Bedrock Provider Category** - Users see "AWS Bedrock" as a distinct provider
2. **Complete AWS Credential Configuration** - Expose Access Key, Secret Key, and Region fields
3. **Transparent LiteLLM Integration** - Backend automatically handles OpenAI-to-LiteLLM translation
4. **Per-Model AWS Credentials** - Different models can use different AWS accounts/regions

## Architecture

```
User (Bedrock Provider) → Backend Translation → LiteLLM Proxy → AWS Bedrock
```

### User Experience
- **Provider Selection**: Users select "AWS Bedrock" from provider dropdown
- **AWS Configuration**: Direct input of Access Key, Secret Key, Region per model
- **Model Selection**: Choose from available Bedrock models (Claude, Titan, Llama)
- **Transparent Operation**: No knowledge of LiteLLM proxy required

### Backend Implementation
- **Automatic Translation**: Bedrock configs automatically converted to LiteLLM proxy calls
- **Secret Management**: AWS credentials stored securely in Kubernetes secrets
- **Dual Configuration**: Both Bedrock and OpenAI configs stored for seamless operation

## Implementation Details

### 1. Enhanced BedrockConfig Structure

```go
type BedrockConfig struct {
    // AWS Region for Bedrock
    // +required
    Region string `json:"region,omitempty"`

    // AWS Access Key ID for authentication
    // +optional
    AccessKey string `json:"accessKey,omitempty"`

    // AWS Secret Key for authentication
    // +optional
    SecretKey string `json:"secretKey,omitempty"`

    // Model ID for specific Bedrock model
    // +optional
    ModelID string `json:"modelId,omitempty"`

    // Additional Bedrock-specific parameters...
}
```

### 2. Backend Translation Logic

When a user creates a Bedrock model configuration:

```go
case v1alpha1.Bedrock:
    if req.BedrockParams != nil {
        // Validate required Bedrock parameters
        if req.BedrockParams.Region == "" {
            return fmt.Errorf("missing required Bedrock parameter: region")
        }
        
        // Store Bedrock config as-is for user visibility
        modelConfig.Spec.Bedrock = req.BedrockParams
        
        // Add LiteLLM proxy configuration for internal use
        modelConfig.Spec.OpenAI = &v1alpha1.OpenAIConfig{
            BaseURL: "http://localhost:4000/v1",
        }
    }
```

### 3. Enhanced Secret Management

For Bedrock providers, secrets contain both LiteLLM proxy credentials and AWS credentials:

```go
if providerTypeEnum == v1alpha1.Bedrock {
    secretData["BEDROCK_API_KEY"] = "sk-1234" // LiteLLM proxy key
    if req.BedrockParams != nil {
        if req.BedrockParams.AccessKey != "" {
            secretData["AWS_ACCESS_KEY_ID"] = req.BedrockParams.AccessKey
        }
        if req.BedrockParams.SecretKey != "" {
            secretData["AWS_SECRET_ACCESS_KEY"] = req.BedrockParams.SecretKey
        }
        if req.BedrockParams.Region != "" {
            secretData["AWS_DEFAULT_REGION"] = req.BedrockParams.Region
        }
    }
}
```

## User Configuration Guide

### Creating a Bedrock Model

1. **Navigate to Models** in the kagent UI
2. **Click "New Model"**
3. **Configure Bedrock Provider**:
   - **Provider**: Select "AWS Bedrock"
   - **Model**: Choose from available Bedrock models:
     - `anthropic.claude-3-sonnet-20240229-v1:0`
     - `anthropic.claude-3-haiku-20240307-v1:0`
     - `amazon.titan-text-express-v1`
     - `meta.llama2-13b-chat-v1`
   - **AWS Access Key**: Your AWS Access Key ID
   - **AWS Secret Key**: Your AWS Secret Access Key
   - **Region**: AWS region (e.g., `us-west-2`)
4. **Configure Model Parameters** (optional):
   - Max Tokens, Temperature, Top-P, Top-K
5. **Click "Create"**

### Per-Model AWS Credentials

Each Bedrock model can have different AWS credentials:

```yaml
# Model 1: Production account
apiVersion: kagent.dev/v1alpha1
kind: ModelConfig
metadata:
  name: claude-prod
spec:
  provider: Bedrock
  model: anthropic.claude-3-sonnet-20240229-v1:0
  bedrock:
    region: us-east-1
    accessKey: AKIA...PROD
    secretKey: secret...prod

---
# Model 2: Development account  
apiVersion: kagent.dev/v1alpha1
kind: ModelConfig
metadata:
  name: claude-dev
spec:
  provider: Bedrock
  model: anthropic.claude-3-haiku-20240307-v1:0
  bedrock:
    region: us-west-2
    accessKey: AKIA...DEV
    secretKey: secret...dev
```

## Available Bedrock Models

| Model | Function Calling | Use Case |
|-------|------------------|----------|
| `anthropic.claude-3-sonnet-20240229-v1:0` | ✅ | General purpose, balanced performance |
| `anthropic.claude-3-haiku-20240307-v1:0` | ✅ | Fast responses, cost-effective |
| `anthropic.claude-3-opus-20240229-v1:0` | ✅ | Most capable, complex reasoning |
| `amazon.titan-text-express-v1` | ❌ | Amazon's general purpose model |
| `amazon.titan-text-lite-v1` | ❌ | Lightweight, fast responses |
| `meta.llama2-13b-chat-v1` | ❌ | Open source alternative |

## Benefits

### 1. **Improved User Experience**
- Clear provider categorization
- Direct AWS credential configuration
- No technical implementation details exposed

### 2. **Flexible Credential Management**
- Per-model AWS accounts
- Different regions per model
- Secure secret storage

### 3. **Transparent Backend Operation**
- Automatic LiteLLM proxy integration
- No user configuration of proxy details
- Seamless OpenAI-compatible API usage

### 4. **Maintainable Architecture**
- Clean separation of concerns
- Standard AutoGen integration patterns
- Easy to add new Bedrock models

## Migration from OpenAI Provider Workaround

If you previously configured Bedrock models using the OpenAI provider workaround:

### Old Configuration (OpenAI Provider)
```yaml
provider: OpenAI
baseUrl: http://localhost:4000/v1
apiKey: sk-1234
model: anthropic.claude-3-sonnet-20240229-v1:0
```

### New Configuration (Bedrock Provider)
```yaml
provider: Bedrock
model: anthropic.claude-3-sonnet-20240229-v1:0
bedrock:
  region: us-west-2
  accessKey: AKIA...
  secretKey: secret...
```

The backend automatically handles the LiteLLM proxy integration, so users no longer need to know about the technical implementation details.

## Troubleshooting

### Common Issues

1. **"Missing required Bedrock parameter: region"**
   - Ensure the Region field is filled in the UI

2. **AWS Authentication Errors**
   - Verify Access Key and Secret Key are correct
   - Check that the AWS account has Bedrock access permissions
   - Ensure the region supports the requested Bedrock models

3. **Model Not Available**
   - Verify the model is available in your AWS region
   - Check that your AWS account has access to the specific model

### Verification Steps

1. **Check Model Configuration**:
   ```bash
   kubectl get modelconfig -n kagent
   kubectl describe modelconfig <model-name> -n kagent
   ```

2. **Verify Secret Creation**:
   ```bash
   kubectl get secret <model-name> -n kagent -o yaml
   ```

3. **Test LiteLLM Proxy**:
   ```bash
   curl -X POST http://localhost:4000/v1/chat/completions \
     -H "Authorization: Bearer sk-1234" \
     -H "Content-Type: application/json" \
     -d '{"model": "anthropic.claude-3-sonnet-20240229-v1:0", "messages": [{"role": "user", "content": "Hello"}]}'
   ```

## Future Enhancements

1. **AWS IAM Role Support**: Integration with AWS IAM roles for service accounts
2. **Model Discovery**: Automatic discovery of available Bedrock models per region
3. **Cost Monitoring**: Integration with AWS cost tracking
4. **Model Versioning**: Support for model version management
5. **Regional Failover**: Automatic failover to different regions

This enhanced implementation provides a much better user experience while maintaining the robust LiteLLM proxy integration under the hood. 