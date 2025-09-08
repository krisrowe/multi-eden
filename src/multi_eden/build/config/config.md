# Multi-Eden Configuration System

## **System Overview**

The Multi-Eden configuration system provides a unified, inheritance-based approach to managing environment variables across different contexts (development, testing, production). The system uses a single `config.yaml` file with inheritance-based layering, eliminating the need for separate configuration files. The system supports single-profile loading with optional side-loading for specific scenarios.

## **Core Design Principles**

### **Primary Requirements**
1. **Direct pytest execution**: `git clone` → `source venv/bin/activate` → `pytest` should work immediately for unit tests
2. **No complex setup**: Minimal code required in app repos
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
```

**Workflow**:
1. **Clone SDK**: `git clone <sdk-repo>` → `cd multi-eden`
2. **Install**: `make install` → **creates venv, installs dependencies**
3. **Run tests**: `pytest` → **all tests pass, some AI integration tests skipped**
4. **Register secret**: `invoke secrets.set gemini-api-key` → **sets up AI integration**
5. **Run AI tests**: `pytest tests/ai/` → **all tests pass including AI integration**

#### **App Repository**
**Configuration**: `config/app.yaml` with `secrets.manager: "google"` for production
```yaml
id: my-app
secrets:
  manager: "google"  # Use Google Secret Manager for production app
  # Google manager will use project_id from config.yaml or GOOGLE_CLOUD_PROJECT env var
```

**Workflow**:
1. **Clone app**: `git clone <app-repo>` → `cd my-app`
2. **Install**: `make install` → **creates venv, installs dependencies**
3. **Run tests**: `pytest` → **all tests pass, some AI integration tests skipped**
4. **Start API**: `invoke api-start` → **starts local API server**
5. **Run API tests**: `pytest tests/api/ --dproj=local` → **tests against running API**
6. **Build**: `invoke build` → **creates Docker image**
7. **Deploy**: `invoke deploy --target=dev` → **deploys to Google Cloud**

## **Configuration Concepts**

### **Core Terminology**

- **config layer**: A named set of environment variables that may inherit from other layers. Layers are defined in `config.yaml` and can reference secrets, other environment variables, or static values.

- **config profile**: The combined set of environment variables and values for a given top layer that accounts for its inherited layers. This is the resolved configuration after processing all inheritance chains.

- **deployment environment / denv**: A unique alias for an environment, either locally hosted (inside or outside Docker) or hosted in Google Cloud. When not local or local-docker, this is the alias such as `dev` or `prod` for a GCP project ID.

- **config.yaml**: Where config profiles are defined in the SDK. May be extended by app copy but ideally not required. This replaces the previous `environments.yaml` design.

- **.projects**: A file that maps deployment environment names / aliases to GCP project IDs.

- **the --dproj cmd line arg**: Used on either a task or a pytest invocation when PROJECT_ID needs to be set using a project alias (e.g. dev or prod), e.g. when "ai" profile is loaded with a secret reference. Formerly called `--denv`.

- **the --target cmd line arg**: Used for side-loading a deployment profile alongside the main profile, with all variables prefixed with `TARGET_`. Used for API testing and deployment tasks.

- **the --profile cmd line arg**: Required when `@config()` is used without the profile argument. Functions the same as the decorator argument.

- **side-loading**: The process of loading an additional profile alongside the main profile, with all variables from the side-loaded profile prefixed with `TARGET_` to avoid conflicts.

### **Decorator System**

The new decorator will be `@config(profile -> str)` for example `@config("unit")` or `@config("ai")`. This replaces the old `@requires_env_stack` but we will only reference the new name in documentation.

We will not have `--config-env` args, as those are not necessary, and it's old terminology. The config profiles "dev" and "prod" should include PROJECT_ID with a reference to the .projects file and failure to resolve should be caught and presented with clear guidance as a ConfigException.

We will use three command line arguments going forward: `--dproj`, `--target`, and `--profile`.

## **Environment Configuration Structure**

### **Single Source of Truth: config.yaml**

All configuration layers are defined in a single `config.yaml` file with inheritance-based layering:

```yaml
# config/config.yaml
layers:
  # App layer - common application settings
  app:
    env:
      APP_ID: "multi-eden-sdk"
      CUSTOM_AUTH_ENABLED: IN_MEMORY
    
  # Cloud layer - shared cloud configuration
  cloud:
    inherits: "app"
    env:
      STUB_AI: REMOTE
      STUB_DB: REMOTE
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
      GCP_REGION: "us-central1"
      GCP_ZONE: "us-central1-a"
    
  # Unit testing environment
  unit:
    inherits: "app"
    env:
      STUB_AI: IN_MEMORY
      STUB_DB: IN_MEMORY
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"
      TEST_API_MODE: IN_MEMORY
      TEST_OMIT_INTEGRATION: IN_MEMORY
    
  # AI testing environment (minimal - only needs API key)
  ai:
    inherits: "app"
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"
    
  # API testing environment (minimal test configuration)
  api-test:
    inherits: "app"
    env:
      TEST_API_MODE: REMOTE  # Indicates external API testing
    
  # Local development environment
  local:
    inherits: "app"
    env:
      PORT: 8000
      STUB_AI: IN_MEMORY
      STUB_DB: IN_MEMORY
      LOCAL: IN_MEMORY
      GEMINI_API_KEY: "fake-local-gemini-key"
      JWT_SECRET_KEY: "local-jwt-secret"
      ALLOWED_USER_EMAILS: "test-user@static.multi-eden-sdk.app"
    
  # Development environment
  dev:
    inherits: "cloud"
    env:
      PROJECT_ID: "$.projects.dev"
    
  # Production environment
  prod:
    inherits: "cloud"
    env:
      PROJECT_ID: "$.projects.prod"
```


### **Environment Variable Substitution**

The `$.projects.dev` syntax references values from the `.projects` file:

- **.projects file**: Maps environment names to GCP project IDs
- **Command line**: `--dproj=dev` sets `PROJECT_ID` from `.projects.dev`
- **Environment variable**: `export PROJECT_ID=my-project` (direct override)
- **Docker**: `docker run -e PROJECT_ID=my-project my-image`
- **CI/CD**: Set `PROJECT_ID` in pipeline environment variables

If `PROJECT_ID` is not provided, the environment loading will fail with a clear error message:

```
❌ Secret 'gemini-api-key' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify an environment: pytest tests/ai/ --dproj=dev
      (Note: --dproj must be a name found in .projects file that is mapped to a Google Cloud project id
       where gemini-api-key is registered as the name of a secret in Secrets Manager)
```

**⚠️ OPEN ITEM**: The guidance system currently requires mixing context from different levels (profile name, .projects file status, secret availability) to form clear guidance. This may result in kludgey implementation. The ideal solution would centralize all guidance in `load_env` for both pytest and invoke deploy scenarios where `--target` is used. Until this is resolved, guidance may be vague and mention the profile name and need to either configure PROJECT_ID in that profile or set up the expected entry in .projects file.

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
     PROJECT_ID: "$.projects.dev"  # Resolved from .projects file via --dproj=dev
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
    TEST_API_MODE: REMOTE  # Indicates external API testing
```

**What this means:**
- The `api-test` environment provides **minimal test configuration** for API testing
- It sets `TEST_API_MODE: REMOTE` to indicate external API testing (not in-memory)
- Target API configuration comes from side-loaded `TARGET_*` variables via `--target`
- The actual API URL and target settings are constructed by the pytest plugin from side-loaded configuration
- If **secrets** cannot be resolved, `load_env` fails and tests are skipped with guidance
- If **TEST_API_URL** is missing, the API client fixture skips tests with different guidance

**Why api-test is so minimal:**
- **API tests don't use local services** - they test against an external API process
- **No STUB_* settings needed** - the target API has its own service configuration
- **No JWT_SECRET_KEY needed** - the target API has its own auth configuration  
- **Target settings come from side-loading** - `--target=dev` loads the dev profile with `TARGET_` prefix
- **Only test behavior matters** - `TEST_API_MODE: REMOTE` tells pytest to use external API client

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

### **Scenario Overview Table**

| Command | Decorator | Command Line Arg | Arg Need | Required Environment Variables |
|---------|-----------|------------------|----------|-------------------------------|
| `pytest tests/unit/` | None (pytest plugin) | `--dproj` | None | `JWT_SECRET_KEY`, `STUB_AI`, `STUB_DB`, `TEST_API_MODE`, `TEST_OMIT_INTEGRATION` |
| `pytest tests/ai/` | None (pytest plugin) | `--dproj` | Cloud Secrets | `GEMINI_API_KEY` |
| `pytest tests/db/` | None (pytest plugin) | `--dproj` | Cloud Secrets | `PROJECT_ID` |
| `pytest tests/api/` | None (pytest plugin) | `--target` | Side-load | None (small subset of tests may depend on side-loading the profile corresponding to --target to validate target's configuration) |
| `pytest tests/` | None (pytest plugin) | `--dproj --target` | Both | Mixed requirements from different test suites |
| `invoke prompt` | `@config("ai")` | `--dproj` | Cloud Secrets | `GEMINI_API_KEY` |
| `invoke build` | None | None | Not applicable | None (reads registry.project_id from config/app.yaml for docker push destination) |
| `invoke deploy` | None | `--target` | Side-load | `PROJECT_ID`, `GCP_REGION`, `GCP_ZONE`, `STUB_AI`, `STUB_DB`, `JWT_SECRET_KEY`, `ALLOWED_USER_EMAILS` (reads images-denv from app.yaml for docker pull source) |
| `invoke api-start` | `@config("local")` | None | Not applicable | `LOCAL`, `PORT`, `STUB_AI`, `STUB_DB` |
| `invoke token` | `@config()` | `--profile` | Cloud Secrets | `JWT_SECRET_KEY`, `ALLOWED_USER_EMAILS` |
| `invoke py --module="core.api"` | `@config()` | `--profile` | Cloud Secrets | Depends on specified profile |

### **When Both --dproj and --target Are Needed**

Some scenarios require both arguments in the same command:

#### **Mixed Test Suites**
```bash
# Run all tests with both PROJECT_ID resolution and side-loading
pytest tests/ --dproj=dev --target=dev
```

**Why both are needed:**
- **`--dproj=dev`**: Sets `PROJECT_ID` for unit/ai/db tests that need cloud resources
- **`--target=dev`**: Side-loads dev profile for api tests (though api tests don't need PROJECT_ID)

#### **API Tests (Target Configuration Only)**
```bash
# API tests only need target configuration, not PROJECT_ID
pytest tests/api/ --target=dev
```

**Why only --target is needed:**
- **`--target=dev`**: Side-loads target API configuration for testing
- **No PROJECT_ID needed**: API tests don't do local work, just make HTTP calls

#### **Complex Integration Scenarios**
```bash
# Tests that span multiple concerns
pytest tests/integration/ --dproj=dev --target=prod
```

**Why both are needed:**
- **`--dproj=dev`**: Uses dev project for data/cloud resources
- **`--target=prod`**: Tests against prod API configuration

### **Task Decorator Usage**

Tasks use the `@config` decorator with profile specification:

#### **Fixed Profile (For Testing/Development)**
```python
@config("unit")  # Fixed profile
def test_unit(ctx):
    """Run unit tests."""
    # Always loads "unit" profile
```

**Usage**: `invoke test unit` (always uses "unit" profile)

#### **Configurable Profile (For Flexible Tasks)**
```python
@config()  # No default profile
def token(ctx, profile=None):
    """Generate authentication token."""
    # Uses --profile parameter to specify which profile to load
```

**Usage**: 
- `invoke token --profile=ai` (uses "ai" profile)
- `invoke token --profile=local` (uses "local" profile)

### **Task-Specific Decorator Declarations**

Each task has a specific decorator pattern based on its purpose and security requirements:

#### **Testing Tasks (Fixed Profiles)**
```python
# test.py - Fixed testing profile
@config("unit")
def test_unit(ctx):
    """Run unit tests."""
    # Always loads "unit" profile
```

#### **AI Tasks (Fixed AI Profile)**
```python
# prompt.py - AI-specific profile
@config("ai")
def prompt(ctx, prompt_text, model='gemini-2.5-flash', ...):
    """Send a prompt to an AI model."""
    # Always loads "ai" profile

# analyze.py - AI-specific profile
@config("ai")
def analyze(ctx, description, ...):
    """Analyze description with AI."""
    # Always loads "ai" profile
```

#### **Local Development Tasks (Fixed Local Profile)**
```python
# local.py - Fixed local profile
@config("local")
def api_start(ctx, port=None, debug=False):
    """Start local API server."""
    # Always loads "local" profile
```

#### **Deployment Tasks (Default Profile with Override)**
```python
# deploy.py - Default deployment profile
@config("cloud")
def deploy(ctx, profile=None, debug=False):
    """Deploy application to specified environment."""
    # Defaults to "cloud", can override: invoke deploy --profile=dev

# build.py - Default deployment profile
@config("cloud")
def build(ctx, profile=None, debug=False):
    """Build application for development."""
    # Defaults to "cloud", can override: invoke build --profile=dev
```

#### **Utility Tasks (Required Profile)**
```python
# secrets.py tasks - User must specify profile
@config()
def list(ctx, profile=None, ...):
    """List all secrets in the configured store."""
    # User specifies: invoke secrets.list --profile=dev

# docker.py tasks - User must specify profile
@config()
def docker_build(ctx, profile=None, ...):
    """Build local Docker image."""
    # User specifies: invoke docker build --profile=local
```

### **Security Guidelines**

1. **NEVER hardcode production profiles**: Production tasks MUST use dynamic profiles or require explicit --profile
2. **Fixed profiles allowed for non-production**: Development, testing, and local profiles can be fixed
3. **Explicit production specification**: Users must explicitly specify production profiles
4. **Exception-based guidance**: Missing profiles provide helpful, context-aware guidance
5. **Profile validation**: Invalid profiles fail with clear error messages

## **Test System**

### **Single Profile + Side-loading Support**

The test system uses single-profile loading with optional side-loading for specific scenarios:

1. **Single Profile Loading**: Each test suite loads its designated profile (e.g., `unit`, `ai`, `api-test`)
2. **Optional Side-loading**: Some test suites can side-load deployment profiles with `--target`
3. **Environment Variable Override**: `--dproj` can set `PROJECT_ID` for cloud services when needed

This approach provides clean separation between test configuration and deployment environment concerns while allowing flexible testing scenarios.

#### **Rationale for Side-loading**

The primary motivation for side-loading is **configuration clarity and predictability**, not process isolation concerns:

**Configuration Clarity**:
- **Minimal Configuration**: Each task/test suite loads only what it explicitly needs
- **Predictable Behavior**: Settings are only used when explicitly intended
- **Clear Dependencies**: It's obvious which configuration is required for each operation

**Preventing Unexpected Behavior**:
- **No Surprise Settings**: Avoid accidentally using deployment settings in test contexts
- **Explicit Intent**: Side-loading makes it clear when deployment settings are intentionally needed
- **Reduced Cognitive Load**: Developers can reason about what configuration is active

**Example Scenarios**:

```bash
# API tests with side-loading - explicit intent to test against dev deployment
pytest tests/api/ --target=dev
# Result: api-test profile + TARGET_PROJECT_ID, TARGET_STUB_AI, etc. from dev

# API tests without side-loading - pure test configuration only
pytest tests/api/
# Result: api-test profile only - no deployment settings mixed in

# Unit tests - completely isolated, ignores all external arguments
pytest tests/unit/
# Result: unit profile only - all external arguments ignored
```

**Not About Process Conflicts**:
- **Out-of-process Operations**: Docker, gcloud, and API calls run in separate processes
- **Environment Isolation**: Each process gets its own environment variables
- **No Runtime Interference**: The pytest/invoke process doesn't conflict with target processes

The side-loading approach ensures that configuration is **explicit, minimal, and predictable** rather than trying to solve process isolation problems that don't actually exist.

#### **Example: API Tests with Side-loading**

```bash
# Run API tests with side-loaded dev deployment profile
pytest tests/api/ --target=dev
```

**Configuration Flow**:
1. **Main Profile**: Loads `api-test` profile with its inheritance chain:
   - `app` layer → `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY`
   - `api-test` layer → `TEST_API_MODE: REMOTE`
2. **Side-loaded Profile**: Loads `dev` profile with `TARGET_` prefix:
   - `TARGET_PROJECT_ID` from dev (resolved from `.projects` file)
   - `TARGET_STUB_AI: REMOTE`, `TARGET_STUB_DB: REMOTE` from cloud layer
   - `TARGET_GEMINI_API_KEY: "secret:gemini-api-key"` from cloud layer
   - `TARGET_JWT_SECRET_KEY: "secret:jwt-secret-key"` from cloud layer
3. **Combined Result**: Main profile + side-loaded variables:
   - `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY` from app
   - `TEST_API_MODE: REMOTE` from api-test
   - `TARGET_PROJECT_ID` from dev (for API client fixture)
   - `TARGET_STUB_AI: REMOTE`, `TARGET_STUB_DB: REMOTE` from dev
   - `TARGET_GEMINI_API_KEY: "secret:gemini-api-key"` from dev
   - `TARGET_JWT_SECRET_KEY: "secret:jwt-secret-key"` from dev

#### **Example: Database Tests (Direct Service Testing)**

```bash
# Run database tests with project ID for Firestore connection
pytest tests/db/ --dproj=dev
# Result: db-test profile + PROJECT_ID from .projects.dev
```

**Configuration Flow**:
1. **Main Profile**: Loads `db-test` profile with its inheritance chain:
   - `app` layer → `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY`
   - `db-test` layer → `STUB_AI: IN_MEMORY`, `STUB_DB: REMOTE`, `JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"`
2. **Project ID Resolution**: `--dproj=dev` sets `PROJECT_ID` from `.projects.dev`
3. **Combined Result**: Database testing configuration:
   - `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY`
   - `STUB_AI: IN_MEMORY`, `STUB_DB: REMOTE` (real database, stubbed AI)
   - `JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"` (test auth)
   - `PROJECT_ID: "my-dev-project"` (for Firestore connection)

**How Database Tests Work**:
- **Direct Service Testing**: Tests call service classes directly, bypassing API layer
- **Stubbed Services**: AI and other external services are stubbed (`STUB_AI: IN_MEMORY`)
- **Real Database**: Uses actual Firestore (`STUB_DB: REMOTE`)
- **Test Authentication**: Uses mock JWT secret for auth testing
- **Project ID Usage**: Google Firestore client uses `PROJECT_ID` to determine which Firestore instance to connect to

**Project ID Resolution in Code**:
```python
# In service classes (e.g., core/data_providers/firebase_provider.py)
from google.cloud.firestore import Client

class FirebaseDataProvider(DataProvider):
    def __init__(self):
        # Google Cloud client automatically uses PROJECT_ID from environment
        # This comes from our config system via --dproj=dev
        self.db = Client()  # Uses os.environ['PROJECT_ID']
        self.collection_name = "meal_items"
    
    def save_meal_items(self, user_email: str, date: str, items: List[MealItemInput]):
        # Direct Firestore operations - no API layer
        batch = self.db.batch()
        for item_input in items:
            doc_ref = self.db.collection(self.collection_name).document(item_id)
            batch.set(doc_ref, enhanced_data)
        batch.commit()

# In test files (e.g., tests/db/test_firebase_connectivity.py)
def test_firebase_auth_connectivity(self):
    # PROJECT_ID is set by pytest plugin from --dproj=dev
    # Google Firestore client automatically connects to dev project
    from multi_eden.run.auth.testing import ensure_static_firebase_test_user
    token_info = ensure_static_firebase_test_user()
    assert token_info is not None
```

**Guidance Handling**:

**Missing PROJECT_ID**:
```
❌ Secret 'user-data' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify a deployment environment: pytest tests/db/ --dproj=dev
      (Note: --dproj must be a name found in .projects file that is mapped to a Google Cloud project id
       where user-data is registered as the name of a secret in Secrets Manager)
```

**Missing .projects Entry**:
```
❌ Project ID not found for environment 'dev'
💡 The specified environment 'dev' is not found in .projects file. You must do one of the following:
   1. Add entry to .projects file: echo "dev=my-dev-project" >> .projects
   2. Or use a different environment: pytest tests/db/ --dproj=prod
   3. Or set PROJECT_ID directly: export PROJECT_ID=my-dev-project
```

#### **Example: Unit Tests (No Side-loading)**

```bash
# Run unit tests (ignores --dproj and --target)
pytest tests/unit/
```

**Configuration Flow**:
1. **Main Profile**: Loads `unit` profile with its inheritance chain:
   - `app` layer → `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY`
   - `unit` layer → `JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"`, `STUB_AI: IN_MEMORY`, `STUB_DB: IN_MEMORY`, `TEST_API_MODE: IN_MEMORY`, `TEST_OMIT_INTEGRATION: IN_MEMORY`
2. **Result**: Complete unit test environment:
   - `APP_ID: "multi-eden-sdk"`, `CUSTOM_AUTH_ENABLED: IN_MEMORY` from app
   - `JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"` from unit
   - `STUB_AI: IN_MEMORY`, `STUB_DB: IN_MEMORY` from unit
   - `TEST_API_MODE: IN_MEMORY`, `TEST_OMIT_INTEGRATION: IN_MEMORY` from unit

#### **API Client Fixture Logic with Side-loading**

The pytest plugin uses the combined configuration to determine API client behavior:

```python
def api_client_fixture():
    # Check if API tests should run in-memory
    if os.environ.get('TEST_API_MODE', 'REMOTE').lower() == 'IN_MEMORY':
        return create_in_memory_client()
    
    # Check if we have the info needed for remote API testing
    if os.environ.get('TEST_API_URL'):
        return create_remote_client(os.environ['TEST_API_URL'])
    
    # Check if we have local development info
    if os.environ.get('LOCAL') and os.environ.get('PORT'):
        test_api_url = f"http://localhost:{os.environ['PORT']}"
        return create_remote_client(test_api_url)
    
    # Check if we have TARGET_PROJECT_ID for cloud services (from side-loaded profile)
    if os.environ.get('TARGET_PROJECT_ID'):
        # Could construct cloud API URL here
        test_api_url = f"https://api-{os.environ['TARGET_PROJECT_ID']}.run.app"
        return create_remote_client(test_api_url)
    
    # Skip tests that require API client (this is NOT a load_env failure)
    pytest.skip("API client not available - missing LOCAL configuration or TARGET_PROJECT_ID")
```

#### **Auth Token Compatibility Problem**

**⚠️ IMPORTANT NOTE**: API tests that rely on different side-loaded environment variables may face auth token compatibility issues. When testing against a target deployment environment, the test may need to generate auth tokens that are compatible with the target's expected user configuration.

**The Problem**:
- API tests load their own profile (e.g., `api-test`) with test-specific settings
- Target deployment profile is side-loaded with `TARGET_` prefix (e.g., `TARGET_ALLOWED_USER_EMAILS`)
- Auth token generation may need to use the target's user configuration, not the test's configuration

**Potential Solutions** (require further guidance and clear approvals before implementation):
1. **Pytest Plugin Copies Side-loaded Vars**: Copy specific side-loaded variables to main environment (kludgey but simple)
2. **Auth Package Enhancement**: Make auth token generation specific about which user configuration to use
3. **Test-Specific Token Generation**: Allow tests to specify which environment variables to use for token generation

**Current Status**: This problem is identified but not yet resolved. Further analysis and approval needed before any code changes to the test system.

#### **Test Skipping with Guidance**

When tests are skipped due to missing configuration, the pytest plugin provides clear guidance and maintains the existing pytest session footer output:

```python
# Missing PROJECT_ID for Google Cloud services
pytest.skip("""
❌ API tests require PROJECT_ID for Google Cloud services

💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify a deployment environment: pytest tests/api/ --dproj=dev
      (Note: --dproj must be a deployment environment with PROJECT_ID configured)
""")
```

**Pytest Session Footer Output**:
```
❌ 5 tests skipped:
   tests/api/test_billing.py::test_create_invoice - API tests require PROJECT_ID for Google Cloud services
   tests/api/test_billing.py::test_update_invoice - API tests require PROJECT_ID for Google Cloud services
   tests/api/test_billing.py::test_delete_invoice - API tests require PROJECT_ID for Google Cloud services
   tests/api/test_billing.py::test_list_invoices - API tests require PROJECT_ID for Google Cloud services
   tests/api/test_billing.py::test_invoice_validation - API tests require PROJECT_ID for Google Cloud services

💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify a deployment environment: pytest tests/api/ --dproj=dev
      (Note: --dproj must be a deployment environment with PROJECT_ID configured)
```

#### **Implementation Details**

The pytest system is implemented with single-profile loading and optional side-loading:

```python
def pytest_runtest_setup(item):
    """Configure pytest with single profile + optional side-loading."""
    test_file_path = str(item.fspath)
    test_profile = _get_environment_for_test_path(test_file_path)
    
    if test_profile:
        try:
            # Handle --dproj parameter for PROJECT_ID override (only for non-unit tests)
            denv = None
            if test_profile != 'unit':
                if hasattr(item, 'config') and hasattr(item.config, 'getoption'):
                    try:
                        denv = item.config.getoption("--dproj")
                    except:
                        pass
            
            # Handle --target parameter for side-loading
            target_profile = None
            if hasattr(item, 'config') and hasattr(item.config, 'getoption'):
                try:
                    target_profile = item.config.getoption("--target")
                except:
                    pass
            
            # Load the test profile with optional side-loading
            load_env(top_layer=test_profile, fail_on_secret_error=True, target_profile=target_profile)
            
            if denv:
                # Only set PROJECT_ID from .projects file
                project_id = get_project_id_from_projects_file(denv)
                if project_id:
                    os.environ['PROJECT_ID'] = project_id
                else:
                    pytest.skip(f"❌ Environment '{denv}' not found in .projects file")
                        
        except ConfigException as e:
            # Use the exception's built-in guidance
            pytest.skip(f"Test requires {test_profile} environment but configuration is missing: {e.guidance}")
```

**Key Benefits**:
- **Single profile loading**: Clean, simple configuration for most test scenarios
- **Optional side-loading**: Flexible testing against different deployment environments
- **Environment variable override**: `--dproj` provides PROJECT_ID when needed
- **Preserved pytest behavior**: Maintains existing skip reporting and session footer
- **Minimal disruption**: Uses existing `load_env` function with new `target_profile` parameter

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
    # Sets: PROJECT_ID=dev-project
    assert os.environ["PROJECT_ID"] == "dev-project"

# tests/ai/test_gemini.py  
# No markers needed! Environment loaded automatically based on path

def test_ai_prompt():
    # load_env("ai") called automatically
    # Sets: GEMINI_API_KEY=secret123
    assert os.environ["GEMINI_API_KEY"] == "secret123"
```

## **Environment Loading Process**

### **Atomic Four-Phase Loading**

The environment loading system uses a four-phase atomic process to ensure `os.environ` and internal state remain consistent:

```python
def load_env(top_layer: str, target_profile: Optional[str] = None,
             files: Optional[List[str]] = None, force_reload: bool = False, 
             fail_on_secret_error: bool = True) -> Dict[str, Tuple[str, str]]:
    """Load environment with atomic staging/clearing/applying phases and optional side-loading."""
    
    # PHASE 1: STAGING - Load all new values without touching os.environ
    staged_vars = _stage_environment_variables(top_layer, files, fail_on_secret_error)
    
    # PHASE 2: SIDE-LOADING - Load target profile with TARGET_ prefix if specified
    if target_profile:
        target_vars = _stage_environment_variables(target_profile, files, fail_on_secret_error)
        # Add TARGET_ prefix to all target profile variables
        for key, value in target_vars.items():
            staged_vars[f"TARGET_{key}"] = value
    
    # PHASE 3: CLEARING - Remove old variables (only after staging succeeds)
    _clear_previous_variables()
    
    # PHASE 4: APPLYING - Apply all new variables atomically
    _apply_staged_variables(staged_vars)
    _commit_load_state(top_layer, target_profile, files, staged_vars)
    
    return staged_vars
```

### **Two Loading Modes**

#### **Mode 1: `fail_on_secret_error=True` (pytest plugin)**
- **Strict mode**: Fails if any secret cannot be resolved
- **Used by**: pytest plugin for test execution
- **Behavior**: Either all secrets load or none do


### **Environment Isolation**

Each `load_env()` call completely replaces previously loaded variables:

```python
# Call 1: Load "dev" environment
load_env("dev")
# Sets: PROJECT_ID=dev-project

# Call 2: Load "ai" environment  
load_env("ai")
# CLEARS: PROJECT_ID (our previous vars)
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
# config.yaml
layers:
  dev:
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"  # Resolved from secrets manager
      PROJECT_ID: "dev-project"                 # Direct value
      GCP_REGION: "us-central1"               # Direct value
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
   2. Or specify a deployment environment: {command} --dproj=<your-environment>
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
   2. Or specify a deployment environment: {command} --dproj=<your-environment>
      (Note: --dproj must be a deployment environment where {self.secret_name} is registered as the name of a secret in Secrets Manager)
"""

class NoKeyCachedForLocalSecretsException(ConfigException):
    """Raised when local secrets are configured but no key is cached for decryption."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' unavailable because local secrets require a cached decryption key but none is available
💡 You're configured for local secrets manager in app.yaml, therefore, you must do the following:
   1. Set the cached key: invoke secrets.set-cached-key --passphrase="your-passphrase"
   2. Validate the secret is accessible: invoke secrets.get {self.secret_name}
"""

class LocalSecretNotFoundException(ConfigException):
    """Raised when local secrets are accessible but the specific secret is not found."""
    def __init__(self, message: str, secret_name: str, **kwargs):
        super().__init__(message, secret_name=secret_name, **kwargs)

    def _generate_guidance(self):
        return f"""
❌ Secret '{self.secret_name}' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set {self.secret_name}
   2. Or check if secret exists: invoke secrets.list
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
   1. Set the secret: invoke secrets.set {self.secret_name} --dproj={env_name}
   2. Or check if secret exists: invoke secrets.list --dproj={env_name}
      (Note: --dproj must be a deployment environment where {self.secret_name} is registered as the name of a secret in Secrets Manager)
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
   1. Set the cached key: invoke secrets.set-cached-key --passphrase="your-passphrase"
   2. Validate the secret is accessible: invoke secrets.get gemini-api-key

# Missing secret in local file
❌ Secret 'gemini-api-key' not found in local secrets file
💡 You're configured for local secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set gemini-api-key
   2. Or check if secret exists: invoke secrets.list
```

#### **Google Secrets Manager (App Development)**
```bash
# Missing PROJECT_ID for Google secrets
❌ Secret 'gemini-api-key' unavailable because Google Secret Manager is used per app.yaml and no PROJECT_ID is available
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify a deployment environment: pytest tests/ai/ --dproj=dev
      (Note: --dproj must be a deployment environment where gemini-api-key is registered as the name of a secret in Secrets Manager)

# Missing secret in Google Secret Manager
❌ Secret 'gemini-api-key' not found in Google Secret Manager
💡 You're configured for Google secrets manager in app.yaml, therefore, you must do one of the following:
   1. Set the secret: invoke secrets.set gemini-api-key --dproj=dev
   2. Or check if secret exists: invoke secrets.list --dproj=dev
      (Note: --dproj must be a deployment environment where gemini-api-key is registered as the name of a secret in Secrets Manager)
```

#### **Direct Google Cloud Service Calls**
```bash
# Missing PROJECT_ID for direct Google Cloud services (not secret-related)
❌ Project ID required for Google Cloud services
💡 Resolve this in one of the following ways:
   1. Set PROJECT_ID environment variable: export PROJECT_ID=your-project
   2. Or specify a deployment environment: invoke test db --dproj=dev
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
2. **`config/config.yaml`** - Configuration layer definitions
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

## **Future Enhancements**

### **Layer-Level Default Arguments**

A future enhancement would allow specifying default `dproj` or `target` properties at the layer level in `config.yaml`, eliminating the need to pass `--dproj` or `--target` arguments to pytest or invoke commands.

#### **Proposed Configuration Structure**

```yaml
# config/config.yaml
layers:
  app:
    env:
      APP_ID: "multi-eden-sdk"
      CUSTOM_AUTH_ENABLED: IN_MEMORY
  
  cloud:
    inherits: "app"
    env:
      STUB_AI: REMOTE
      STUB_DB: REMOTE
      GEMINI_API_KEY: "secret:gemini-api-key"
      JWT_SECRET_KEY: "secret:jwt-secret-key"
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"
      GCP_REGION: "us-central1"
      GCP_ZONE: "us-central1-a"
  
  # Test layers with defaults
  ai:
    inherits: "app"
    default_dproj: "dev"  # Default project for AI tests
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"
  
  db-test:
    inherits: "app"
    default_dproj: "dev"  # Default project for database tests
    env:
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"
      STUB_AI: IN_MEMORY
      STUB_DB: REMOTE
  
  api-test:
    inherits: "app"
    default_target: "dev"  # Default target for API tests
    env:
      TEST_API_MODE: REMOTE
  
  # Deployment layers (no defaults needed)
  dev:
    inherits: "cloud"
    env:
      PROJECT_ID: "$.projects.dev"
  
  prod:
    inherits: "cloud"
    env:
      PROJECT_ID: "$.projects.prod"
```

#### **Benefits**

1. **Simplified Commands**: 
   - `pytest tests/` instead of `pytest tests/ --dproj=dev --target=dev`
   - `invoke deploy` instead of `invoke deploy --target=prod`

2. **Environment-Specific Defaults**:
   - Development environments default to `dev` project
   - Production environments default to `prod` project
   - API tests automatically get appropriate target configuration

3. **App-Level Customization**:
   - Apps can override SDK defaults in their own `config.yaml`
   - Different apps can have different default behaviors
   - Maintains backward compatibility with explicit arguments

4. **Reduced Cognitive Load**:
   - Developers don't need to remember which arguments to use
   - Commands work out-of-the-box with sensible defaults
   - Explicit arguments still override defaults when needed

#### **Implementation Considerations**

- **Backward Compatibility**: Explicit `--dproj` and `--target` arguments override layer defaults
- **Inheritance**: Child layers inherit parent defaults unless overridden
- **Validation**: Ensure default values exist in `.projects` file
- **Documentation**: Clear precedence rules for defaults vs. explicit arguments
