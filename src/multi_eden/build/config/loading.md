# Multi-Eden Environment Configuration System

## **System Overview**

The Multi-Eden environment configuration system provides a unified, inheritance-based approach to managing environment variables across different contexts (development, testing, production). The system uses a single `environments.yaml` file with inheritance-based layering, eliminating the need for separate configuration files.

## **Core Design Principles**

### **Primary Requirements**
1. **Direct pytest execution**: `git clone` → `source venv/bin/activate` → `pytest` should work immediately for unit tests
2. **No complex setup**: Minimal code required in app repos (like `~/ai-food-log`)
3. **Environment isolation**: Different test suites ran in the same session can load different environments without conflicts
4. **Secret caching**: Expensive secret resolution happens once per process / pytest session
5. **Clean reloading**: Track what we load so we can reload different configurations
6. **Exception-based guidance**: Users get helpful, context-aware messages when configurations are missing
7. **No backward compatibility**: Clean break from old system, build it right from the start
8. **Minimal app configuration**: Allow apps to configure nothing but project IDs if desired, keeping project ID definition as easy as possible while allowing all other app-level configuration to be version controlled safely
9. **Declarative test environments**: Make it as easy as possible to define which tests need which environment layers, with automatic loading all via a simple `pytest` command without sdk-specific arguments, and provide clear reporting on skipped integration tests when local configuration is insufficient, with detailed guidance wtih options for enabling integration tests not to be skipped that accounts for how the repo where tests are being run is currently configured
10. **Atomic environment loading**: Environment loading must be atomic - either ALL variables load successfully or NONE are applied. No partial state where `os.environ` and global tracking are out of sync.

### **User Experience Goals**

#### **SDK Repository (multi-eden)**
**Configuration**: `config/app.yaml` with `secrets.manager: "local"` for development
```yaml
id: "multi-eden-sdk"
secrets:
  manager: "local"  # Use local for SDK testing to avoid GCP dependency
  file: ".secrets"  # Path to encrypted secrets file
```

**Workflow**:
1. **Clone SDK**: `git clone <sdk-repo>` → `cd multi-eden`
2. **Activate environment**: `source venv/bin/activate`
3. **Run unit tests**: `pytest tests/unit` → **works immediately** (no secrets needed)
4. **Run AI tests**: `pytest tests/ai` → **guided to set up secrets**:
   ```
   ❌ Secret 'gemini-api-key' not found in local secrets file
   💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
      1. Set the secret: invoke secrets set gemini-api-key
      2. Or check if secret exists: invoke secrets list
   ```
5. **Run integration tests**: `pytest tests/integration` → **works if PROJECT_ID configured**
6. **Task execution**: `invoke prompt "hello" --config-env=ai` → **works with AI environment loaded**

#### **App Repository (e.g., ~/ai-food-log)**
**Configuration**: `config/app.yaml` with `secrets.manager: "google"` for production
```yaml
id: ai-food-log
secrets:
  manager: "google"  # Use Google Secret Manager for production app
  # Google manager will use project_id from environments.yaml or GOOGLE_CLOUD_PROJECT env var
```

**Workflow**:
1. **Clone app**: `git clone <app-repo>` → `cd ai-food-log`
2. **Activate environment**: `source venv/bin/activate`
3. **Run tests**: `pytest` → **works with appropriate environments loaded automatically**
4. **Deploy**: `invoke deploy --config-env=prod` → **requires explicit environment specification**

## **Environment Configuration Structure**

### **Single Source of Truth: environments.yaml**

All environment configurations are defined in a single `environments.yaml` file with inheritance-based layering:

```yaml
# config/environments.yaml
environments:
  # App layer - common application settings
  app:
    env:
      APP_ID: "multi-eden-sdk"
      LOG_LEVEL: "INFO"
      CUSTOM_AUTH_ENABLED: true
    
  # Unit testing environment
  unit:
    inherits: "app"
    env:
      STUB_AI: true
      STUB_DB: true
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"
      TEST_API_IN_MEMORY: true
      TEST_OMIT_INTEGRATION: true
    
  # AI testing environment (minimal - only needs API key)
  ai:
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"
    
  # API testing environment (requires PROJECT_ID to be provided externally)
  api-test:
    inherits: "app"
    env:
      PROJECT_ID: "${PROJECT_ID}"  # Must be provided via command line or environment variable
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
    
  # Integration testing environment
  integration-test:
    inherits: "app"
    env:
      PROJECT_ID: "${PROJECT_ID}"  # Must be provided via command line or environment variable
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
      INTEGRATION_TEST_MODE: true
    
  # Local development environment
  local:
    inherits: "app"
    env:
      PORT: 8000
      STUB_AI: true
      STUB_DB: true
      LOCAL: true
      GEMINI_API_KEY: "fake-local-gemini-key"
      JWT_SECRET_KEY: "local-jwt-secret"
      ALLOWED_USER_EMAILS: "test-user@static.multi-eden-sdk.app"
    
  # Development environment
  dev:
    inherits: "app"
    env:
      PROJECT_ID: "dev-project"
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
    
  # Production environment
  prod:
    inherits: "app"
    env:
      PROJECT_ID: "prod-project"
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
```

### **Complete SDK environments.yaml Reference**

The following is the complete `environments.yaml` file that should be provided out-of-the-box with the Multi-Eden SDK:

```yaml
# config/environments.yaml - Complete SDK Default Configuration
environments:
  # Base application layer - common settings for all environments
  app:
    env:
      APP_ID: "multi-eden-sdk"
      LOG_LEVEL: "INFO"
      CUSTOM_AUTH_ENABLED: true
      DEBUG: false
      ENVIRONMENT: "unknown"
  
  # Unit testing environment - fully mocked, no external dependencies
  unit:
    inherits: "app"
    env:
      ENVIRONMENT: "unit"
      STUB_AI: true
      STUB_DB: true
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"
      TEST_API_IN_MEMORY: true
      TEST_OMIT_INTEGRATION: true
      GEMINI_API_KEY: "fake-unit-gemini-key"
      PROJECT_ID: "test-project"
    
  # AI testing environment - minimal configuration for AI functionality
  ai:
    env:
      ENVIRONMENT: "ai"
      GEMINI_API_KEY: "secret:gemini-api-key"
      AI_MODEL: "gemini-2.5-flash"
      AI_MAX_TOKENS: 1000
      AI_TEMPERATURE: 0.7
    
  # API testing environment - requires PROJECT_ID to be provided externally
  api-test:
    inherits: "app"
    env:
      ENVIRONMENT: "api-test"
      PROJECT_ID: "${PROJECT_ID}"  # Must be provided via command line or environment variable
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
      API_TIMEOUT: 30
      API_RETRY_ATTEMPTS: 3
    
  # Local development environment - fully local, no external dependencies
  local:
    inherits: "app"
    env:
      ENVIRONMENT: "local"
      PORT: 8000
      STUB_AI: true
      STUB_DB: true
      LOCAL: true
      DEBUG: true
      GEMINI_API_KEY: "fake-local-gemini-key"
      JWT_SECRET_KEY: "local-jwt-secret"
      ALLOWED_USER_EMAILS: "test-user@static.multi-eden-sdk.app"
      PROJECT_ID: "local-project"
      DATABASE_URL: "sqlite:///local.db"
  
  # Development environment - uses real services with dev project
  dev:
    inherits: "app"
    env:
      ENVIRONMENT: "dev"
      PROJECT_ID: "dev-project"
      STUB_AI: false
      STUB_DB: false
      DEBUG: true
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
      DATABASE_URL: "secret:dev-database-url"
      REDIS_URL: "secret:dev-redis-url"
    
  # Staging environment - pre-production testing
  staging:
    inherits: "app"
    env:
      ENVIRONMENT: "staging"
      PROJECT_ID: "staging-project"
      STUB_AI: false
      STUB_DB: false
      DEBUG: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:staging-allowed-user-emails"
      DATABASE_URL: "secret:staging-database-url"
      REDIS_URL: "secret:staging-redis-url"
    
  # Production environment - live production system
  prod:
    inherits: "app"
    env:
      ENVIRONMENT: "prod"
      PROJECT_ID: "prod-project"
      STUB_AI: false
      STUB_DB: false
      DEBUG: false
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:prod-allowed-user-emails"
      DATABASE_URL: "secret:prod-database-url"
      REDIS_URL: "secret:prod-redis-url"
      LOG_LEVEL: "WARNING"  # Override app layer for production
```

### **Environment Variable Substitution**

The `${PROJECT_ID}` syntax indicates that the value must be provided externally:

- **Command line**: `PROJECT_ID=my-project invoke test api-test`
- **Environment variable**: `export PROJECT_ID=my-project && pytest tests/api/`
- **Docker**: `docker run -e PROJECT_ID=my-project my-image`
- **CI/CD**: Set `PROJECT_ID` in pipeline environment variables

If `PROJECT_ID` is not provided, the environment loading will fail with a clear error message:

```
❌ Secret 'gemini-api-key' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: pytest tests/api/ --env-name=<your-environment>
      (Note: --env-name must be a name found in .projects file that is mapped to a Google Cloud project id
       where gemini-api-key is registered as the name of a secret in Secrets Manager)
```

## **Layering Load Framework**

### **Environment Variable Declaration Philosophy**

The layering load framework operates on a **declaration-based model** where each environment layer explicitly declares what variables it requires, regardless of whether it provides the values itself.

#### **Variable Declaration Types**

1. **Value-Provided Variables**: The layer provides both the declaration and the value
   ```yaml
   env:
     LOG_LEVEL: "INFO"  # Declares LOG_LEVEL and provides value
     PORT: 8000         # Declares PORT and provides value
   ```

2. **Value-Required Variables**: The layer declares the variable but requires external provision
   ```yaml
   env:
     PROJECT_ID: "${PROJECT_ID}"  # Declares PROJECT_ID as required, no value provided
     API_KEY: "${API_KEY}"        # Declares API_KEY as required, no value provided
   ```

3. **Secret-Required Variables**: The layer declares the variable but requires secret resolution
   ```yaml
   env:
     GEMINI_API_KEY: "secret:gemini-api-key"  # Declares variable, requires secret resolution
     JWT_SECRET: "secret:jwt-secret"          # Declares variable, requires secret resolution
   ```

#### **Load Framework Behavior**

The framework treats all variable declarations equally - each represents a **contract** that the environment layer requires:

- **Success Condition**: All declared variables must be resolvable (have values or secrets available)
- **Failure Condition**: Any declared variable cannot be resolved → entire load fails
- **Atomic Loading**: Either all variables load successfully or none are applied

#### **Example: api-test Environment**

```yaml
api-test:
  inherits: "app"
  env:
    # Value-Provided Variables (inherited from app + local overrides)
    ENVIRONMENT: "api-test"
    STUB_AI: false
    STUB_DB: false
    
    # Value-Required Variables (declared but must be provided externally)
    PROJECT_ID: "${PROJECT_ID}"  # Declaration: "I need PROJECT_ID"
    # API_URL is constructed from PROJECT_ID, not declared as a separate variable
    
    # Secret-Required Variables (declared but must be resolved from secrets)
    GEMINI_API_KEY: "secret:gemini-api-key"  # Declaration: "I need GEMINI_API_KEY"
    JWT_SECRET_KEY: "secret:jwt-secret-key"  # Declaration: "I need JWT_SECRET_KEY"
```

**What this means:**
- The `api-test` environment **declares** that it needs `PROJECT_ID`, `GEMINI_API_KEY`, and `JWT_SECRET_KEY`
- It does **not** provide a value for `PROJECT_ID` - this must come from external sources
- It does **not** provide values for `GEMINI_API_KEY` or `JWT_SECRET_KEY` - these must be resolved from secrets
- If **any** of these cannot be resolved, the entire environment load fails

#### **Load Failure Scenarios**

```bash
# Scenario 1: Missing required environment variable
PROJECT_ID=my-project invoke test api-test
# ✅ Success: PROJECT_ID provided, secrets resolved

# Scenario 2: Missing required environment variable  
invoke test api-test
# ❌ Failure: PROJECT_ID not provided
# Error: Secret 'gemini-api-key' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available

# Scenario 3: Missing required secret
PROJECT_ID=my-project invoke test api-test
# ❌ Failure: GEMINI_API_KEY secret not found
# Error: Secret 'gemini-api-key' not found in Google Secret Manager

# Scenario 4: All requirements met
PROJECT_ID=my-project invoke test api-test
# ✅ Success: All declared variables resolved
```

#### **Framework Benefits**

1. **Explicit Contracts**: Each environment layer clearly declares its requirements
2. **Fail-Fast Behavior**: Missing requirements cause immediate, clear failures
3. **No Silent Failures**: The framework never loads partial configurations
4. **Clear Error Messages**: Users get specific guidance on what's missing
5. **Atomic Loading**: Environment state is always consistent

This declaration-based approach ensures that environment loading is predictable, secure, and provides clear feedback when requirements are not met.

### **Environment Inheritance Rules**

1. **App Layer**: Common application settings, not all environments need to inherit from it
2. **Minimal Environments**: Some environments (like `ai`) only need specific variables
3. **Override Behavior**: Child environments override parent values
4. **Secret Resolution**: Secrets are resolved using the configured secrets manager
5. **Project ID**: Cloud environments can specify `project_id` for secret resolution

## **Task System**

### **Task Decorator Usage**

Tasks use the `@requires_env_stack` decorator with flexible environment specification:

#### **Dynamic Environment (Required for Production)**
```python
@requires_env_stack()  # No hardcoded environment
def deploy(ctx, config_env=None, debug=False):
    """Deploy application to specified environment."""
    # Environment loaded from config_env parameter
```

**Usage**: `invoke deploy --config-env=prod` (explicit environment required)

#### **Default Environment (For Development/Testing)**
```python
@requires_env_stack("dev")  # Default environment
def build(ctx, config_env=None, debug=False):
    """Build application for development."""
    # Environment defaults to "dev", can be overridden with --config-env
```

**Usage**: 
- `invoke build` (uses default "dev" environment)
- `invoke build --config-env=staging` (overrides to "staging" environment)

### **Task-Specific Decorator Declarations**

Each task has a specific decorator pattern based on its purpose and security requirements:

#### **Production Tasks (Must Use Dynamic)**
```python
# deploy.py - CRITICAL: Never hardcode production
@requires_env_stack()
def deploy(ctx, config_env=None, debug=False):
    """Deploy application to specified environment."""
    # User MUST specify: invoke deploy --config-env=prod
```

#### **Development Tasks (Can Use Defaults)**
```python
# build.py - Safe to default to dev
@requires_env_stack("dev")
def build(ctx, config_env=None, debug=False):
    """Build application for development."""
    # Defaults to dev, can override: invoke build --config-env=staging

# api_start.py - Safe to default to local
@requires_env_stack("local")
def api_start(ctx, port=None, config_env=None, debug=False):
    """Start local API server."""
    # Defaults to local, can override: invoke api-start --config-env=dev
```

#### **AI Tasks (Can Use Defaults)**
```python
# prompt.py - Safe to default to ai
@requires_env_stack("ai")
def prompt(ctx, prompt_text, config_env=None, model='gemini-2.5-flash', ...):
    """Send a prompt to an AI model."""
    # Defaults to ai, can override: invoke prompt "hello" --config-env=dev

# analyze.py - Safe to default to ai
@requires_env_stack("ai")
def analyze(ctx, food_description, config_env=None, ...):
    """Analyze food description with AI."""
    # Defaults to ai, can override: invoke analyze "chicken" --config-env=dev
```

#### **Utility Tasks (Can Use Defaults)**
```python
# secrets.py tasks - Safe to use dynamic
@requires_env_stack()
def list(ctx, config_env=None, ...):
    """List all secrets in the configured store."""
    # User specifies: invoke secrets list --config-env=dev

# docker.py tasks - Safe to use dynamic
@requires_env_stack()
def docker_build(ctx, config_env=None, ...):
    """Build local Docker image."""
    # User specifies: invoke docker build --config-env=local
```

### **Security Guidelines**

1. **NEVER hardcode production environments**: Production tasks MUST use dynamic environments
2. **Default environments allowed for non-production**: Development, testing, and local environments can have defaults
3. **Explicit production specification**: Users must explicitly specify production environments
4. **Exception-based guidance**: Missing environments provide helpful, context-aware guidance
5. **Environment validation**: Invalid environments fail with clear error messages

## **Test System**

### **Complete SDK tests.yaml Reference**

The following is the complete `tests.yaml` file that should be provided out-of-the-box with the Multi-Eden SDK:

```yaml
# tests.yaml - Complete SDK Test Configuration
# Path-based environment mapping for pytest (automatic environment loading)
paths:
  "tests/unit/": "unit"
  "tests/ai/": "ai"
  "tests/api/": "api-test"
  "tests/providers/": "unit"

# Suite-based configuration for invoke test [suite] commands
suites:
  unit:
    description: "Unit tests with mocked dependencies - no external services required"
    env: "unit"
    tests:
      - "tests/unit"
      - "tests/providers"
    
  ai:
    description: "AI integration tests with real API calls - requires GEMINI_API_KEY"
    env: "ai"
    tests:
      - "tests/ai"
    
  api:
    description: "API tests via HTTP - requires PROJECT_ID and secrets"
    env: "api-test"
    tests:
      - "tests/api"
      - "tests/providers"
    
```

### **Test Execution Modes**

#### **Direct pytest execution** (uses path mapping)
```bash
pytest tests/unit/          # Loads 'unit' environment
pytest tests/ai/            # Loads 'ai' environment  
pytest tests/api/           # Loads 'api-test' environment
pytest                      # Loads appropriate environment per test file
```

#### **Suite-based execution** (uses suite configuration)
```bash
invoke test unit            # Runs tests/unit/ and tests/providers/ with 'unit' environment
invoke test ai              # Runs tests/ai/ with 'ai' environment
invoke test api             # Runs tests/api/ and tests/providers/ with 'api-test' environment
```

### **Pytest Plugin for Automatic Environment Loading**

The pytest plugin automatically loads environments based on test file paths:

**File**: `src/multi_eden/pytest_plugin.py`

```python
def pytest_runtest_setup(item):
    """Load environment based on test file path."""
    test_file_path = str(item.fspath)
    env_layer = _get_environment_for_test_path(test_file_path)
    
    if env_layer:
        try:
            load_env(top_layer=env_layer, fail_on_secret_error=True)
        except ConfigException as e:
            pytest.skip(f"Test requires {env_layer} environment but configuration is missing: {e.guidance}")
```

**Path Mapping Logic**:
- `tests/unit/` → loads `unit` environment
- `tests/ai/` → loads `ai` environment  
- `tests/api/` → loads `api-test` environment
- `tests/providers/` → loads `unit` environment

### **Test Execution Modes**

#### **Direct pytest execution** (uses path mapping)
```bash
pytest tests/unit/          # Loads 'unit' environment
pytest tests/ai/            # Loads 'ai' environment
pytest tests/api/           # Loads 'api-test' environment
pytest                      # Loads appropriate environment per test file
```

#### **Suite-based execution** (uses suite configuration)
```bash
invoke test unit            # Runs tests/unit/ and tests/providers/ with 'unit' environment
invoke test ai              # Runs tests/ai/ with 'ai' environment
invoke test api             # Runs tests/api/ and tests/providers/ with 'api-test' environment
```

### **Test Examples**

```python
# tests/api/test_billing.py
# No markers needed! Environment loaded automatically based on path

def test_create_invoice():
    # load_env("api-test") called automatically
    # Sets: PROJECT_ID=dev-project, API_URL=https://api.dev.com
    assert os.environ["PROJECT_ID"] == "dev-project"

# tests/ai/test_gemini.py  
# No markers needed! Environment loaded automatically based on path

def test_ai_prompt():
    # load_env("ai") called automatically
    # Sets: GEMINI_API_KEY=secret123
    assert os.environ["GEMINI_API_KEY"] == "secret123"
```

## **Environment Loading Process**

### **Atomic Three-Phase Loading**

The environment loading system uses a three-phase atomic process to ensure `os.environ` and internal state remain consistent:

```python
def load_env(top_layer: str, base_layer: Optional[str] = None, 
             files: Optional[List[str]] = None, force_reload: bool = False, 
             fail_on_secret_error: bool = True) -> Dict[str, Tuple[str, str]]:
    """Load environment with atomic staging/clearing/applying phases."""
    
    # PHASE 1: STAGING - Load all new values without touching os.environ
    staged_vars = _stage_environment_variables(top_layer, base_layer, files, fail_on_secret_error)
    
    # PHASE 2: CLEARING - Remove old variables (only after staging succeeds)
    _clear_previous_variables()
    
    # PHASE 3: APPLYING - Apply all new variables atomically
    _apply_staged_variables(staged_vars)
    _commit_load_state(top_layer, base_layer, files, staged_vars)
    
    return staged_vars
```

### **Two Loading Modes**

#### **Mode 1: `fail_on_secret_error=True` (pytest plugin)**
- **Strict mode**: Fails if any secret cannot be resolved
- **Used by**: pytest plugin for test execution
- **Behavior**: Either all secrets load or none do

#### **Mode 2: `fail_on_secret_error=False` (task mode)**
- **Permissive mode**: Skips failed secrets, continues with others
- **Used by**: invoke tasks for development workflow
- **Behavior**: Loads available secrets, skips unavailable ones

### **Environment Isolation**

Each `load_env()` call completely replaces previously loaded variables:

```python
# Call 1: Load "dev" environment
load_env("dev")
# Sets: PROJECT_ID=dev-project, API_URL=https://api.dev.com

# Call 2: Load "ai" environment  
load_env("ai")
# CLEARS: PROJECT_ID, API_URL (our previous vars)
# Sets: GEMINI_API_KEY=secret123, AI_MODEL=gemini-2.5-flash
```

## **Secret Management**

### **Secret Resolution**

Secrets are resolved using the configured secrets manager:

```yaml
# config/app.yaml
secrets:
  manager: "local"  # or "google"
  file: ".secrets"  # for local manager
```

### **Secret Caching**

- **Process-level caching**: Secrets loaded once per process
- **Automatic invalidation**: Cache cleared on environment reload
- **Performance optimization**: Expensive secret resolution happens once

### **Secret Examples**

```yaml
# environments.yaml
environments:
  dev:
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"  # Resolved from secrets manager
      PROJECT_ID: "dev-project"                 # Direct value
      API_URL: "https://api.dev.com"           # Direct value
```

## **Exception-Based Guidance System**

### **Exception Classes with Built-in Guidance**

The system uses strongly-typed exceptions that carry their own guidance messages, eliminating the need for separate guidance generation functions:

```python
# src/multi_eden/build/config/exceptions.py
import sys

class ConfigException(Exception):
    """Base exception for all configuration errors."""
    def __init__(self, message: str, error_type: str = None, provider: str = None, 
                 secret_name: str = None, env_name: str = None, variable_name: str = None):
        super().__init__(message)
        self.error_type = error_type
        self.provider = provider
        self.secret_name = secret_name
        self.env_name = env_name
        self.variable_name = variable_name
        self.guidance = self._generate_guidance()

    def _get_current_command(self):
        """Get the current command being executed."""
        if len(sys.argv) > 0:
            return ' '.join(sys.argv)
        return "unknown command"

    def _generate_guidance(self):
        """Override in subclasses to provide specific guidance."""
        return f"""
❌ Configuration error: {self}
💡 Check your configuration and try again
"""

class ProjectIdRequiredException(ConfigException):
    """Raised when PROJECT_ID is required for Google Cloud services but not available."""
    def __init__(self, message: str, service_type: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.service_type = service_type

    def _generate_guidance(self):
        command = self._get_current_command()
        return f"""
❌ Project ID required for Google Cloud services
💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: {command} --env-name=<your-environment>
"""

class NoProjectIdForGoogleSecretsException(ConfigException):
    """Raised when Google Secret Manager is configured but PROJECT_ID is missing."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        command = self._get_current_command()
        return f"""
❌ Secret '{self.secret_name}' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: {command} --env-name=<your-environment>
      (Note: --env-name must be a name found in .projects file that is mapped to a Google Cloud project id
       where {self.secret_name} is registered as the name of a secret in Secrets Manager)
"""

class NoKeyCachedForLocalSecretsException(ConfigException):
    """Raised when local secrets are configured but no key is cached for decryption."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' unavailable because local secrets require a cached decryption key but none is available
💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
   1. Set the cached key: invoke secrets set-cached-key
   2. Validate the secret is accessible: invoke secrets get {self.secret_name}
"""

class LocalSecretNotFoundException(ConfigException):
    """Raised when local secrets are accessible but the specific secret is not found."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets set {self.secret_name}
   2. Or check if secret exists: invoke secrets list
"""

class GoogleSecretNotFoundException(ConfigException):
    """Raised when Google Secret Manager is accessible but the specific secret is not found."""
    def __init__(self, message: str, secret_name: str, env_name: str = None, **kwargs):
        super().__init__(message, secret_name=secret_name, env_name=env_name, **kwargs)

    def _generate_guidance(self):
        command = self._get_current_command()
        env_name = self.env_name or '<your-environment>'
        return f"""
❌ Secret '{self.secret_name}' not found in Google Secret Manager
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets set {self.secret_name} --env-name={env_name}
   2. Or check if secret exists: invoke secrets list --env-name={env_name}
      (Note: --env-name must be a name found in .projects file that is mapped to a Google Cloud project id
       where {self.secret_name} is registered as the name of a secret in Secrets Manager)
"""
```

### **Usage Examples**

```python
# In pytest plugin:
try:
    load_env(top_layer="ai", fail_on_secret_error=True)
except ConfigException as e:
    pytest.skip(f"Test requires ai environment but configuration is missing: {e.guidance}")

# In invoke tasks:
try:
    load_env(top_layer="ai", fail_on_secret_error=True)
except ConfigException as e:
    print(e.guidance)  # Exception handles everything, including command detection

# In secrets tasks:
try:
    load_env(top_layer="ai", fail_on_secret_error=True)
except ConfigException as e:
    print(e.guidance)  # Works for any config exception
```

### **Guidance Message Examples**

#### **Local Secrets Manager (SDK Development)**
```bash
# Missing cached key for local secrets
❌ Secret 'gemini-api-key' unavailable because local secrets require a cached decryption key but none is available
💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
   1. Set the cached key: invoke secrets set-cached-key
   2. Validate the secret is accessible: invoke secrets get gemini-api-key

# Missing secret in local file
❌ Secret 'gemini-api-key' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets set gemini-api-key
   2. Or check if secret exists: invoke secrets list
```

#### **Google Secrets Manager (App Development)**
```bash
# Missing PROJECT_ID for Google secrets
❌ Secret 'gemini-api-key' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: pytest tests/ai/ --env-name=<your-environment>
      (Note: --env-name must be a name found in .projects file that is mapped to a Google Cloud project id
       where gemini-api-key is registered as the name of a secret in Secrets Manager)

# Missing secret in Google Secret Manager
❌ Secret 'gemini-api-key' not found in Google Secret Manager
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets set gemini-api-key --env-name=dev
   2. Or check if secret exists: invoke secrets list --env-name=dev
      (Note: --env-name must be a name found in .projects file that is mapped to a Google Cloud project id
       where gemini-api-key is registered as the name of a secret in Secrets Manager)
```

#### **Direct Google Cloud Service Calls**
```bash
# Missing PROJECT_ID for direct Google Cloud services (not secret-related)
❌ Project ID required for Google Cloud services
💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: invoke test db --env-name=<your-environment>
```

### **Key Benefits**

1. **Self-contained exceptions**: Each exception carries its own guidance
2. **Automatic command detection**: No need to pass command context around
3. **Provider-aware guidance**: Different messages for local vs Google providers
4. **Context-aware**: Guidance adapts to the specific error and configuration
5. **Consistent interface**: All exceptions have the same `guidance` property
6. **No parameter passing**: Simple usage - just catch and print `e.guidance`

## **Configuration Files**

### **Required Files**

1. **`config/app.yaml`** - Application configuration
2. **`config/environments.yaml`** - Environment definitions
3. **`tests.yaml`** - Test suite and path configuration

### **Optional Files**

1. **`.secrets`** - Local encrypted secrets file
2. **`pytest.ini`** - Pytest configuration (auto-generated)

## **Migration Guide**

### **From Old System**

1. **Remove old files**: Delete `loading.yaml` (no longer needed)
2. **Update tests.yaml**: Use new structure with `paths` and `suites` sections
3. **Update tasks**: Use appropriate decorator patterns based on security requirements
4. **Update tests**: Remove manual environment loading, rely on path-based loading

### **Best Practices**

1. **Use dynamic environments for production**: Never hardcode production environments
2. **Use default environments for development**: Convenient defaults for non-critical tasks
3. **Clear naming**: Use descriptive environment names (`dev`, `staging`, `prod`)
4. **Minimal configuration**: Start with app layer, add only necessary overrides
5. **Secret security**: Never commit secrets to version control

## **Performance Characteristics**

- **Secret caching**: Expensive operations happen once per process
- **Atomic loading**: No partial state corruption
- **Environment isolation**: Clean state between different test suites
- **Minimal overhead**: Simple inheritance-based configuration
- **Fast reloading**: Track loaded variables for efficient clearing

This system provides a robust, secure, and user-friendly approach to environment configuration that scales from simple development setups to complex production deployments.
