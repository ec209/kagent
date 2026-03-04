# Changelog

## Unreleased

### Added
- AWS Bedrock provider support via external LiteLLM proxy architecture
- Slack bot integration with Socket Mode for real-time agent interaction
- UI support for Bedrock configuration (region, model parameters)
- Multi-container architecture: controller, app, ui, slack-bot
- IRSA-ready configuration for secure AWS access
- Comprehensive project documentation (INDEX.md)

### Changed
- **BREAKING**: Moved to external LiteLLM proxy architecture for better separation of concerns
- Removed embedded LiteLLM proxy container from kagent deployment
- AWS credentials now handled by external LiteLLM service with IRSA
- Simplified Bedrock configuration to focus on model parameters only
- Enhanced build system with Slack bot support

### Fixed
- Removed hardcoded AWS credentials from configuration files
- Cleaned up build artifacts and improved .gitignore
- Simplified controller logic by removing AWS-specific secret management

### Removed
- bedrock-integration.sh script (replaced by cleaner LiteLLM SDK integration)
- Direct AWS credential handling in kagent controller
- Embedded LiteLLM proxy container

## v0.4.0

... 