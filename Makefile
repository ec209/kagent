# Image configuration
DOCKER_REGISTRY ?= ghcr.io
DOCKER_REPO ?= kagent-dev/kagent
CONTROLLER_IMAGE_NAME ?= controller
UI_IMAGE_NAME ?= ui
APP_IMAGE_NAME ?= app
VERSION ?= $(shell git describe --tags --always --dirty)
CONTROLLER_IMAGE_TAG ?= $(VERSION)
UI_IMAGE_TAG ?= $(VERSION)
APP_IMAGE_TAG ?= $(VERSION)
CONTROLLER_IMG ?= $(DOCKER_REGISTRY)/$(DOCKER_REPO)/$(CONTROLLER_IMAGE_NAME):$(CONTROLLER_IMAGE_TAG)
UI_IMG ?= $(DOCKER_REGISTRY)/$(DOCKER_REPO)/$(UI_IMAGE_NAME):$(UI_IMAGE_TAG)
APP_IMG ?= $(DOCKER_REGISTRY)/$(DOCKER_REPO)/$(APP_IMAGE_NAME):$(APP_IMAGE_TAG)
# Retagged image variables for minikube; the Helm chart uses these
RETAGGED_DOCKER_REGISTRY = cr.kagent.dev
RETAGGED_CONTROLLER_IMG = $(RETAGGED_DOCKER_REGISTRY)/$(DOCKER_REPO)/$(CONTROLLER_IMAGE_NAME):$(CONTROLLER_IMAGE_TAG)
RETAGGED_UI_IMG = $(RETAGGED_DOCKER_REGISTRY)/$(DOCKER_REPO)/$(UI_IMAGE_NAME):$(UI_IMAGE_TAG)
RETAGGED_APP_IMG = $(RETAGGED_DOCKER_REGISTRY)/$(DOCKER_REPO)/$(APP_IMAGE_NAME):$(APP_IMAGE_TAG)
DOCKER_BUILDER ?= podman
DOCKER_BUILD_ARGS ?=

# Check if OPENAI_API_KEY is set
check-openai-key:
	@if [ -z "$(OPENAI_API_KEY)" ]; then \
		echo "Error: OPENAI_API_KEY environment variable is not set"; \
		echo "Please set it with: export OPENAI_API_KEY=your-api-key"; \
		exit 1; \
	fi

# Build targets

.PHONY: build
build: build-controller build-ui build-app

.PHONY: build-cli
build-cli:
	make -C go build

.PHONY: push
push: push-controller push-ui push-app

.PHONY: controller-manifests
controller-manifests:
	make -C go manifests
	cp go/config/crd/bases/* helm/kagent-crds/templates/

.PHONY: build-controller
build-controller: controller-manifests
	$(DOCKER_BUILDER) build  $(DOCKER_BUILD_ARGS) -t $(CONTROLLER_IMG) -f go/Dockerfile ./go

.PHONY: release-controller
release-controller: DOCKER_BUILD_ARGS += --push --platform linux/amd64,linux/arm64
release-controller: DOCKER_BUILDER = podman
release-controller: build-controller

.PHONY: build-ui
build-ui:
	# Build the combined UI and backend image
	$(DOCKER_BUILDER) build $(DOCKER_BUILD_ARGS)  -t $(UI_IMG) -f ui/Dockerfile ./ui

.PHONY: release-ui
release-ui: DOCKER_BUILD_ARGS += --push --platform linux/amd64,linux/arm64
release-ui: DOCKER_BUILDER = podman
release-ui: build-ui

.PHONY: build-app
build-app:
	$(DOCKER_BUILDER)  build $(DOCKER_BUILD_ARGS) -t $(APP_IMG) -f python/Dockerfile ./python

.PHONY: release-app
release-app: DOCKER_BUILD_ARGS += --push --platform linux/amd64,linux/arm64
release-app: DOCKER_BUILDER = podman
release-app: build-app

.PHONY: minikube-load-images
minikube-load-images: retag-docker-images
	@echo "Saving images to temporary files..."
	podman save $(RETAGGED_CONTROLLER_IMG) -o /tmp/controller-image.tar
	podman save $(RETAGGED_UI_IMG) -o /tmp/ui-image.tar
	podman save $(RETAGGED_APP_IMG) -o /tmp/app-image.tar
	@echo "Loading images into minikube..."
	minikube image load /tmp/controller-image.tar
	minikube image load /tmp/ui-image.tar
	minikube image load /tmp/app-image.tar
	@echo "Cleaning up temporary files..."
	rm -f /tmp/controller-image.tar /tmp/ui-image.tar /tmp/app-image.tar

.PHONY: retag-docker-images
retag-docker-images: build
	podman tag $(CONTROLLER_IMG) $(RETAGGED_CONTROLLER_IMG)
	podman tag $(UI_IMG) $(RETAGGED_UI_IMG)
	podman tag $(APP_IMG) $(RETAGGED_APP_IMG)

.PHONY: helm-version
helm-version:
	@# Convert Git hash to semver-compatible format and ensure there's valid content after prefix
	@export CLEAN_VERSION=$$(echo "${VERSION}" | sed 's/-dirty//g'); \
	if [ -z "$$CLEAN_VERSION" ]; then \
		export VERSION="0.0.0-dev"; \
	else \
		export VERSION="0.0.0-$$CLEAN_VERSION"; \
	fi; \
	envsubst < helm/kagent-crds/Chart-template.yaml > helm/kagent-crds/Chart.yaml; \
	envsubst < helm/kagent/Chart-template.yaml > helm/kagent/Chart.yaml; \
	helm package helm/kagent-crds; \
	helm package helm/kagent

.PHONY: helm-install
helm-install: helm-version check-openai-key minikube-load-images
	helm upgrade --install kagent-crds helm/kagent-crds \
		--namespace kagent \
		--create-namespace \
		--wait
	helm upgrade --install kagent helm/kagent \
		--namespace kagent \
		--create-namespace \
		--wait \
		--set controller.image.registry=$(RETAGGED_DOCKER_REGISTRY) \
		--set ui.image.registry=$(RETAGGED_DOCKER_REGISTRY) \
		--set app.image.registry=$(RETAGGED_DOCKER_REGISTRY) \
		--set controller.image.tag=$(CONTROLLER_IMAGE_TAG) \
		--set ui.image.tag=$(UI_IMAGE_TAG) \
		--set app.image.tag=$(APP_IMAGE_TAG) \
		--set openai.apiKey=$(OPENAI_API_KEY)

.PHONY: helm-uninstall
helm-uninstall:
	helm uninstall kagent --namespace kagent
	helm uninstall kagent-crds --namespace kagent

.PHONY: helm-publish
helm-publish: helm-version
	helm push kagent-crds-$(VERSION).tgz oci://ghcr.io/kagent-dev/kagent/helm
	helm push kagent-$(VERSION).tgz oci://ghcr.io/kagent-dev/kagent/helm

.PHONY: bedrock-image
bedrock-image:
	@echo "Building Kagent image with Bedrock support..."
	VERSION=5305f81-dirty make build-app
	@echo "Setting up Helm chart with the new image..."
	VERSION=5305f81-dirty make helm-install
	@echo "Bedrock integration complete!"
	@echo "You can now check if Bedrock models are available with:"
	@echo "kubectl -n kagent port-forward svc/kagent 8001:80 &"
	@echo "curl -s http://127.0.0.1:8001/api/models | jq ."
