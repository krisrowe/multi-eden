# Multi-Eden

An opinionated full-stack development SDK that provides task runners, testing framework, and configuration management with comprehensive mocking capabilities. Multi-Eden enables you to rapidly build production-ready applications with Firebase frontend, containerized Python API on Google Cloud Run, and Firestore database - all with flexible stubbing for different testing scenarios.

## What Multi-Eden Provides

### Full-Stack Architecture
- **Firebase Frontend**: Web application with Firebase Hosting
- **Containerized Python API**: FastAPI backend deployed to Google Cloud Run
- **Firestore Database**: NoSQL document database
- **AI Integration**: Optional Google Gemini AI model integration
- **Firebase Authentication**: User authentication and authorization

### Advanced Configuration & Stubbing System
The core strength of Multi-Eden is its sophisticated configuration framework (`multi_eden.run.config`) that enables:

- **Environment-based Configuration**: Different settings for `local`, `docker`, `cloud` environments
- **Test Mode Configuration**: Specialized test configurations with stubbing capabilities
- **Provider Stubbing**: Mock external dependencies selectively:
  - `STUB_DB=true` - Use in-memory database instead of Firestore
  - `STUB_AI=true` - Use mocked AI responses instead of real Gemini API
  - `CUSTOM_AUTH_ENABLED=true` - Use custom auth instead of Firebase Auth
- **In-Memory API Testing**: Run the entire API server in-memory during unit tests
- **Terraform-based Deployment**: Automated infrastructure deployment with environment-specific secrets

### Testing Framework
- **Multi-Suite Testing**: `unit`, `integration`, `api`, `ai` test suites
- **Same Tests, Different Configs**: Run identical test suites against different provider configurations
- **Automatic Environment Setup**: Tests automatically configure the right stubs and providers
- **API Integration Testing**: Test your API endpoints with real or mocked backends

## Quick Start: Building Apps with Multi-Eden

### From an App Repository

Working with an app built around Multi-Eden is designed to be incredibly simple:

```bash
# Clone an app repository that uses Multi-Eden
git clone https://github.com/your-org/your-app.git
cd your-app

# Install and run tests - everything should just work!
make install
pytest
```

**What happens**: All tests pass immediately with some AI integration tests skipped (no API key needed yet).

```bash
# Register a secret and run AI tests too
invoke secrets.set gemini-api-key --denv=local
pytest tests/ai/
```

**What happens**: AI tests now pass with real API integration.

```bash
# Start the API server
invoke api-start

# Run API tests against the running server
pytest tests/api/ --denv=local

# Build and deploy
invoke build
invoke deploy --profile=dev
```

**What happens**: Complete development workflow from testing to deployment with minimal commands.

### From an Empty Directory (New App Initialization)

Create a new app using Multi-Eden with a single command:

```bash
# From any empty directory
curl -sSL https://raw.githubusercontent.com/krisrowe/multi-eden/main/install.sh | bash

# This creates a local venv, installs the SDK, and runs init-app
# Follow the prompts to set up your new application
```

**What happens**: 
- Creates a Python virtual environment
- Installs Multi-Eden SDK
- Runs `invoke init-app` to scaffold your new application
- Sets up configuration files and project structure
- Ready to start development immediately

## Task System: Automated Environment Management

Multi-Eden's task runners automatically handle environment setup, configuration loading, and service orchestration. Each task loads the appropriate settings and populates environment variables before starting your application.

### Testing Tasks

```bash
# Test with automatic environment setup
./invoke test unit                    # Full stubbing (STUB_DB=true, STUB_AI=true)
./invoke test api --config-env=docker # Real DB, mocked AI
./invoke test integration             # All real services
./invoke test ai --test-name="test_*auth*"  # Filter specific tests
```

**How it works**: The test runner:
1. Reads `config/tests.yaml` to determine test suite configuration
2. Loads environment-specific settings from `config/settings/{env}/`
3. Sets up provider stubs based on `providers.json` configuration
4. Runs tests with appropriate in-memory vs. external service routing

### Local Development Tasks

```bash
# Start API server with environment auto-loading
./invoke api-start --env=local-server --port=8000
./invoke api-status                   # Check server status
./invoke api-stop                     # Stop server
./invoke api-restart                  # Restart with new config
```

**Environment Loading**: Automatically loads:
- **Secrets** from `config/secrets/{env}/secrets.json` (JWT salt, AI API keys, auth settings)
- **Provider settings** from `config/settings/{env}/providers.json` (which services to stub)
- **Host configuration** from `config/settings/{env}/host.json` (project ID, API URLs, Firebase config)
- Sets environment variables (`STUB_DB`, `STUB_AI`, `CUSTOM_AUTH_ENABLED`) for your application

### Docker Tasks

```bash
# Run containerized API with config injection
./invoke docker-build                 # Build image with current code
./invoke docker-run --config-env=local-docker --port=8001
./invoke docker-status               # Check container status
./invoke docker-cleanup              # Clean up resources
```

**Container Configuration**: The Docker tasks:
- Build images with your application code
- Mount configuration files into containers
- Set environment variables for containerized services
- Handle port mapping and networking

### Full Stack Tasks

```bash
# Start complete development stack
./invoke compose-up --config-env=dev  # API + Database + Frontend
./invoke compose-logs                 # View all service logs
./invoke compose-down                 # Stop all services
```

### Cloud Deployment Tasks

```bash
# Deploy to Google Cloud with environment-specific config
./invoke deploy --env=prod --tag=v1.2.0
./invoke deploy-web --env=staging     # Deploy frontend to Firebase
./invoke status --env=prod            # Check deployment status
```

**Cloud Deployment**: Automatically:
- Loads environment-specific secrets and configuration
- Builds and tags Docker images
- Deploys to Google Cloud Run with proper environment variables
- Configures Firebase Hosting with environment-specific settings

### Build & Deploy Pipeline

**Smart Incremental Build System**:
- `./invoke build` - Auto-detect git tags, validate state, build Docker images
- `./invoke build --tag=v1.0.0` - Build with specific tag
- `./invoke build --force` - Force rebuild even if image exists

**Environment-Aware Cloud Deployment**:
- `./invoke deploy --env=dev` - Deploy to dev environment using dev configuration
- `./invoke deploy --env=prod --tag=v1.0.0` - Deploy specific tag to production
- `./invoke deploy-web` - Deploy frontend to Firebase Hosting
- `./invoke status` - Check deployment status across environments

### Configuration Management Tasks

```bash
# Manage environment configurations
./invoke config-env-list              # List all environments
./invoke config-env-create --env-name=staging --project-id=my-staging-project
./invoke config-env-backup --env=prod # Backup to GCS
./invoke config-env-restore --env=prod # Restore from GCS
```

## Getting Started with Your App

### Minimum Configuration Required
To use Multi-Eden in your application, you need:

1. **Project Structure**: Multi-Eden expects this structure:
   ```
   your-app/
   ├── config/
   │   ├── app.yaml              # App configuration (optional, defaults generated)
   │   ├── tests.yaml            # Test mode configurations
   │   ├── secrets/
   │   │   └── {env}/secrets.json # Environment-specific secrets
   │   └── settings/
   │       └── {env}/host.json   # Environment-specific settings
   ├── src/your_app/            # Your application code
   ├── tests/                   # Your test files
   └── invoke                   # Multi-Eden task runner
   ```

2. **Test Configuration** (`config/tests.yaml`):
   ```yaml
   modes:
     unit:
       description: "Unit tests with full stubbing"
       in_memory_api: true
       default_env: "local"
       tests:
         paths: ["tests/unit"]
     
     api:
       description: "API integration tests"
       in_memory_api: false
       default_env: "docker"
       tests:
         paths: ["tests/api", "tests/unit"]  # Run API tests + unit tests in-memory
   ```

3. **Provider Configuration** (`config/settings/{env}/providers.json`):
   ```json
   {
     "auth_provider": ["custom"],
     "data_provider": "tinydb",
     "ai_provider": "mocked"
   }
   ```

4. **Host Configuration** (`config/settings/{env}/host.json`):
   ```json
   {
     "project_id": "your-gcp-project-id",
     "api_url": "http://localhost:8000"
   }
   ```

5. **Secrets Configuration** (`config/secrets/{env}/secrets.json`):
   ```json
   {
     "salt": "your-jwt-secret-key-for-token-signing",
     "google_api_key": "your-gemini-api-key-here",
     "authorization": {
       "all_authenticated_users": false,
       "allowed_user_emails": ["user@example.com"]
     }
   }
   ```

### How Configuration Files Work Together

**Test Suite Configuration Flow**:
1. `./invoke test api` → reads `tests.yaml` → finds `api` mode
2. `api` mode specifies `default_env: "docker"` and `paths: ["tests/api", "tests/unit"]`
3. Loads `config/settings/docker/providers.json` → determines which services to stub
4. Loads `config/settings/docker/host.json` → gets project ID and API configuration
5. Sets environment variables (`STUB_DB`, `STUB_AI`, etc.) based on provider configuration
6. Runs both API tests (against real/containerized services) AND unit tests (in-memory)

**Provider Stubbing Logic**:
- `"data_provider": "tinydb"` → Uses in-memory TinyDB instead of Firestore
- `"ai_provider": "mocked"` → Returns predefined responses instead of calling Gemini API
- `"auth_provider": ["custom"]` → Uses test tokens instead of Firebase Auth

**Multi-Suite Testing**: The `api` test mode can run multiple test suites:
- `tests/api/` - Integration tests against containerized services
- `tests/unit/` - Unit tests running in-memory alongside the API tests
- Same test code, different provider configurations automatically loaded

### Optional Configuration
- **AI Models** (`models.yaml`): Configure available AI models and providers
- **App Configuration** (`config/app.yaml`): Override default app ID

### Key Configuration Settings

**JWT Authentication** (`secrets.json`):
- `salt`: Secret key used for signing JWT tokens in your API
- Used by the authentication system to generate and validate user tokens

**AI Integration** (`secrets.json`):
- `google_api_key`: Your Google Gemini API key for AI model access
- Required when `STUB_AI=false` to make real AI API calls

**Host Configuration** (`host.json`):
- `project_id`: Google Cloud project ID for Firestore and Cloud Run deployment
- `api_url`: Base URL for API server (varies by environment: local, docker, cloud)

**Environment Variables** (set by task runners):
- `STUB_DB`: Control database provider (true=TinyDB, false=Firestore)
- `STUB_AI`: Control AI provider (true=mocked responses, false=real Gemini API)
- `CUSTOM_AUTH_ENABLED`: Control auth provider (true=custom tokens, false=Firebase Auth)

## Cloud Deployment Pipeline: The Power of Environment-Aware Deployment

Multi-Eden's deploy system showcases the framework's most powerful capability: **seamless environment-aware deployment to Google Cloud Run** using a centralized container registry and automated configuration management.

### Smart Build-to-Deploy Pipeline

**1. Centralized Container Registry**:
- All environments share a single Google Container Registry (`gcr.io/{project_id}`)
- Images are automatically tagged with git tags or timestamps
- Build task validates git state and creates reproducible, tagged images
- Deploy task references the same central registry for consistent deployments

**2. Environment-Specific Deployment**:
```bash
# Build once, deploy anywhere
./invoke build                    # Creates gcr.io/my-project/my-app:20240827-2119
./invoke deploy --env=dev         # Deploys to dev with dev configuration
./invoke deploy --env=prod        # Deploys same image to prod with prod configuration
```

**3. Automatic Configuration Injection**:
- Deploy task reads `config/settings/{env}/` for the target environment
- Terraform automatically injects environment-specific secrets and settings
- Cloud Run service gets the right project ID, database connections, and API keys
- Same Docker image, different runtime configuration per environment

### Deploy Task Power Features

**Environment Validation**:
- Validates required configuration files exist (`secrets.json`, `providers.json`, `host.json`)
- Ensures Docker image exists in the central registry before deployment
- Prevents deployment of non-existent or misconfigured environments

**Terraform Integration**:
- Uses infrastructure-as-code for consistent Cloud Run deployments
- Automatically configures Cloud Run services with environment-specific variables
- Handles networking, IAM, and service configuration through Terraform

**Tag Management**:
- Auto-detects latest git tags for deployment
- Supports deploying specific versions: `./invoke deploy --env=prod --tag=v1.0.0`
- Maintains deployment history through tagged container images
- Enables easy rollbacks by redeploying previous tags

### Real-World Deployment Flow

```bash
# Developer workflow
git tag v1.2.0
./invoke build --tag=v1.2.0      # Build & push to gcr.io/my-project/my-app:v1.2.0

# Deploy to staging first
./invoke deploy --env=staging --tag=v1.2.0
# → Reads config/settings/staging/
# → Deploys to staging Cloud Run with staging database/secrets

# Deploy to production
./invoke deploy --env=prod --tag=v1.2.0
# → Reads config/settings/prod/
# → Deploys SAME image to prod Cloud Run with prod database/secrets
```

**Key Benefits**:
- **One Image, Multiple Environments**: Same container, different configurations
- **Configuration Isolation**: Each environment has its own secrets and settings
- **Deployment Consistency**: Terraform ensures identical infrastructure across environments
- **Version Control**: Tagged images enable precise version management and rollbacks
- **Zero Configuration Drift**: Infrastructure-as-code prevents environment inconsistencies

### Framework Assumptions
Multi-Eden assumes your application:
- Uses **FastAPI** for the API backend
- Follows **dependency injection** patterns for easy stubbing
- Structures tests in **suite-based directories** (`tests/unit/`, `tests/api/`, etc.)
- Uses **Pydantic models** for data validation
- Implements **provider interfaces** that can be swapped for testing

## Multi-Eden Project Structure

```
multi-eden/
├── src/multi_eden/
│   ├── run/config/          # Configuration framework
│   │   ├── settings.py      # Environment & secrets management
│   │   ├── testing.py       # Test mode configuration
│   │   ├── providers.py     # Provider stubbing system
│   │   └── models.py        # AI model configuration
│   ├── build/tasks/         # Task runners
│   └── cli.py              # Command-line interface
├── tests/                   # Framework tests
├── config/                  # Default configurations
│   └── config.md           # Configuration concepts and design principles
└── invoke                   # Task runner with auto-setup
```

## Configuration System

For detailed information about Multi-Eden's configuration system, see [Configuration Concepts](src/multi_eden/build/config/config.md).

## Key Benefits of Multi-Eden's Stubbing System

### Same Tests, Multiple Configurations
Run identical test suites against different provider configurations:

```bash
# Unit tests with full stubbing (fast, no external dependencies)
# Uses STUB_DB=true, STUB_AI=true, and stubbed auth
# Includes the api tests and runs API in-memory (w/ the stubs)
./invoke test unit 

# API tests with real database but mocked AI
# Makes real http-based API calls to specified env 
./invoke test api --config-env=docker 

# Integration tests with all real services
# Stubs everything but the AI model and tests it end-to-end
./invoke test ai             

# Stubs everything but the firestore db, even running
# the API tests in memory with a firestore backend.
./invoke test firestore

### Flexible Development Workflow
1. **Start with stubbed environment**: `./invoke test unit` (everything mocked)
2. **Add real database**: `./invoke test api` (Firestore real, AI mocked)
3. **Full integration**: `./invoke test integration` (all services real)
4. **Deploy to cloud**: `./invoke deploy` (production environment)

### Configuration-Driven Testing
The `multi_eden.run.config` package automatically:
- Loads the right configuration for each test suite
- Sets up appropriate stubs and providers
- Manages environment variables and secrets
- Handles in-memory vs. external service routing

## Major Value Proposition: Advanced Backend Stubbing

**Focus on Your Application Logic, Not Infrastructure Setup**

Multi-Eden's primary strength is eliminating the complexity of backend service management during development and testing. Instead of spending time configuring databases, AI APIs, and authentication services, you can focus entirely on your application logic.

### In-Memory Database with State Persistence

```python
# Your application code works identically whether using Firestore or TinyDB
from your_app.data import get_user_repository

user_repo = get_user_repository()  # Multi-Eden provides the right implementation
user = user_repo.create_user({"name": "John", "email": "john@example.com"})
user_repo.update_user(user.id, {"last_login": datetime.now()})
```

**With `STUB_DB=true`**:
- Uses **TinyDB in-memory database** that persists state between API calls
- No external database setup required
- Full CRUD operations work exactly like Firestore
- Perfect for unit tests and rapid development

**With `STUB_DB=false`**:
- Uses real Firestore database
- Same application code, different backend
- Ideal for integration testing and production

### Configurable AI Model Responses

```python
# Your AI integration code
from your_app.ai import get_ai_client

ai_client = get_ai_client()
response = ai_client.generate_response("Summarize this document")
```

**With `STUB_AI=true`**:
- Returns **predefined JSON responses** based on test case configurations
- No AI API calls or costs during development
- Deterministic responses for reliable testing
- Configure different response scenarios:

```json
{
  "test_cases": {
    "document_summary": {
      "input_pattern": "*summarize*",
      "response": {
        "summary": "This document discusses project requirements and implementation details.",
        "key_points": ["Requirements analysis", "Technical specifications", "Timeline"],
        "word_count": 1250,
        "confidence": 0.92
      }
    },
    "content_analysis": {
      "input_pattern": "*analyze*",
      "response": {
        "sentiment": "positive",
        "topics": ["technology", "business", "innovation"],
        "complexity_score": 7.5,
        "reading_time": "5 minutes"
      }
    }
  }
}
```

**With `STUB_AI=false`**:
- Makes real calls to Google Gemini API
- Uses your actual API key and quota
- Returns real AI-generated responses

### Development Workflow Benefits

1. **Instant Setup**: `./invoke test unit` - no database installation, no API keys needed
2. **Predictable Testing**: Stubbed responses ensure consistent test results
3. **Cost Control**: No AI API charges during development and testing
4. **Offline Development**: Work without internet connectivity to external services
5. **Rapid Iteration**: Test different scenarios by changing JSON configurations
6. **Gradual Integration**: Start fully stubbed, then enable real services one by one

**Result**: You spend 90% of your time writing application logic, 10% on infrastructure setup.

## Requirements

- Python 3.7+
- Git
- Docker (for containerized workflows)

The `./invoke` script handles all other dependencies automatically.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `./invoke test unit`
5. Submit a pull request

## License

[Add your license information here]
