package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/kagent-dev/kagent/go/autogen/client"
	"github.com/kagent-dev/kagent/go/controller/internal/httpserver/errors"
	ctrllog "sigs.k8s.io/controller-runtime/pkg/log"
)

// ModelHandler handles model requests
type ModelHandler struct {
	*Base
}

// NewModelHandler creates a new ModelHandler
func NewModelHandler(base *Base) *ModelHandler {
	return &ModelHandler{Base: base}
}

// LiteLLMModel represents a model from LiteLLM proxy
type LiteLLMModel struct {
	ID     string `json:"id"`
	Object string `json:"object"`
}

// LiteLLMResponse represents the response from LiteLLM proxy /v1/models endpoint
type LiteLLMResponse struct {
	Data   []LiteLLMModel `json:"data"`
	Object string         `json:"object"`
}

// queryLiteLLMModels queries the LiteLLM proxy for available Bedrock models
func (h *ModelHandler) queryLiteLLMModels() ([]client.ModelInfo, error) {
	// Create HTTP client with timeout
	httpClient := &http.Client{
		Timeout: 10 * time.Second,
	}

	// Query LiteLLM proxy
	req, err := http.NewRequest("GET", "http://localhost:4000/v1/models", nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Add authorization header
	req.Header.Set("Authorization", "Bearer sk-1234")
	req.Header.Set("Content-Type", "application/json")

	resp, err := httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to query LiteLLM proxy: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("LiteLLM proxy returned status %d", resp.StatusCode)
	}

	var liteLLMResp LiteLLMResponse
	if err := json.NewDecoder(resp.Body).Decode(&liteLLMResp); err != nil {
		return nil, fmt.Errorf("failed to decode LiteLLM response: %w", err)
	}

	// Convert LiteLLM models to ModelInfo format
	var models []client.ModelInfo
	for _, model := range liteLLMResp.Data {
		// Determine function calling capability based on model name
		functionCalling := h.supportsFunctionCalling(model.ID)

		models = append(models, client.ModelInfo{
			Name:            model.ID,
			FunctionCalling: functionCalling,
		})
	}

	return models, nil
}

// supportsFunctionCalling determines if a model supports function calling based on its name
func (h *ModelHandler) supportsFunctionCalling(modelName string) bool {
	// Claude models (Anthropic) support function calling
	if len(modelName) >= 6 && modelName[:6] == "claude" {
		return true
	}
	// Titan models (Amazon) don't support function calling
	if len(modelName) >= 5 && modelName[:5] == "titan" {
		return false
	}
	// Llama models (Meta) - check for specific versions that support function calling
	if len(modelName) >= 5 && modelName[:5] == "llama" {
		// Llama 2 70B and newer versions support function calling
		if strings.Contains(modelName, "70b") || strings.Contains(modelName, "llama-3") {
			return true
		}
		return false
	}
	// Mistral models support function calling
	if len(modelName) >= 7 && modelName[:7] == "mistral" {
		return true
	}
	// Cohere models support function calling
	if len(modelName) >= 6 && modelName[:6] == "cohere" {
		return true
	}
	// Default to false for unknown models to be conservative
	return false
}

func (h *ModelHandler) HandleListSupportedModels(w ErrorResponseWriter, r *http.Request) {
	log := ctrllog.FromContext(r.Context()).WithName("model-handler").WithValues("operation", "list-supported-models")

	log.Info("Listing supported models")

	// Get models from AutoGen Studio
	autogenModels, err := h.AutogenClient.ListSupportedModels()
	if err != nil {
		log.Error(err, "Failed to list AutoGen Studio models")
		w.RespondWithError(errors.NewInternalServerError("Failed to list supported models", err))
		return
	}

	// Start with AutoGen Studio models
	allModels := *autogenModels

	// Try to get models from LiteLLM proxy (don't fail if this doesn't work)
	liteLLMModels, err := h.queryLiteLLMModels()
	if err != nil {
		log.Info("Failed to query LiteLLM proxy, proceeding with AutoGen Studio models only", "error", err)
	} else {
		// Add LiteLLM models under "bedrock" provider section
		if len(liteLLMModels) > 0 {
			allModels["bedrock"] = liteLLMModels
			log.Info("Successfully added LiteLLM models under bedrock provider", "count", len(liteLLMModels))
		}
	}

	RespondWithJSON(w, http.StatusOK, allModels)
}
