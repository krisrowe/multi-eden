# Multi-Eden Environment Configuration Refactoring Plan

## **Design Goals**

### **Primary Requirements**
1. **Direct pytest execution**: `git clone` → `source venv/bin/activate` → `pytest` should work immediately for unit tests
2. **No complex setup**: Minimal code required in app repos (like `~/ai-food-log`)
3. **Environment isolation**: Different test suites ran in the same session can load different environments without conflicts
4. **Secret caching**: Expensive secret resolution happens once per process / pytest session
5. **Clean reloading**: Track what we load so we can reload different configurations
6. **Clear guidance**: Users get helpful messages when configurations are missing
7. **No backward compatibility**: Clean break from old system, build it right from the start
8. **Minimal app configuration**: Allow apps to configure nothing but project IDs if desired, keeping project ID definition as easy as possible while allowing all other app-level configuration to be version controlled safely
9. **Declarative test environments**: Make it as easy as possible to define which tests need which environment layers, with automatic loading via `pytest` and clear skip reporting when local configuration is insufficient

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
   ❌ Cannot load AI environment: GEMINI_API_KEY not found
   💡 To fix this, run: invoke secrets set gemini-api-key --config-env=dev
   ```
5. **Run integration tests**: `pytest tests/integration` → **works if PROJECT_ID configured**:
   - If PROJECT_ID in .projects file → tests run
   - If missing → guided to create .projects file with dev project ID
6. **Task execution**: `invoke prompt "hello"` → **works with AI environment loaded**

#### **App Repository (e.g., ~/ai-food-log)**
**Configuration**: `config/app.yaml` with `secrets.manager: "google"` for production
```yaml
id: ai-food-log
secrets:
  manager: "google"  # Use Google Secret Manager for production app
  # Google manager will use project_id from environments.yaml or GOOGLE_CLOUD_PROJECT env var

# AI Service Definitions
services:
    # ... detailed configuration

# API Server Configuration  
api:
  module: "core.api:app"
```

**Workflow**:
1. **Clone app**: `git clone <app-repo>` → `cd my-food-app`
2. **Activate environment**: `source venv/bin/activate`
3. **Run unit tests**: `pytest tests/unit` → **works immediately** (no secrets needed)
4. **Run AI tests**: `pytest tests/ai` → **works if secrets configured**:
   - If gemini-api-key exists in GCP Secret Manager → tests run
   - If missing → guided to run `invoke secrets set gemini-api-key --config-env=dev`
5. **Run integration tests**: `pytest tests/api` → **works if PROJECT_ID configured**:
   - If PROJECT_ID in .projects file → tests run
   - If missing → guided to create .projects file
6. **Task execution**: `invoke deploy dev` → **works with app environment loaded**

#### **Key Differences**
- **SDK**: Uses `secrets.manager: "local"` with `.secrets` file, has `integration-test` environment pointing to `.projects.dev`
- **App**: Uses `secrets.manager: "google"` with GCP Secret Manager, inherits project configuration, more production-ready
- **Both**: Unit tests work immediately, AI/integration tests provide clear guidance when missing
- **App-specific**: Includes detailed AI service configurations and API module specifications

### **Technical Goals**
- **Single source of truth**: One `environments.yaml` file with inheritance
- **Process-level caching**: Secrets loaded once, cached globally
- **Resilient loading**: Mid-load failures don't corrupt environment state
- **Marker-based testing**: `@pytest.mark.integration()` and `@pytest.mark.uses_secret()` markers for automatic environment loading
- **Strongly-typed exceptions**: Clear error messages for configuration issues
- **No magic**: Explicit environment loading, no hidden side effects
- **Project ID management**: Use `$.projects` syntax to reference `.projects` file
- **Environment inheritance**: Safe `app` layer for common settings, environment-specific project IDs
- **Smart base layer detection**: Auto-detect working base layer for integration tests

## **Glossary**

**Environment Variables:**
- **Staged**: Variables prepared for loading but not yet in `os.environ`
- **Loaded**: Variables that are actually set in `os.environ` and available to the application

**Environment Layers:**
- **Top Layer**: The primary environment being loaded (e.g., "unit", "ai", "integration")
- **Base Layer**: Optional additional layer loaded first (e.g., "app" for app-specific overrides)

**Configuration Files:**
- **SDK Config**: Default environment definitions in the SDK (`src/multi_eden/build/config/environments.yaml`)
- **App Config**: App-specific overrides (`config/environments.yaml` in app repos)

**Test Markers:**
- **@pytest.mark.integration("unit")**: Marks tests requiring unit environment
- **@pytest.mark.integration("ai")**: Marks tests requiring AI environment (needs GEMINI_API_KEY)
- **@pytest.mark.integration("api-test")**: Marks tests requiring integration environment (needs PROJECT_ID)

## **Overview**
Completely rebuild the environment loading system from scratch as the "right system" with no backward compatibility. Use a single `environments.yaml` file with inheritance-based layering, eliminating the need for separate `tasks.yaml` and `tests.yaml` environment configurations. This is a new SDK with no existing users, so we can make breaking changes to get the architecture right.

## **Current State**
- **Complex layering**: Multiple YAML files (`environments.yaml`, `tasks.yaml`, `tests.yaml`) with overlapping concerns
- **No inheritance**: Environments defined independently without reuse
- **Secret resolution**: Expensive operations repeated across multiple calls
- **Environment tracking**: No way to reload different configurations in multi-suite test execution

## **Target State**
- **Single source of truth**: All environment configs in `environments.yaml` with inheritance
- **Process-level secret caching**: Secrets loaded once per process, cached globally
- **Environment tracking**: Track loaded variables to enable clean reloading
- **Configurable file sources**: Support custom file paths for testing and flexibility
- **Verbose debug logging**: Detailed logging of layer loading and inheritance
- **No backward compatibility**: Clean break from old system
- **No tasks.yaml**: Tasks declare environment directly in decorator
- **Test markers**: Test modules use `@pytest.mark.*_env` markers for automatic environment loading

## **Code Refactoring Required**

### **Files to Completely Rewrite**
1. **`multi-eden/src/multi_eden/build/config/loading.py`** - Complete rewrite
2. **`multi-eden/src/multi_eden/build/config/loading.yaml`** - Delete (no longer needed)
3. **`multi-eden/src/multi_eden/build/config/tasks.yaml`** - Delete (no longer needed)
4. **`multi-eden/src/multi_eden/build/config/tests.yaml`** - Delete (no longer needed)
5. **`multi-eden/src/multi_eden/build/tasks/config/decorators.py`** - Simplify decorator
6. **`multi-eden/src/multi_eden/build/tasks/config/setup.py`** - Remove task config functions

### **Files to Update**
1. **`multi-eden/src/multi_eden/build/tasks/prompt.py`** - Update decorator usage
2. **`multi-eden/src/multi_eden/build/tasks/analyze.py`** - Update decorator usage
3. **`multi-eden/src/multi_eden/build/tasks/segment.py`** - Update decorator usage
4. **`multi-eden/src/multi_eden/build/tasks/api_start.py`** - Update decorator usage
5. **`multi-eden/src/multi_eden/build/tasks/build.py`** - Update decorator usage
6. **`multi-eden/src/multi_eden/build/tasks/deploy.py`** - Update decorator usage
7. **`multi-eden/src/multi_eden/build/tasks/test.py`** - Remove decorator, simplify
8. **`multi-eden/tests/conftest.py`** - Central marker-based environment loading
9. **`multi-eden/tests/unit/test_*.py`** - Add `pytestmark = pytest.mark.integration("unit")`
10. **`multi-eden/tests/ai/test_*.py`** - Add `pytestmark = pytest.mark.integration("ai")`

### **New Files to Create**
1. **`multi-eden/src/multi_eden/build/config/exceptions.py`** - Strongly-typed exceptions
2. **`multi-eden/tests/api/test_*.py`** - Add `pytestmark = pytest.mark.integration("api-test")`

### **Files to Delete/Repurpose**
1. **`multi-eden/src/multi_eden/build/config/secrets.py`** - Delete existing file, repurpose for secret caching
2. **`multi-eden/src/multi_eden/build/config/loading.yaml`** - Delete (replaced by environments.yaml)
3. **`multi-eden/src/multi_eden/build/config/tasks.yaml`** - Delete (tasks declare environment directly)
4. **`multi-eden/src/multi_eden/build/config/tests.yaml`** - Delete (replaced by marker system)

### **Dead Code Analysis**
**File**: `multi-eden/src/multi_eden/build/config/models.py`

**Current models**:
- `SecretsConfig` - Used by old secrets.py (will be deleted)
- `Authorization` - Used by old secrets.py (will be deleted)  
- `ProviderConfig` - Used by providers.json (may still be needed)
- `HostConfig` - Used by host.json (may still be needed)

**Action**: Delete `SecretsConfig` and `Authorization` after removing old secrets.py. Keep `ProviderConfig` and `HostConfig` if still used elsewhere.

### **Init-App Task Modernization**
**File**: `multi-eden/src/multi_eden/build/tasks/init_app.py`

**Current Issues**:
- Uses old `environments.yaml` structure (no inheritance)
- Creates separate `dev` and `prod` environments instead of using inheritance
- No support for new marker-based testing system
- Missing `tests/conftest.py` creation
- No guidance for new environment loading system

**Required Updates**:

### **1. New Invoke Task: `register-project`**

#### **1.1 Task Implementation**
**File**: `src/multi_eden/build/tasks/config/project.py`
```python
"""
Project ID management tasks.
"""
from pathlib import Path
from invoke import task

@task
def register_project(ctx, env_name, project_id):
    """
    Register a project ID for an environment in .projects file.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod', 'integration-test')
        project_id: Google Cloud Project ID
    """
    projects_file = Path(".projects")
    
    # Create .projects file if it doesn't exist
    if not projects_file.exists():
        projects_file.write_text("# Project IDs for different environments\n")
        print(f"✅ Created .projects file")
    
    # Read existing content
    lines = projects_file.read_text().splitlines()
    
    # Check if environment already exists
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{env_name}="):
            lines[i] = f"{env_name}={project_id}"
            updated = True
            break
    
    # Add new environment if not found
    if not updated:
        lines.append(f"{env_name}={project_id}")
    
    # Write back to file
    projects_file.write_text("\n".join(lines) + "\n")
    print(f"✅ Registered {env_name}={project_id}")
    
    # Ensure .gitignore includes .projects
    gitignore_file = Path(".gitignore")
    if gitignore_file.exists():
        gitignore_content = gitignore_file.read_text()
        if ".projects" not in gitignore_content:
            gitignore_file.write_text(gitignore_content + "\n# Project IDs (sensitive)\n.projects\n")
            print("✅ Added .projects to .gitignore")
    else:
        gitignore_file.write_text("# Project IDs (sensitive)\n.projects\n")
        print("✅ Created .gitignore with .projects entry")
```

#### **1.2 Task Registration**
**File**: `src/multi_eden/build/tasks/__init__.py`
```python
from .config.project import register_project

# Add to tasks namespace
__all__ = ["register_project"]
```

### **2. Update `_create_environments_yaml()`**:
   ```yaml
   environments:
     app:
       environment:
         APP_ID: "my-app-id"  # App-specific settings, no project ID
     dev:
       inherits: ["app"]
       environment:
         PROJECT_ID: "$.projects.dev"  # Reference .projects file
     prod:
       inherits: ["app"]
       environment:
         PROJECT_ID: "$.projects.prod"
   ```

2. **Add `.projects` file creation**:
   ```python
   def _create_projects_file(repo_root: Path, dev_project_id: str) -> None:
       """Create .projects file with project IDs."""
       projects_content = f"""# Multi-Eden Project IDs
# Format: environment=project-id

dev={dev_project_id}
prod={dev_project_id}  # TODO: Update with production project ID
integration-test={dev_project_id}
"""
       with open(repo_root / ".projects", "w") as f:
           f.write(projects_content)
   ```

3. **Add `tests/conftest.py` creation**:
   ```python
   def _create_tests_conftest(tests_dir: Path) -> None:
       """Create tests/conftest.py for marker-based environment loading."""
       conftest_content = '''"""
   Central pytest configuration for marker-based environment loading.
   """
   import os
   import pytest
   from multi_eden.build.config.loading import load_env

   @pytest.fixture(scope="module", autouse=True)
   def integration_loader(request):
       """Handle integration marker environment loading."""
       integration_marker = request.node.get_closest_marker("integration")
       if integration_marker:
           test_suite_layer = integration_marker.args[0]
           base_layer = integration_marker.kwargs.get("base_layer", None)
           
           # Find working base layer or skip
           working_base_layer = find_working_base_layer(base_layer)
           if not working_base_layer:
               pytest.skip("Integration tests require PROJECT_ID in base layer")
               return
           
           # Load test suite layer with working base layer
           load_env(top_layer=test_suite_layer, base_layer=working_base_layer)

   @pytest.fixture(scope="module", autouse=True)
   def secret_loader(request):
       """Handle uses_secret marker environment loading."""
       secret_marker = request.node.get_closest_marker("uses_secret")
       if secret_marker:
           secret_name = secret_marker.args[0]
           
           if not is_secret_available(secret_name):
               pytest.skip(f"Test requires {secret_name} secret")
               return

   # Helper functions
   def find_working_base_layer(preferred_base_layer=None):
       """Find a working base layer that has PROJECT_ID available."""
       # Try preferred base layer first
       if preferred_base_layer:
           try:
               load_env(top_layer=preferred_base_layer)
               if os.environ.get('PROJECT_ID'):
                   return preferred_base_layer
           except Exception:
               pass
       
       # Try BASE_ENV_LAYER environment variable
       base_env_layer = os.environ.get('BASE_ENV_LAYER')
       if base_env_layer:
           try:
               load_env(top_layer=base_env_layer)
               if os.environ.get('PROJECT_ID'):
                   return base_env_layer
           except Exception:
               pass
       
       # Try integration-test as fallback
       try:
           load_env(top_layer="integration-test")
           if os.environ.get('PROJECT_ID'):
               return "integration-test"
       except Exception:
           pass
       
       return None
   
   def is_secret_available(secret_name):
       """Check if a secret is available without loading it."""
       # This would check the secrets provider directly
       # Implementation depends on secrets provider type
       pass
   '''
       with open(tests_dir / "conftest.py", "w") as f:
           f.write(conftest_content)
   ```

4. **Add pytest.ini creation**:
   ```python
   def _create_pytest_ini(repo_root: Path) -> None:
       """Create pytest.ini with environment markers."""
       pytest_content = '''[pytest]
   markers =
       integration(layer_name, base_layer=None): Marks tests requiring specific environment layer
       uses_secret(secret_name): Marks tests requiring specific secret
   '''
       with open(repo_root / "pytest.ini", "w") as f:
           f.write(pytest_content)
   ```

5. **Add guidance messages** for new environment system:
   - Explain inheritance-based environments
   - Show how to add AI tests with `pytestmark = pytest.mark.uses_secret("gemini-api-key")`
   - Show how to add integration tests with `pytestmark = pytest.mark.integration("api-test")`

## **Decorator Usage**

### **Task Decorators**
Tasks use `@requires_config_env("environment_name")` decorator:
```python
@requires_config_env("ai")
def prompt(ctx, prompt_text):
    # Task implementation
```

### **Test Markers**
Test modules use `pytestmark` at module level with appropriate markers:

**Integration Tests** (with and without base layer):
```python
# tests/api/test_billing.py
import pytest

# With explicit base layer
pytestmark = pytest.mark.integration("api-test", base_layer="integration-test")

def test_create_invoice():
    # Test implementation

# tests/db/test_queries.py
import pytest

# Without base layer (auto-detects)
pytestmark = pytest.mark.integration("db-test")

def test_user_queries():
    # Test implementation
```

**Secret Tests**:
```python
# tests/ai/test_analysis.py
import pytest
pytestmark = pytest.mark.uses_secret("gemini-api-key")

def test_meal_analysis():
    # Test implementation
```

**Unit Tests** (no markers needed):
```python
# tests/unit/test_calculation.py
import pytest

def test_calculation():
    # Test implementation - no markers needed
```

**No function-level decorators needed** - the marker applies to all tests in the module.

## **App Repository Setup**

### **Minimal App Repo Requirements**
App repos (like `~/ai-food-log`) need only:

1. **`config/environments.yaml`** - App-specific overrides:
```yaml
environments:
  app:
    environment:
      PROJECT_ID: "my-app-project"
      APP_ID: "my-app"
```

2. **`tests/conftest.py`** - Single line:
```python
from multi_eden.build.config.loading import load_env
load_env("unit")  # Default environment for all tests
```

3. **Test modules** - Add markers as needed:
```python
# tests/ai/test_analysis.py
import pytest
pytestmark = pytest.mark.integration("ai")  # Only if AI tests exist
```

### **SDK Repository Setup**
After `git clone` and `source venv/bin/activate`:

1. **Unit tests work immediately**: `pytest tests/unit`
2. **AI tests need secret**: `pytest tests/ai` → guided to run `invoke secrets register`
3. **Integration tests need PROJECT_ID**: `pytest tests/api` → guided to set PROJECT_ID

## **Implementation Plan**

### **Phase 1: Core Infrastructure**

#### **1.1 Project ID Management**
**File**: `.projects` (in app repos)
```ini
# Multi-Eden Project IDs
# Format: environment=project-id

dev=my-app-dev-project
prod=my-app-prod-project
integration-test=my-app-test-project
staging=my-app-staging-project
```

**Benefits**:
- **Separation of concerns**: Project IDs separate from app configuration
- **Environment-specific**: Different project IDs for different environments
- **Simple format**: Easy to read and edit
- **Version control friendly**: Can be committed or gitignored as needed
- **No app.yaml bloat**: Keeps app.yaml focused on app-specific config

**Environment Configuration**:
```yaml
# src/multi_eden/build/config/environments.yaml
environments:
  unit:
    environment:
      # No requirements - always works
  
  ai:
    environment:
      GEMINI_API_KEY: "secret:gemini-api-key"
  
  integration-test:
    environment:
      PROJECT_ID: "$.projects.dev"  # Reference .projects file (uses dev project for SDK testing)
```

**SDK .projects File (Gitignored)**:
```ini
# .projects (gitignored) - SDK uses dev project for integration testing
dev=multi-eden-sdk-dev-project
```

**App .projects File (Gitignored)**:
```ini
# .projects (gitignored)
dev=my-app-dev-project
prod=my-app-prod-project
integration-test=my-app-test-project
staging=my-app-staging-project
```

**Loading Logic**:
```python
def _load_environment_variables(env_config, top_layer):
    """Load environment variables from configuration."""
    environment_vars = env_config.get("environment", {})
    loaded_vars = {}
    
    for var_name, var_value in environment_vars.items():
        if var_value.startswith("secret:"):
            # Handle secrets
            secret_name = var_value.replace("secret:", "")
            secret_value = get_secret(secret_name)
            loaded_vars[var_name] = (secret_value, f"secret:{secret_name}")
            
        elif var_value.startswith("$.projects."):
            # Handle project IDs from .projects file
            env_name = var_value.replace("$.projects.", "")
            project_id = get_project_id_from_projects_file(env_name)
            if project_id:
                loaded_vars[var_name] = (project_id, f"$.projects.{env_name}")
            else:
                raise ProjectIdNotFoundException(
                    f"Project ID not found for environment '{env_name}' in .projects file"
                )
                
        else:
            # Handle direct values
            loaded_vars[var_name] = (var_value, "direct")
    
    return loaded_vars

def get_project_id_from_projects_file(env_name):
    """Get project ID from .projects file for specific environment."""
    projects_file = Path(".projects")
    
    if not projects_file.exists():
        raise ProjectIdNotFoundException(
            f".projects file not found. Create it with: invoke register-project {env_name} your-project-id"
        )
    
    with open(projects_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    file_env, project_id = line.split("=", 1)
                    if file_env.strip() == env_name:
                        return project_id.strip()
    
    raise ProjectIdNotFoundException(
        f"Environment '{env_name}' not found in .projects file. "
        f"Add it with: invoke register-project {env_name} your-project-id"
    )
```

**Strongly-Typed Exceptions**:
```python
# src/multi_eden/build/config/exceptions.py
class ProjectIdNotFoundException(Exception):
    """Raised when a project ID cannot be found in .projects file."""
    pass

class ProjectsFileNotFoundException(Exception):
    """Raised when .projects file is missing."""
    pass
```

**Benefits of `$.projects` Syntax**:
- **Clear reference**: `$.projects.integration-test` clearly indicates file and key
- **Consistent pattern**: Similar to JSONPath or other reference syntax
- **Extensible**: Easy to add other file references like `$.secrets.local`
- **Self-documenting**: Makes it obvious where the value comes from
- **Gitignored by default**: `.projects` file can be safely gitignored

#### **1.2 Environment Merging Logic**
**File**: `multi-eden/src/multi_eden/build/config/loading.py`

**Merging Strategy**:
1. **SDK defaults**: Load `src/multi_eden/build/config/environments.yaml`
2. **App overrides**: Load `config/environments.yaml` (if exists)
3. **App-specific environments**: Allow apps to add custom environments like `staging`
4. **App-specific overrides**: Allow apps to override SDK settings (e.g., `stub_db: true` in dev)

**Example App Override**:
```yaml
# config/environments.yaml (app repo)
environments:
  # Override SDK dev environment
  dev:
    inherits: ["app"]  # Inherit from SDK
    environment:
      PROJECT_ID: "$.projects.dev"  # Use .projects file
      STUB_DB: "true"               # Override SDK setting
  
  # Add custom staging environment
  staging:
    inherits: ["app"]
    environment:
      PROJECT_ID: "$.projects.staging"
      CUSTOM_SETTING: "staging-value"
```

**Merging Implementation**:
```python
def _load_and_merge_files(files: List[str]) -> Dict[str, Any]:
    """Load and merge multiple environment configuration files."""
    merged_config = {"environments": {}}
    
    for file_path in files:
        if Path(file_path).exists():
            with open(file_path) as f:
                config = yaml.safe_load(f)
                if "environments" in config:
                    # Merge environments, app configs override SDK defaults
                    merged_config["environments"].update(config["environments"])
    
    return merged_config
```

#### **1.3 Secret Caching System**
**File**: `multi-eden/src/multi_eden/build/config/secrets.py`
```python
_secret_cache = {}  # Module-level cache: secret_name -> value

def get_secret(secret_name: str) -> str:
    """Get secret with process-level caching."""
    if secret_name in _secret_cache:
        logger.debug(f"Using cached secret '{secret_name}'")
        return _secret_cache[secret_name]
    
    # Load from secrets manager - let any exception bubble up
    logger.debug(f"Loading secret '{secret_name}' from secrets manager")
    try:
        from multi_eden.build.secrets.factory import get_secrets_manager
        manager = get_secrets_manager()
        response = manager.get_secret(secret_name, show=True)
        
        if response.meta.success and response.secret:
            _secret_cache[secret_name] = response.secret.value
            logger.debug(f"Successfully loaded and cached secret '{secret_name}'")
            return response.secret.value
        else:
            raise SecretUnavailableException(f"Secret '{secret_name}' not found")
            
    except Exception as e:
        logger.debug(f"Failed to load secret '{secret_name}': {e}")
        # Re-raise as-is - let the calling code handle it
        raise
```

**Key Points**:
- Module-level cache persists for entire process
- No fallbacks or default values
- Let secrets manager exceptions bubble up
- Never call secrets manager twice for same secret name

#### **1.2 Environment Isolation & Clean State Management**

**Critical Behavior**: Each `load_env()` call ensures a **clean environment state** by:
1. **Clearing our previously loaded variables** (preserving pre-existing `os.environ`)
2. **Loading new variables** from the specified layers
3. **Tracking what we loaded** for future cleanup

This prevents **environment pollution** between different test modules that require different environments.

**Example Scenario**:
```python
# Module A: tests/api/test_billing.py
@pytest.mark.integration("api-test")
def test_create_invoice():
    # load_env("api-test", base_layer="dev") called
    # Sets: PROJECT_ID=dev-project, API_URL=https://api.dev.com
    assert os.environ["PROJECT_ID"] == "dev-project"

# Module B: tests/ai/test_gemini.py  
@pytest.mark.uses_secret("gemini-api-key")
def test_ai_prompt():
    # load_env("ai") called
    # CLEARS: PROJECT_ID, API_URL (our previous vars)
    # Sets: GEMINI_API_KEY=secret123
    assert "PROJECT_ID" not in os.environ  # ✅ Clean state
    assert os.environ["GEMINI_API_KEY"] == "secret123"
```

#### **1.3 Environment Variable Tracking & Load Optimization**
**File**: `multi-eden/src/multi_eden/build/config/loading.py`
```python
_last_load = None  # Track last successful load: {"params": {...}, "loaded_vars": {...}}

def _is_same_load(top_layer: str, base_layer: Optional[str], files: List[str]) -> bool:
    """Check if this is the same load request as the current one."""
    if _last_load is None:
        return False
    
    # Resolve the actual base layer that will be used
    resolved_base_layer = _resolve_base_layer(base_layer)
    
    last_params = _last_load["params"]
    return (
        last_params["top_layer"] == top_layer and
        last_params["base_layer"] == resolved_base_layer and  # Compare resolved values
        last_params["files"] == files
    )

def _resolve_base_layer(base_layer: Optional[str]) -> Optional[str]:
    """Resolve the actual base layer that will be used."""
    if base_layer is not None:
        return base_layer
    return os.environ.get("BASE_ENV_LAYER")

def _clear_our_vars():
    """Clear only the variables that WE previously loaded."""
    if _last_load is None:
        return
    
    for var_name in _last_load["loaded_vars"]:
        if var_name in os.environ:
            del os.environ[var_name]

def _load_staged_vars(staged_vars: Dict[str, Tuple[str, str]]) -> Dict[str, str]:
    """Load staged variables into os.environ after clearing our previous vars."""
    # Clear our previously loaded variables
    _clear_our_vars()
    
    # Load staged variables into os.environ
    for var_name, (value, source) in staged_vars.items():
        os.environ[var_name] = value
    
    # Return the loaded variables for tracking
    return {var_name: value for var_name, (value, source) in staged_vars.items()}

def _commit_load(top_layer: str, base_layer: Optional[str], files: List[str], loaded_vars: Dict[str, str]):
    """Commit a successful load operation."""
    global _last_load
    _last_load = {
        "params": {
            "top_layer": top_layer,
            "base_layer": _resolve_base_layer(base_layer),  # Store resolved value
            "files": files
        },
        "loaded_vars": loaded_vars
    }
```

**Key Points**:
- **Environment Isolation**: Each `load_env()` call completely replaces our previously loaded variables
- **Clean State**: `_clear_our_vars()` removes only variables WE loaded, preserving pre-existing `os.environ`
- **No Pollution**: Different test modules get clean environments - no mixing of variables between modules
- **Optimization**: Skip reloading if same request (unless `force_reload=True`)
- **Load Process**: Clear our vars → Load new vars → Commit to tracking
- Resilient to mid-load failures (no partial state corruption)

**Example: Load Optimization**
```python
# Call 1: Load "api-test" layer
load_env("api-test", files)  # Loads environment, tracks as current
# _current_load = {"top_layer": "api-test", "base_layer": None, "files": files}

# Call 2: Load "unit" layer  
load_env("unit", files)      # Loads different environment, clears previous
# _current_load = {"top_layer": "unit", "base_layer": None, "files": files}

# Call 3: Load "unit" layer again (same request)
load_env("unit", files)      # Skips loading - same as current
# _current_load = {"top_layer": "unit", "base_layer": None, "files": files} (unchanged)

# Call 4: Force reload same environment
load_env("unit", files, force_reload=True)  # Forces reload even though same
# _current_load = {"top_layer": "unit", "base_layer": None, "files": files} (updated)
```

### **Phase 2: Environment Structure with Inheritance**

#### **2.1 New Environment YAML Structure**
**File**: `multi-eden/src/multi_eden/build/config/environments.yaml`
```yaml
environments:
  app:  # Renamed from 'base' to avoid confusion with base_layer parameter
    env:
      APP_ID: "multi-eden-sdk"
      CUSTOM_AUTH_ENABLED: true
  
  ai:
    env:
      GEMINI_API_KEY: "secret:gemini-api-key"
  
  unit:
    inherits: "app"
    env:
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"  # Mock value
      STUB_AI: true
      STUB_DB: true
      TEST_API_IN_MEMORY: true
      TEST_OMIT_INTEGRATION: true
  
  api-test:
    inherits: "app"
    env:
      JWT_SECRET_KEY: "test-jwt-secret-multi-eden-sdk"  # Mock value
      STUB_AI: true
      STUB_DB: true
      TEST_API_IN_MEMORY: false
      TEST_API_URL: "http://localhost:8000"
  
  local:
    inherits: "app"
    env:
      STUB_AI: true
      STUB_DB: true
      LOCAL: true
      PORT: 8000
      GEMINI_API_KEY: "fake-local-gemini-key"  # Mock value
      JWT_SECRET_KEY: "local-jwt-secret"  # Mock value
      ALLOWED_USER_EMAILS: "test-user@static.multi-eden-sdk.app"
  
  dev:
    inherits: "app"
    env:
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"  # Real secret
      JWT_SECRET_KEY: "secret:jwt-secret-key"  # Real secret
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"  # Real secret
  
  prod:
    inherits: "app"
    env:
      STUB_AI: false
      STUB_DB: false
      GEMINI_API_KEY: "secret:gemini-api-key"  # Real secret
      JWT_SECRET_KEY: "secret:jwt-secret-key"  # Real secret
      ALLOWED_USER_EMAILS: "secret:allowed-user-emails"  # Real secret
```

#### **2.2 App-Specific Overrides**
**File**: `multi-eden/config/environments.yaml` (new)
```yaml
environments:
  integration:
    env:
      PROJECT_ID: "your-integration-project-id"
      # This environment provides PROJECT_ID for integration testing
      # when used as base_layer for API tests
  
  dev:
    env:
      PROJECT_ID: "your-dev-project-id"
  
  prod:
    env:
      PROJECT_ID: "your-prod-project-id"
```

### **Phase 3: Inheritance Processing**

#### **3.1 Environment Merging**
**File**: `multi-eden/src/multi_eden/build/config/loading.py`
```python
def _load_merged_environments() -> Dict[str, Any]:
    """Load and merge SDK + app environment configs."""
    # Load SDK environments
    sdk_config = _load_yaml_file("environments.yaml")
    
    # Load app environments (if exists)
    app_config = _load_yaml_file("{cwd}/config/environments.yaml")
    
    # Merge: app overrides SDK
    merged_environments = sdk_config.get('environments', {}).copy()
    if app_config and 'environments' in app_config:
        for env_name, env_config in app_config['environments'].items():
            if env_name in merged_environments:
                # Merge app overrides into SDK defaults
                merged_environments[env_name]['env'].update(env_config.get('env', {}))
            else:
                # Add app-only environments
                merged_environments[env_name] = env_config
    
    return {'environments': merged_environments}
```

#### **3.2 Inheritance Processing with Optional Base Layer**
```python
def _process_inheritance(top_layer: str, base_layer: Optional[str], merged_config: Dict[str, Any]) -> Dict[str, Any]:
    """Process environment inheritance with optional base layer."""
    loaded_layers = set()  # Track loaded layers in this call
    
    def _load_layer(layer_name: str) -> Dict[str, Any]:
        if layer_name in loaded_layers:
            logger.warning(f"Circular dependency detected: {layer_name} already loaded")
            return {}  # Return empty config to break cycle
        
        loaded_layers.add(layer_name)
        logger.debug(f"Loading layer '{layer_name}'")
        
        if layer_name not in merged_config['environments']:
            raise EnvironmentNotFoundError(f"Environment '{layer_name}' not found")
        
        env_config = merged_config['environments'][layer_name]
        final_config = {'env': {}}
        
        # Load base layer first if specified
        if base_layer and base_layer != layer_name:
            logger.debug(f"Loading base environment layer: '{base_layer}'")
            base_config = _load_layer(base_layer)
            final_config['env'].update(base_config.get('env', {}))
            logger.debug(f"Applied {len(base_config.get('env', {}))} variables from base layer '{base_layer}'")
        
        # Process inheritance
        if 'inherits' in env_config:
            parent_name = env_config['inherits']
            logger.debug(f"Layer '{layer_name}' inherits from '{parent_name}'")
            parent_config = _load_layer(parent_name)
            final_config['env'].update(parent_config.get('env', {}))
            logger.debug(f"Inherited {len(parent_config.get('env', {}))} variables from '{parent_name}'")
        
        # Apply current layer's config (overrides inherited)
        current_env = env_config.get('env', {})
        final_config['env'].update(current_env)
        logger.debug(f"Applied {len(current_env)} variables from layer '{layer_name}'")
        
        return final_config
    
    return _load_layer(top_layer)
```

### **Phase 4: New Load Environment Function**

#### **4.1 Main Load Environment Function**
```python
def load_env(top_layer: str, base_layer: Optional[str] = None, files: Optional[List[str]] = None, force_reload: bool = False) -> Dict[str, Tuple[str, str]]:
    """Load environment with optional base layer and configurable file sources."""
    if files is None:
        # Default file sources
        files = [
            "environments.yaml",  # SDK environments
            "{cwd}/config/environments.yaml"  # App environments
        ]
    
    # Check if this is the same load request as current
    if not force_reload and _is_same_load(top_layer, base_layer, files):
        logger.debug(f"Skipping reload - same environment already loaded: '{top_layer}'")
        return {}  # Return empty dict since nothing changed
    
    return _load_env(top_layer, base_layer, files)

def _load_env(top_layer: str, base_layer: Optional[str], files: List[str]) -> Dict[str, Tuple[str, str]]:
    """Internal load environment function with required parameters."""
    logger.debug(f"Loading environment '{top_layer}' from files: {files}")
    if base_layer:
        logger.debug(f"With base environment layer: '{base_layer}'")
    
    # Load and merge configuration files
    merged_config = _load_and_merge_files(files)
    
    # Process inheritance and load new variables
    env_config = _process_inheritance(top_layer, base_layer, merged_config)
    new_vars = _load_environment_variables(env_config, top_layer)
    
    # Load the staged variables (clear our vars, load new vars)
    loaded_vars = _load_staged_vars(new_vars)
    
    # Commit the successful load
    _commit_load(top_layer, base_layer, files, loaded_vars)
    
    # Return the loaded variables with source info
    return {name: (value, source) for name, (value, source) in new_vars.items()}

def _load_and_merge_files(files: List[str]) -> Dict[str, Any]:
    """Load and merge multiple configuration files."""
    merged_environments = {}
    
    for file_path in files:
        # Resolve file path (handle {cwd} placeholder)
        resolved_path = file_path.replace("{cwd}", str(Path.cwd()))
        if not resolved_path.startswith("/"):
            # Relative path - resolve from SDK root
            sdk_root = Path(__file__).parent.parent.parent.parent
            resolved_path = sdk_root / resolved_path
        
        logger.debug(f"Loading config file: {resolved_path}")
        
        if not Path(resolved_path).exists():
            logger.debug(f"Config file not found: {resolved_path}")
            continue
        
        try:
            with open(resolved_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            if 'environments' in config:
                # Merge environments (later files override earlier ones)
                for env_name, env_config in config['environments'].items():
                    if env_name in merged_environments:
                        # Merge app overrides into SDK defaults
                        merged_environments[env_name]['env'].update(env_config.get('env', {}))
                    else:
                        # Add new environment
                        merged_environments[env_name] = env_config
                
                logger.debug(f"Loaded {len(config['environments'])} environments from {resolved_path}")
        
        except Exception as e:
            logger.error(f"Failed to load config file {resolved_path}: {e}")
            raise EnvironmentLoadError(f"Failed to load config file {resolved_path}: {e}")
    
    return {'environments': merged_environments}

# This function is now defined above in section 3.2

def _load_environment_variables(env_config: Dict[str, Any], layer_name: str) -> Dict[str, Tuple[str, str]]:
    """Load environment variables with secret error handling."""
    loaded_vars = {}
    
    for key, value in env_config.get('env', {}).items():
        env_var_name = key.upper()
        
        # Check if already in os.environ (highest priority)
        if env_var_name in os.environ:
            existing_value = os.environ[env_var_name]
            
            # Process the value we would have loaded to compare
            try:
                processed_value = _process_value(value)
                
                if existing_value == processed_value:
                    logger.debug(f"Variable '{env_var_name}' already set to desired value - keeping existing")
                else:
                    logger.debug(f"Variable '{env_var_name}' already set to different value (wanted different) - keeping existing")
                
                loaded_vars[env_var_name] = (existing_value, 'os.environ')
                continue
                
            except SecretUnavailableException as e:
                logger.debug(f"Variable '{env_var_name}' already set - skipping secret processing due to error: {e}")
                loaded_vars[env_var_name] = (existing_value, 'os.environ')
                continue
            except Exception as e:
                logger.debug(f"Variable '{env_var_name}' already set - skipping processing due to error: {e}")
                loaded_vars[env_var_name] = (existing_value, 'os.environ')
                continue
        
        # Process new value (not in os.environ)
        try:
            processed_value = _process_value(value)
            # Simple decision: if it's a secret, don't log the value
            if value.startswith('secret:'):
                logger.debug(f"Variable '{env_var_name}' not set - loading new secret value from layer '{layer_name}'")
            else:
                logger.debug(f"Variable '{env_var_name}' not set - loading new value '{processed_value}' from layer '{layer_name}'")
            loaded_vars[env_var_name] = (processed_value, 'environment')
        except SecretUnavailableException as e:
            if fail_on_secret_error:
                raise  # Re-raise the exception
            else:
                logger.error(f"Failed to load secret for {env_var_name}: {e}")
                logger.debug(f"Variable '{env_var_name}' not set - skipping due to secret error")
                # Don't set any value - continue loading other variables
        except Exception as e:
            logger.error(f"Failed to process {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to processing error")
            if fail_on_secret_error:
                raise
    
    return loaded_vars

def _process_value(value: Any) -> str:
    """Process value with different source schemes (secret:, etc.)."""
    if not isinstance(value, str):
        logger.debug(f"Converting non-string value to string: {value}")
        return str(value)
    
    if value.startswith('secret:'):
        secret_name = value[7:]  # Remove 'secret:' prefix
        logger.debug(f"Processing secret reference: {value} -> {secret_name}")
        return get_secret(secret_name)  # Uses cached version
    else:
        logger.debug(f"Using literal value: {value}")
        return value
```

### **Phase 5: Update Task System**

#### **5.1 Task Decorator with Direct Environment Declaration**
**File**: `multi-eden/src/multi_eden/build/tasks/config/decorators.py`
```python
def requires_config_env(environment: str):
    """Decorator that requires a specific environment to be loaded."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(ctx, *args, **kwargs):
            try:
                load_env(environment, fail_on_secret_error=True)
            except SecretUnavailableException as e:
                print(f"❌ Secret unavailable: {e}", file=sys.stderr)
                sys.exit(1)
            except EnvironmentLoadError as e:
                print(f"❌ Environment load failed: {e}", file=sys.stderr)
                sys.exit(1)
            # Let other exceptions bubble up
            
            return func(ctx, *args, **kwargs)
        return wrapper
    return decorator
```

#### **5.2 Updated Task Definitions**
**File**: `multi-eden/src/multi_eden/build/tasks/prompt.py`
```python
@task(help={...})
@requires_config_env("ai")
def prompt(ctx, prompt_text, config_env=None, model='gemini-2.5-flash', grounding=False, quiet=False, debug=False):
    # Task implementation
```

**File**: `multi-eden/src/multi_eden/build/tasks/analyze.py`
```python
@task(help={...})
@requires_config_env("ai")
def analyze(ctx, food_description, config_env=None, model=None, format='json'):
    # Task implementation
```

**File**: `multi-eden/src/multi_eden/build/tasks/api_start.py`
```python
@task(help={...})
@requires_config_env("local")
def api_start(ctx, config_env=None, debug=False):
    # Task implementation
```

**File**: `multi-eden/src/multi_eden/build/tasks/build.py`
```python
@task(help={...})
@requires_config_env("dev")
def build(ctx, config_env=None, debug=False):
    # Task implementation
```

**File**: `multi-eden/src/multi_eden/build/tasks/deploy.py`
```python
@task(help={...})
@requires_config_env("prod")
def deploy(ctx, config_env=None, debug=False):
    # Task implementation
```

### **Phase 6: Update Test System**

#### **6.1 Marker-Based Environment Loading**
**File**: `multi-eden/pytest.ini`
```ini
[pytest]
markers =
    integration(layer_name): Marks tests requiring specific environment layer
```

**File**: `multi-eden/tests/conftest.py` (Central marker-based environment loading)
```python
    import os
import pytest
from multi_eden.build.config.loading import load_env

@pytest.fixture(scope="module", autouse=True)
def env_loader(request):
    """
    This autouse fixture runs once per test module. It checks for environment
    markers and loads the specified environment.
    """
    # Check for integration marker
    integration_marker = request.node.get_closest_marker("integration")
    if integration_marker:
        layer_name = integration_marker.args[0]
        base_layer = os.environ.get("BASE_ENV_LAYER", "app")
        try:
            load_env(top_layer=layer_name, base_layer=base_layer)
    except SecretUnavailableException as e:
            print(f"\n❌ Cannot load integration environment: {e}")
        print("💡 To fix this, either:")
        print("   1. Set up .secrets file locally, OR")
        print("   2. Set BASE_ENV_LAYER environment variable")
        print("   3. Run: export BASE_ENV_LAYER=dev")
            pytest.exit("Integration environment setup failed")
        return
    
    # No additional marker checks needed - integration marker handles all cases
    
    # Default: load unit environment for tests without markers
    try:
        load_env(top_layer="unit")
    except SecretUnavailableException as e:
        print(f"\n❌ Cannot load default unit environment: {e}")
        print("💡 To fix this, either:")
        print("   1. Set up .secrets file locally, OR")
        print("   2. Set BASE_ENV_LAYER environment variable")
        print("   3. Run: export BASE_ENV_LAYER=dev")
        pytest.exit("Default environment setup failed")

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add custom footer to pytest output."""
    # Check if GEMINI_API_KEY is available for AI tests
    if not os.environ.get('GEMINI_API_KEY'):
        terminalreporter.write_sep("=", "AI TESTS SKIPPED")
        terminalreporter.write_line("❌ AI tests were skipped due to missing GEMINI_API_KEY")
        terminalreporter.write_line("💡 To run AI tests:")
        terminalreporter.write_line("   invoke secrets set gemini-api-key --config-env=dev")
        terminalreporter.write_line("   # Or set BASE_ENV_LAYER environment variable")
        terminalreporter.write_line("   export BASE_ENV_LAYER=dev")
    
    # Check if PROJECT_ID is available for integration tests
    if not os.environ.get('PROJECT_ID'):
        terminalreporter.write_sep("=", "INTEGRATION TESTS SKIPPED")
        terminalreporter.write_line("❌ Integration tests were skipped due to missing PROJECT_ID")
        terminalreporter.write_line("💡 To run integration tests:")
        terminalreporter.write_line("   1. Register project ID for integration testing:")
        terminalreporter.write_line("      invoke register-project integration-test your-project-id")
        terminalreporter.write_line("")
        terminalreporter.write_line("   2. Or set BASE_ENV_LAYER environment variable:")
        terminalreporter.write_line("      export BASE_ENV_LAYER=dev  # or any layer with PROJECT_ID")
```

#### **6.2 Example Test Files with Markers**
**File**: `multi-eden/tests/unit/test_calculation_logic.py`
```python
import pytest

# This marker applies to ALL tests in this file
pytestmark = pytest.mark.unit_env

def test_calculate_nutrition():
    # Test logic here...
    assert True

def test_validate_units():
    # Test logic here...
    assert True
```

**File**: `multi-eden/tests/ai/test_ai_prompts.py`
```python
import pytest

# This marker applies to ALL tests in this file
pytestmark = pytest.mark.integration("ai")

def test_prompt_generation():
    # Test logic here...
    assert True

def test_response_parsing():
    # Test logic here...
    assert True
```

**File**: `multi-eden/tests/api/test_billing.py`
```python
import pytest

# This marker applies to ALL tests in this file
pytestmark = pytest.mark.integration

def test_create_invoice():
    # Test logic here...
    assert True

def test_get_invoice_status():
    # Test logic here...
    assert True
```

**File**: `multi-eden/tests/api/test_auth.py`
```python
import pytest

# This marker applies to ALL tests in this file
pytestmark = pytest.mark.integration

def test_user_authentication():
    # Test logic here...
    assert True

def test_token_validation():
    # Test logic here...
    assert True
```

#### **6.3 Test Task Runner (No Decorator)**
**File**: `multi-eden/src/multi_eden/build/tasks/test.py`
```python
@task(help={...})
def test(ctx, suite, config_env=None, verbose=False, test_name=None, show_config=False, quiet=False):
    """
    Run tests for a specific suite.
    
    Note: Environment loading is handled by markers in test modules and central conftest.py.
    This task just runs pytest with the appropriate test paths.
    """
    if suite is None:
        print("❌ Error: Test suite is required")
        print("   Usage: inv test <suite>")
        print("   Available suites: unit, ai, firestore, api")
        sys.exit(1)
    
    # Get test paths for pytest - no environment loading needed
    test_paths = _get_test_paths(suite) if suite else None
    
    return run_pytest(suite, config_env, verbose, test_name, show_config, test_paths, quiet)
```

#### **6.4 Pytest Footer Guidance**
**Approach**: Use `pytest_terminal_summary` to provide helpful footer output when tests are skipped due to missing configuration.

**Key Benefits**:
- **User-Friendly**: Clear guidance on how to fix configuration issues
- **Test-Specific**: Different guidance for different test suites (AI vs API vs Unit)
- **Non-Intrusive**: Doesn't break test execution, just provides helpful output
- **Environment-Aware**: Checks actual loaded environment variables

**Footer Output Examples**:
```
========================= AI TESTS SKIPPED =========================
❌ AI tests were skipped due to missing GEMINI_API_KEY
💡 To run AI tests, either:
   1. Set up .secrets file locally, OR
   2. Set BASE_ENV_LAYER environment variable
   3. Run: export BASE_ENV_LAYER=dev

========================= INTEGRATION TESTS SKIPPED =========================
❌ Integration tests were skipped due to missing PROJECT_ID
💡 To run integration tests, either:
   1. Set up .secrets file locally, OR
   2. Set BASE_ENV_LAYER environment variable
   3. Run: export BASE_ENV_LAYER=dev
   4. Ensure your app's config/environments.yaml has 'integration' environment with PROJECT_ID
```

#### **6.5 Pytest Conftest Verification**
**Verification needed**: Confirm pytest conftest.py behavior for folder-by-folder execution.

**Expected behavior**:
- `pytest tests/unit` → runs `tests/conftest.py` → `load_env("unit")` for integration("unit") marked tests
- `pytest tests/ai` → runs `tests/conftest.py` → `load_env("ai")` for integration("ai") marked tests  
- `pytest tests/api` → runs `tests/conftest.py` → `load_env("api-test", base_layer="app")` for integration("api-test") marked tests
- Each test module loads exactly what it needs via markers

**No teardown needed**: Each test module is independent and loads its own environment

### **Phase 7: BASE_ENV_LAYER Support**

#### **7.1 BASE_ENV_LAYER Concept**
The `BASE_ENV_LAYER` environment variable allows users to specify an additional base layer that gets loaded before the main environment layer. This is useful for:

- **Integration Testing**: Load a layer with `PROJECT_ID` for cloud services
- **Local Development**: Load a layer with local configuration overrides
- **Environment-Specific Setup**: Load different base configurations per environment

#### **7.2 Usage Examples**
```python
# Basic usage (no base layer)
load_env("unit")

# With base layer from environment variable
# export BASE_ENV_LAYER=dev
load_env("unit")  # Automatically loads "dev" as base layer

# With explicit base layer
load_env("unit", base_layer="dev")

# With custom files
load_env("unit", base_layer="dev", files=["custom-env.yaml"])

# In conftest.py
def pytest_configure(config):
    from multi_eden.build.config.loading import load_env
    import os
    base_layer = os.environ.get('BASE_ENV_LAYER')
    load_env("unit", base_layer=base_layer)
```

#### **7.3 Layer Loading Order**
When `base_layer` is specified, the loading order is:
1. **Base Layer**: Load `base_layer` first (if specified)
2. **Inheritance**: Process `inherits` chain from top layer
3. **Top Layer**: Apply top layer configuration (overrides everything)

Example: `load_env("unit", base_layer="dev")` loads:
1. `dev` layer (from base_layer)
2. `app` layer (from unit's `inherits: "app"`)
3. `unit` layer (final overrides)

### **Phase 8: Error Handling & Validation**

#### **8.1 Strongly-Typed Exceptions**
**File**: `multi-eden/src/multi_eden/build/config/exceptions.py`
```python
class EnvironmentLoadError(Exception):
    """Raised when environment cannot be loaded."""
    pass

class EnvironmentNotFoundError(EnvironmentLoadError):
    """Raised when environment name not found."""
    pass

class SecretUnavailableException(Exception):
    """Raised when a secret cannot be loaded."""
    pass
```

#### **8.2 Task-Level Error Handling**
- Only catch strongly-typed exceptions
- Convert to user-friendly messages
- Use stderr for error output
- No fallbacks or default values

### **Phase 9: Clean Implementation (No Migration)**

#### **9.1 Delete Old Files**
- Delete `loading.yaml` (replaced by inheritance system)
- Delete `tasks.yaml` (no longer needed - tasks declare environment in decorator)
- Delete `tests.yaml` (no longer needed - test suites use conftest.py)
- Delete old `loading.py` (complete rewrite)

#### **9.2 Update All Dependencies**
- Update all task files to use new decorator syntax
- Update all test modules to use appropriate markers
- Update all imports to use new loading system
- Remove all references to old configuration system

#### **9.3 Update Documentation**
- Document new inheritance system
- Update task configuration examples
- Document error handling patterns
- Document rollback functionality

## **Debug Logging Examples**

### **Environment Variable Processing**
```
DEBUG: Loading layer 'unit'
DEBUG: Layer 'unit' inherits from 'base'
DEBUG: Inherited 2 variables from 'base'
DEBUG: Applied 4 variables from layer 'unit'
DEBUG: Variable 'APP_ID' not set - loading new value 'multi-eden-sdk' from layer 'unit'
DEBUG: Using literal value: multi-eden-sdk
DEBUG: Variable 'JWT_SECRET_KEY' not set - loading new value 'test-jwt-secret-multi-eden-sdk' from layer 'unit'
DEBUG: Using literal value: test-jwt-secret-multi-eden-sdk
DEBUG: Variable 'TEST_API_IN_MEMORY' not set - loading new value 'true' from layer 'unit'
DEBUG: Using literal value: true
DEBUG: Variable 'STUB_AI' not set - loading new value 'true' from layer 'unit'
DEBUG: Using literal value: true
```

### **Secret Variable Processing**
```
DEBUG: Variable 'GEMINI_API_KEY' not set - loading new secret value from layer 'ai'
DEBUG: Processing secret reference: secret:gemini-api-key -> gemini-api-key
DEBUG: Loading secret 'gemini-api-key' from secrets manager
DEBUG: Successfully loaded and cached secret 'gemini-api-key'
```

### **Already Set Variables**
```
DEBUG: Variable 'APP_ID' already set to desired value - keeping existing
DEBUG: Variable 'JWT_SECRET_KEY' already set to different value (wanted different) - keeping existing
DEBUG: Variable 'GEMINI_API_KEY' already set - skipping secret processing due to error: Secret 'gemini-api-key' not found
```

### **Cached Secret Usage**
```
DEBUG: Variable 'GEMINI_API_KEY' not set - loading new secret value from layer 'ai'
DEBUG: Processing secret reference: secret:gemini-api-key -> gemini-api-key
DEBUG: Using cached secret 'gemini-api-key'
```

## **Key Design Principles**

1. **Single source of truth**: All environment configs in `environments.yaml`
2. **Process-level secret caching**: Never call secrets manager twice for same secret
3. **No fallbacks**: Fail fast with clear error messages
4. **Environment tracking**: Enable clean reloading for multi-suite tests
5. **Load optimization**: Skip reloading if same environment already loaded
6. **Configurable file sources**: Support custom file paths for testing and flexibility
7. **Verbose debug logging**: Detailed logging of layer loading and inheritance
8. **Inheritance over layering**: Use `inherits` instead of complex layer system
9. **Mock vs real secrets**: Mock values in test layers, real secrets in cloud layers
10. **Circular dependency handling**: Warn and break cycles, don't fail
11. **Error propagation**: Let secrets manager exceptions bubble up
12. **No backward compatibility**: Clean break from old system
13. **No tasks.yaml**: Tasks declare environment directly in decorator
14. **Marker-based testing**: Test modules declare environment needs via pytest markers
15. **Unit testable**: Internal functions accept required parameters for testing

## **Testing Strategy**

1. **Unit tests**: Test inheritance processing, secret caching, environment tracking
2. **Integration tests**: Test full environment loading with real configs
3. **Error tests**: Test different failure modes and error handling
4. **Performance tests**: Test secret caching and environment reloading performance

## **Success Criteria**

1. ✅ All environment configs consolidated in `environments.yaml`
2. ✅ Inheritance system working with circular dependency detection
3. ✅ Process-level secret caching implemented
4. ✅ Environment tracking enabling clean reloading
5. ✅ Task system using new environment loading
6. ✅ Test system using new environment loading
7. ✅ Error handling with strongly-typed exceptions
8. ✅ No fallbacks or default values
9. ✅ All existing functionality preserved
10. ✅ Performance improved (secrets cached, simpler loading)

## **Implementation Order**

1. **Phase 1**: Secret caching and environment tracking
2. **Phase 2**: New environment YAML structure
3. **Phase 3**: Inheritance processing
4. **Phase 4**: New load environment function
5. **Phase 5**: Update task system
6. **Phase 6**: Update test system
7. **Phase 7**: BASE_ENV_LAYER support
8. **Phase 8**: Error handling and validation
9. **Phase 9**: Migration and cleanup

This plan provides a complete roadmap for implementing the new environment configuration system while maintaining backward compatibility and improving performance.
