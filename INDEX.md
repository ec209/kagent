# Kagent Project Index

## Overview
**Kagent** is a Kubernetes native framework for building AI agents. It provides a flexible and powerful way to build, deploy, and manage AI agents in Kubernetes environments using declarative configuration.

## Project Structure

### Root Directory
```
misc/kagent/
├── README.md                    # Main project documentation
├── DEVELOPMENT.md              # Development setup and guidelines
├── CONTRIBUTION.md             # Contribution guidelines
├── CHANGELOG.md                # Project changelog
├── LICENSE                     # Project license
├── CODE_OF_CONDUCT.md         # Code of conduct
├── CODEOWNERS                  # Code ownership definitions
├── Makefile                    # Build and deployment automation
├── .gitignore                  # Git ignore rules
├── bedrock-integration.sh      # AWS Bedrock integration script
└── kagent-*.tgz               # Various versioned release packages
```

### Core Components

#### 1. Python Engine (`python/`)
The AI agent execution engine built on Microsoft Autogen.

**Key Files:**
- `pyproject.toml` - Python project configuration
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container build configuration
- `uv.lock` - Dependency lock file

**Source Structure:**
```
python/src/
├── kagent/
│   ├── agents/          # Agent implementations
│   ├── tools/           # Tool definitions and implementations
│   ├── tool_servers/    # Tool server implementations
│   ├── memory/          # Memory management
│   └── cli.py          # Command-line interface
└── autogen_ext/        # Autogen extensions
```

**Additional Directories:**
- `tests/` - Test suite
- `docs/` - Python-specific documentation
- `examples/` - Usage examples
- `notebooks/` - Jupyter notebooks for development

#### 2. Go Controller (`go/`)
Kubernetes controller and CLI implementation.

**Key Files:**
- `go.mod`, `go.sum` - Go module configuration
- `Dockerfile` - Container build configuration
- `Makefile` - Go-specific build targets
- `README.md` - Go component documentation

**Source Structure:**
```
go/controller/
├── api/             # Kubernetes API definitions
├── cmd/             # Command-line applications
├── internal/        # Internal packages
├── hack/            # Development scripts
└── PROJECT          # Kubebuilder project configuration
```

**Additional Directories:**
- `bin/` - Compiled binaries
- `test/` - Test files
- `config/` - Kubernetes configurations
- `cli/` - CLI implementation
- `autogen/` - Auto-generated code

#### 3. Web UI (`ui/`)
React-based web interface for managing agents and tools.

**Key Files:**
- `package.json` - Node.js dependencies and scripts
- `package-lock.json` - Dependency lock file
- `next.config.ts` - Next.js configuration
- `tailwind.config.ts` - Tailwind CSS configuration
- `tsconfig.json` - TypeScript configuration
- `Dockerfile` - Container build configuration

**Source Structure:**
```
ui/src/
├── app/             # Next.js app router pages
├── components/      # React components
├── hooks/           # Custom React hooks
├── lib/             # Utility libraries
└── types/           # TypeScript type definitions
```

**Configuration Files:**
- `eslint.config.mjs` - ESLint configuration
- `jest.config.ts` - Jest testing configuration
- `postcss.config.mjs` - PostCSS configuration
- `components.json` - UI component configuration

### Documentation (`docs/`)
```
docs/
├── aws-bedrock.md                    # AWS Bedrock integration guide
└── implementation-notes-bedrock.md   # Bedrock implementation details
```

### Examples (`examples/`)
```
examples/
└── bedrock_client.py    # Example Bedrock client implementation
```

### Deployment (`helm/`)
Helm charts for Kubernetes deployment.

**Structure:**
```
helm/
├── kagent/          # Main kagent Helm chart
├── kagent-crds/     # Custom Resource Definitions chart
└── README.md        # Helm deployment documentation
```

### Scripts (`scripts/`)
```
scripts/
└── get-kagent       # Installation script
```

### Assets (`img/`)
Project images and assets for documentation.

## Architecture

Kagent consists of 4 core components:

1. **Controller** - Kubernetes controller that manages kagent custom resources
2. **UI** - Web interface for managing agents and tools
3. **Engine** - Python application that executes agents (built on Autogen)
4. **CLI** - Command-line tool for management operations

## Key Features

- **Kubernetes Native**: Fully integrated with Kubernetes ecosystem
- **Declarative**: Define agents and tools using YAML configurations
- **Extensible**: Support for custom agents and tools
- **Observable**: Built-in monitoring and tracing capabilities
- **Multi-LLM**: Support for multiple LLM providers including AWS Bedrock
- **Tool Discovery**: Automatic tool discovery and MCP server support

## Development Workflow

### Local Development
1. **Python Engine**: Run from `python/` directory using `uv run kagent-engine serve`
2. **UI**: Run from `ui/` directory using `npm run dev`
3. **Controller**: Build and run from `go/` directory

### Kubernetes Development
1. Create cluster: `make create-kind-cluster`
2. Set API keys: `export OPENAI_API_KEY=your-key`
3. Deploy: `make helm-install`
4. Access UI: `kubectl port-forward svc/app 8001:80`

## Build System

The project uses a comprehensive Makefile with targets for:
- **Building**: `make build` (builds all components)
- **Docker Images**: Component-specific build targets
- **Helm Deployment**: `make helm-install`
- **Release**: Multi-platform image builds and publishing

## Version Management

- Versions are derived from Git tags and commits
- Release packages are stored as `.tgz` files in the root directory
- Helm charts use templated versioning system

## Integration Points

- **AWS Bedrock**: Via external LiteLLM proxy with IRSA for secure access
- **OpenAI**: Primary LLM provider support
- **LiteLLM Proxy**: External service handling multi-provider LLM access
- **Kubernetes**: Full CRD and operator pattern implementation
- **Autogen**: Built on Microsoft's Autogen framework
- **MCP**: Model Context Protocol server support

## Architecture Principles

### LLM Provider Integration
Kagent follows a **proxy-based architecture** for LLM access:

```
Kagent Controller → External LiteLLM Proxy → AWS Bedrock/OpenAI/etc.
```

**Benefits:**
- 🔒 **Secure**: LiteLLM handles credentials via IRSA
- 🏗️ **Scalable**: LiteLLM scales independently
- 🧹 **Clean**: Kagent focuses on orchestration, not LLM specifics

## Configuration Management

- **Environment Variables**: API keys and runtime configuration
- **Kubernetes ConfigMaps/Secrets**: Cluster-level configuration
- **Helm Values**: Deployment-time configuration
- **YAML Manifests**: Declarative agent and tool definitions 