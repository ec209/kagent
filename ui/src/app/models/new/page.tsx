"use client";
import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { LoadingState } from "@/components/LoadingState";
import { ErrorState } from "@/components/ErrorState";
import { getModelConfig, createModelConfig, updateModelConfig } from "@/app/actions/modelConfigs";
import {
    CreateModelConfigPayload,
    UpdateModelConfigPayload,
    Provider,
    OpenAIConfigPayload,
    AzureOpenAIConfigPayload,
    AnthropicConfigPayload,
    OllamaConfigPayload
} from "@/lib/types";
import { toast } from "sonner";
import { isResourceNameValid } from "@/lib/utils";
import { getSupportedProviders } from "@/app/actions/providers";
import { getModels, ProviderModelsResponse } from "@/app/actions/models";
import { isValidProviderInfoKey, getProviderFormKey, ModelProviderKey, BackendModelProviderType } from "@/lib/providers";
import { BasicInfoSection } from '@/components/models/new/BasicInfoSection';
import { AuthSection } from '@/components/models/new/AuthSection';
import { ParamsSection } from '@/components/models/new/ParamsSection';

interface ValidationErrors {
  name?: string;
  selectedCombinedModel?: string;
  apiKey?: string;
  secretKey?: string;
  requiredParams?: Record<string, string>;
  optionalParams?: string;
}

interface ModelParam {
  id: string;
  key: string;
  value: string;
}

// Helper function to process parameters before submission

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const processModelParams = (requiredParams: ModelParam[], optionalParams: ModelParam[]): Record<string, any> => {
  const allParams = [...requiredParams, ...optionalParams]
    .filter(p => p.key.trim() !== "")
    .reduce((acc, param) => {
      acc[param.key.trim()] = param.value;
      return acc;
    }, {} as Record<string, string>);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const providerParams: Record<string, any> = {};
  const numericKeys = new Set([
    'max_tokens',
    'top_k',
    'seed',
    'n',
    'timeout',
    'temperature',
    'frequency_penalty',
    'presence_penalty'
  ]);

  const booleanKeys = new Set([
    'stream'
  ]);

  Object.entries(allParams).forEach(([key, value]) => {
    if (numericKeys.has(key)) {
      const numValue = parseFloat(value);
      if (!isNaN(numValue)) {
        providerParams[key] = numValue;
      } else {
        if (value.trim() !== '') {
          console.warn(`Invalid number for parameter '${key}': '${value}'. Treating as unset.`);
        }
      }
    } else if (booleanKeys.has(key)) {
      const lowerValue = value.toLowerCase().trim();
      if (lowerValue === 'true' || lowerValue === '1' || lowerValue === 'yes') {
        providerParams[key] = true;
      } else if (lowerValue === 'false' || lowerValue === '0' || lowerValue === 'no' || lowerValue === '') {
        providerParams[key] = false;
      } else {
        console.warn(`Invalid boolean for parameter '${key}': '${value}'. Treating as false.`);
        providerParams[key] = false;
      }
    } else {
      if (value.trim() !== '') {
        providerParams[key] = value;
      }
    }
  });

  return providerParams;
}

function ModelPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const isEditMode = searchParams.get("edit") === "true";
  const modelId = searchParams.get("id");

  const [name, setName] = useState("");
  const [isEditingName, setIsEditingName] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);
  const [showSecretKey, setShowSecretKey] = useState(false);
  const [requiredParams, setRequiredParams] = useState<ModelParam[]>([]);
  const [optionalParams, setOptionalParams] = useState<ModelParam[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerModelsData, setProviderModelsData] = useState<ProviderModelsResponse | null>(null);
  const [selectedCombinedModel, setSelectedCombinedModel] = useState<string | undefined>(undefined);
  const [selectedModelSupportsFunctionCalling, setSelectedModelSupportsFunctionCalling] = useState<boolean | null>(null);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingError, setLoadingError] = useState<string | null>(null);
  const [errors, setErrors] = useState<ValidationErrors>({});

  const isOllamaSelected = selectedProvider?.type === "Ollama";
  const isBedrockSelected = selectedProvider?.type === "Bedrock";

  useEffect(() => {
    let isMounted = true;
    const fetchData = async () => {
      setLoadingError(null);
      setIsLoading(true);
      try {
        const [providersResponse, modelsResponse] = await Promise.all([
          getSupportedProviders(),
          getModels()
        ]);

        if (!isMounted) return;

        if (providersResponse.success && providersResponse.data) {
          setProviders(providersResponse.data);
        } else {
          throw new Error(providersResponse.error || "Failed to fetch supported providers");
        }

        if (modelsResponse.success && modelsResponse.data) {
          setProviderModelsData(modelsResponse.data);
        } else {
          throw new Error(modelsResponse.error || "Failed to fetch available models");
        }
      } catch (err) {
        console.error("Error fetching initial data:", err);
        const message = err instanceof Error ? err.message : "Failed to load providers or models";
        if (isMounted) {
          setLoadingError(message);
          setError(message);
        }
      } finally {
        if (isMounted) {
          if (!isEditMode) {
            setIsLoading(false);
          }
        }
      }
    };
    fetchData();
    return () => { isMounted = false; };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const fetchModelData = async () => {
      if (isEditMode && modelId && providers.length > 0 && providerModelsData) {
        try {
          if (!isLoading) setIsLoading(true);
          const response = await getModelConfig(modelId);
          if (!isMounted) return;

          if (!response.success || !response.data) {
            throw new Error(response.error || "Failed to fetch model");
          }
          const modelData = response.data;
          setName(modelData.name);

          const provider = providers.find(p => p.type === modelData.providerName);
          setSelectedProvider(provider || null);

          const providerFormKey = provider ? getProviderFormKey(provider.type as BackendModelProviderType) : undefined;
          if (providerFormKey && modelData.model) {
            setSelectedCombinedModel(`${providerFormKey}::${modelData.model}`);
          }

          setApiKey("");
          setSecretKey("");

          const requiredKeys = provider?.requiredParams || [];
          const fetchedParams = modelData.modelParams || {};

          const initialRequired: ModelParam[] = requiredKeys.map((key, index) => {
            const fetchedValue = fetchedParams[key];
            const displayValue = (fetchedValue === null || fetchedValue === undefined) ? "" : String(fetchedValue);
            return { id: `req-${index}`, key: key, value: displayValue };
          });

          const initialOptional: ModelParam[] = Object.entries(fetchedParams)
            .filter(([key]) => !requiredKeys.includes(key))
            .map(([key, value], index) => {
              const displayValue = (value === null || value === undefined) ? "" : String(value);
              return { id: `fetched-opt-${index}`, key, value: displayValue };
            });

            setRequiredParams(initialRequired);
            setOptionalParams(initialOptional);

        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : "Failed to fetch model";
          if (isMounted) {
            setError(errorMessage);
            setLoadingError(errorMessage);
            toast.error(errorMessage);
          }
        } finally {
          if (isMounted) {
            setIsLoading(false);
          }
        }
      }
    };
    fetchModelData();
    return () => { isMounted = false; };
  }, [isEditMode, modelId, providers, providerModelsData]);

  useEffect(() => {
    if (selectedProvider) {
      const requiredKeys = selectedProvider.requiredParams || [];
      const optionalKeys = selectedProvider.optionalParams || [];

      const currentModelRequiresReset = !isEditMode;

      if (currentModelRequiresReset) {
        const newRequiredParams = requiredKeys.map((key, index) => ({
          id: `req-${index}`,
          key: key,
          value: "",
        }));
        const newOptionalParams = optionalKeys.map((key, index) => ({
          id: `opt-${index}`,
          key: key,
          value: "",
        }));
        setRequiredParams(newRequiredParams);
        setOptionalParams(newOptionalParams);
      }

      setErrors(prev => ({ ...prev, requiredParams: {}, optionalParams: undefined }));

    } else {
      setRequiredParams([]);
      setOptionalParams([]);
    }
  }, [selectedProvider, isEditMode]);

  useEffect(() => {
    if (!isEditMode && !isEditingName && selectedCombinedModel) {
      const parts = selectedCombinedModel.split('::');
      if (parts.length === 2) {
        const providerKey = parts[0];
        const modelName = parts[1];
        const baseName = `${providerKey}-${modelName}`.toLowerCase();
        const validName = baseName.replace(/[^a-z0-9-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
        if (isResourceNameValid(validName)) {
          setName(validName);
        }
      }
    }
  }, [selectedCombinedModel, isEditMode, isEditingName]);

  const validateForm = () => {
    const newErrors: ValidationErrors = {};

    console.log("🐛 DEBUGGING - validateForm called");
    console.log("🐛 Form state:", {
      name,
      selectedCombinedModel,
      apiKey: apiKey ? "***filled***" : "empty",
      secretKey: secretKey ? "***filled***" : "empty",
      isBedrockSelected,
      isEditMode,
      requiredParams: requiredParams.map(p => ({ key: p.key, value: p.value ? "***filled***" : "empty" })),
      optionalParams: optionalParams.map(p => ({ key: p.key, value: p.value ? "***filled***" : "empty" }))
    });

    if (!isResourceNameValid(name)) {
      newErrors.name = "Name must be a valid RFC 1123 subdomain name";
      console.log("🐛 VALIDATION ERROR: Invalid name", name);
    }
    
    if (!selectedCombinedModel) {
      newErrors.selectedCombinedModel = "Provider and Model selection is required";
      console.log("🐛 VALIDATION ERROR: No model selected");
    }
    
    const isOllamaNow = selectedCombinedModel?.startsWith('ollama::');
    if (!isEditMode && !isOllamaNow && !apiKey.trim()) {
      newErrors.apiKey = "API key is required for new models (except Ollama)";
      console.log("🐛 VALIDATION ERROR: API key required");
    }

    // Special validation for Bedrock
    if (isBedrockSelected && !isEditMode && !secretKey.trim()) {
      newErrors.secretKey = "Secret key is required for AWS Bedrock";
      console.log("🐛 VALIDATION ERROR: Bedrock secret key required");
    }

    // Skip required parameter validation for Bedrock since it has no required parameters
    if (!isBedrockSelected) {
      console.log("🐛 Checking required params for non-Bedrock provider");
      const requiredParamErrors: Record<string, string> = {};
    requiredParams.forEach(param => {
      if (!param.value.trim() && param.key.trim()) {
          requiredParamErrors[param.key] = `${param.key} is required`;
          console.log("🐛 VALIDATION ERROR: Required param missing", param.key);
        }
      });
      // Only add requiredParams to newErrors if there are actual errors
      if (Object.keys(requiredParamErrors).length > 0) {
        newErrors.requiredParams = requiredParamErrors;
      }
    } else {
      console.log("🐛 Skipping required param validation for Bedrock");
      }

    const paramKeys = new Set<string>();
    let duplicateKeyError = false;
    optionalParams.forEach(param => {
      const key = param.key.trim();
      if (key) {
        if (paramKeys.has(key)) {
          duplicateKeyError = true;
          console.log("🐛 VALIDATION ERROR: Duplicate optional param key", key);
        }
        paramKeys.add(key);
      }
    });
    requiredParams.forEach(param => {
      const key = param.key.trim();
      if (key) {
        if (paramKeys.has(key)) {
        } else {
          paramKeys.add(key);
        }
      }
    });

    if (duplicateKeyError) {
      newErrors.optionalParams = "Duplicate optional parameter key detected";
    }

    console.log("🐛 Final validation errors:", newErrors);
    console.log("🐛 Has errors:", Object.keys(newErrors).length > 0 || 
        (newErrors.requiredParams && Object.keys(newErrors.requiredParams).length > 0) ||
        newErrors.optionalParams);

    return newErrors;
  };

  const handleRequiredParamChange = (index: number, value: string) => {
    const newParams = [...requiredParams];
    newParams[index].value = value;
    setRequiredParams(newParams);
    if (errors.requiredParams && errors.requiredParams[newParams[index].key]) {
      const updatedParamErrors = { ...errors.requiredParams };
      delete updatedParamErrors[newParams[index].key];
      setErrors(prev => ({ ...prev, requiredParams: updatedParamErrors }));
    }
  };

  const handleOptionalParamChange = (index: number, value: string) => {
    const newParams = [...optionalParams];
    newParams[index].value = value;
    setOptionalParams(newParams);
    if (errors.optionalParams) {
      setErrors(prev => ({ ...prev, optionalParams: undefined }));
    }
  };

  const handleSubmit = async () => {
    console.log("🐛 DEBUGGING - handleSubmit called");
    const validationErrors = validateForm();
    console.log("🐛 Validation errors returned:", validationErrors);
    console.log("🐛 Error check results:", {
      "Object.keys(validationErrors).length": Object.keys(validationErrors).length,
      "validationErrors.requiredParams": validationErrors.requiredParams,
      "Object.keys(validationErrors.requiredParams || {}).length": Object.keys(validationErrors.requiredParams || {}).length,
      "validationErrors.optionalParams": validationErrors.optionalParams
    });
    
    if (Object.keys(validationErrors).length > 0 || 
        (validationErrors.requiredParams && Object.keys(validationErrors.requiredParams).length > 0) ||
        validationErrors.optionalParams) {
      console.log("🐛 VALIDATION FAILED - Setting errors and showing toast");
      setErrors(validationErrors);
      toast.error("Please fix the errors in the form");
      return;
    }

    console.log("🐛 VALIDATION PASSED - Proceeding with submission");
    setIsSubmitting(true);
    setError(null);

    try {
      const parts = selectedCombinedModel!.split('::');
      const providerKey = parts[0] as ModelProviderKey;
      const modelName = parts[1];
      
      const finalSelectedProvider = providers.find(p => getProviderFormKey(p.type as BackendModelProviderType) === providerKey);
      if (!finalSelectedProvider) {
        throw new Error("Provider not found");
      }

      const modelParams = processModelParams(requiredParams, optionalParams);
      
      // Handle Bedrock secretKey special case
      if (isBedrockSelected && secretKey) {
        modelParams.secretKey = secretKey;
      }

      const payload: CreateModelConfigPayload = {
        name,
        model: modelName,
        provider: {
          name: finalSelectedProvider.name,
          type: finalSelectedProvider.type
        },
        apiKey: "", // Will be updated if there's a valid key
      };

      // Only add apiKey to payload if it exists and isn't empty
      const trimmedApiKey = apiKey.trim();
      if (trimmedApiKey) {
        payload.apiKey = trimmedApiKey;
      }
      
      // Set the provider-specific config based on the provider type
      if (finalSelectedProvider.type === "OpenAI") {
        payload.openAI = modelParams;
      } else if (finalSelectedProvider.type === "Anthropic") {
        payload.anthropic = modelParams;
      } else if (finalSelectedProvider.type === "AzureOpenAI") {
        // For Azure, ensure required fields are present
        // Check if azureEndpoint and apiVersion are in the modelParams
        if (modelParams.azureEndpoint && modelParams.apiVersion) {
          payload.azureOpenAI = modelParams as AzureOpenAIConfigPayload;
        } else {
          // If the required fields are missing, we need to handle that case
          // Here, we'll use a minimal implementation with empty strings for required fields
          payload.azureOpenAI = {
            azureEndpoint: modelParams.azureEndpoint || "",
            apiVersion: modelParams.apiVersion || "",
            ...modelParams
          };
        }
      } else if (finalSelectedProvider.type === "Ollama") {
        payload.ollama = modelParams;
      } else if (finalSelectedProvider.type === "Bedrock") {
        // For Bedrock, use the enhanced backend that translates to LiteLLM
        payload.bedrock = {
          region: modelParams.region || "us-west-2",
          maxTokens: modelParams.maxTokens || modelParams.max_tokens || 1024,
          temperature: modelParams.temperature || "0.7",
          topP: modelParams.topP || modelParams.top_p || "1.0"
        };
        // Send AWS Secret Access Key as top-level secretKey field
        if (secretKey) {
          payload.secretKey = secretKey;
        }
      }

      const response = isEditMode && modelId
        ? await updateModelConfig(modelId, payload)
        : await createModelConfig(payload);

      if (!response.success) {
        throw new Error(response.error || "Failed to save model");
      }

      toast.success(`Model ${isEditMode ? 'updated' : 'created'} successfully`);
      router.push("/models");
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to save model";
      setError(errorMessage);
      toast.error(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (error) {
    return <ErrorState message={error} />;
  }

  if (isLoading && !isEditMode) {
    return <LoadingState />;
  }

  const showLoadingOverlay = isLoading && isEditMode;

  return (
    <div className="min-h-screen p-8 relative">
      {showLoadingOverlay && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-50">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      )}

      <div className="max-w-6xl mx-auto">
        <h1 className="text-2xl font-bold mb-8">{isEditMode ? "Edit Model" : "Create New Model"}</h1>

        <div className="space-y-6">
          <BasicInfoSection
            name={name}
            isEditingName={isEditingName}
            errors={errors}
            isSubmitting={isSubmitting}
            isLoading={isLoading}
            onNameChange={setName}
            onToggleEditName={() => setIsEditingName(!isEditingName)}
            providers={providers}
            providerModelsData={providerModelsData}
            selectedCombinedModel={selectedCombinedModel}
            onModelChange={(comboboxValue, providerKey, modelName, functionCalling) => {
              setSelectedCombinedModel(comboboxValue);
              const prov = providers.find(p => getProviderFormKey(p.type as BackendModelProviderType) === providerKey);
              setSelectedProvider(prov || null);
              setSelectedModelSupportsFunctionCalling(functionCalling);
              if (errors.selectedCombinedModel) {
                setErrors(prev => ({ ...prev, selectedCombinedModel: undefined }));
              }
            }}
            selectedProvider={selectedProvider}
            selectedModelSupportsFunctionCalling={selectedModelSupportsFunctionCalling}
            loadingError={loadingError}
            isEditMode={isEditMode}
          />

          <AuthSection
            isOllamaSelected={isOllamaSelected}
            isBedrockSelected={isBedrockSelected}
            isEditMode={isEditMode}
            apiKey={apiKey}
            secretKey={secretKey}
            showApiKey={showApiKey}
            showSecretKey={showSecretKey}
            errors={errors}
            isSubmitting={isSubmitting}
            isLoading={isLoading}
            onApiKeyChange={setApiKey}
            onSecretKeyChange={setSecretKey}
            onToggleShowApiKey={() => setShowApiKey(!showApiKey)}
            onToggleShowSecretKey={() => setShowSecretKey(!showSecretKey)}
            selectedProvider={selectedProvider}
          />

          <ParamsSection
            selectedProvider={selectedProvider}
            requiredParams={requiredParams}
            optionalParams={optionalParams}
            errors={errors}
            isSubmitting={isSubmitting}
            isLoading={isLoading}
            onRequiredParamChange={handleRequiredParamChange}
            onOptionalParamChange={handleOptionalParamChange}
          />
        </div>

        <div className="flex justify-end pt-6">
          <Button
            variant="default"
            onClick={handleSubmit}
            disabled={isSubmitting || isLoading}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {isEditMode ? "Updating..." : "Creating..."}
              </>
            ) : isEditMode ? (
              "Update Model"
            ) : (
              "Create Model"
            )}
          </Button>
        </div>

      </div>
    </div>
  );
}

export default function ModelPage() {
  return (
    <React.Suspense fallback={<LoadingState />}>
      <ModelPageContent />
    </React.Suspense>
  );
} 