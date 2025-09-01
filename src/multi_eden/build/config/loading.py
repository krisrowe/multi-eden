"""Environment configuration loading for build tasks.

Handles loading environment configuration from environments.yaml and test modes,
layering test mode settings on top of environment settings, and setting up
all environment variables for build task execution.

This module implements a single-call architecture where load_env() is called
once per process and sets up all required environment variables."""

import os
import sys
import logging
from typing import Dict, Any, Optional

from .test_mode import get_test_mode_config
from .settings import load_settings
from ..secrets_setup import setup_secrets_environment
from ...run.config.settings import SettingValueNotFoundException


class SecretUnavailableException(SettingValueNotFoundException):
    """Exception raised when a required secret cannot be loaded."""
    def __init__(self, secret_name: str, variable_name: str = None):
        self.secret_name = secret_name
        self.variable_name = variable_name
        super().__init__(variable_name or secret_name, f"secret:{secret_name}", 
                        "Secret requires either project_id for Secret Manager or a default value")

# Bootstrap logging configuration
try:
    from ...run.config.logging import bootstrap_logging
    bootstrap_logging()
except ImportError:
    pass  # Logging bootstrap not available

logger = logging.getLogger(__name__)

# Global flag to track if load_env has been called
_load_env_called = False


def stage_env_var(name: str, load: bool, staged_env_vars: list, env_vars_manifest: list, 
                  test_config: dict, env_settings, app_config: dict, repo_root=None) -> None:
    """Recursively stage an environment variable, handling dependencies and conditions.
    
    Args:
        name: Environment variable name to stage
        load: Whether this variable should be loaded into os.environ at the end
        staged_env_vars: List of staged environment variable objects
        env_vars_manifest: Full environment variables manifest
        test_config: Test mode configuration (if available)
        env_settings: Environment settings (if available)
        app_config: Application configuration
        repo_root: Repository root path
    
    Raises:
        RuntimeError: If circular dependency detected or required dependency not found
        ValueError: If condition evaluation fails or value cannot be loaded
    """
    # Step 1: Check if already in staged_env_vars
    for staged_var in staged_env_vars:
        if staged_var["name"] == name:
            if staged_var["value"] == "***TEMP***":
                raise RuntimeError(f"Circular dependency detected for environment variable: {name}")
            # Update load flag if this invocation requires loading
            if load:
                staged_var["load"] = True
            return
    
    # Step 2: Add name to staged_env_vars with temporary value
    staged_var = {"name": name, "load": load, "value": "***TEMP***"}
    staged_env_vars.append(staged_var)
    
    # Find the environment variable definition in manifest
    env_var = None
    for var in env_vars_manifest:
        if var.name.upper() == name.upper():
            env_var = var
            break
    
    if not env_var:
        raise ValueError(f"Environment variable '{name}' not found in manifest")
    
    # Step 3: Check conditions and recursively call stage_env_var for dependencies
    if env_var.condition:
        for condition_key, condition_value in env_var.condition.items():
            # Recursively ensure the condition variable is staged
            stage_env_var(condition_key, False, staged_env_vars, env_vars_manifest, 
                         test_config, env_settings, app_config, repo_root)
    
    # Step 4: Evaluate conditions using staged_env_vars
    if env_var.condition:
        logger.debug(f"Evaluating conditions for {name}: {env_var.condition}")
        condition_met = True
        for condition_key, condition_value in env_var.condition.items():
            logger.debug(f"Checking condition {condition_key} = {condition_value}")
            # Find the staged value
            staged_value = None
            for staged in staged_env_vars:
                if staged["name"].upper() == condition_key.upper():
                    staged_value = staged["value"]
                    logger.debug(f"Found staged value for {condition_key}: {staged_value}")
                    break
            
            if staged_value is None:
                logger.debug(f"No staged value found for condition variable {condition_key}")
                condition_met = False
                break
            
            logger.debug(f"Condition check: {condition_key} = {staged_value} (expected: {condition_value})")
            if staged_value != condition_value:
                # Handle type conversion for boolean conditions
                if isinstance(condition_value, bool):
                    # Convert string values to boolean for comparison
                    if isinstance(staged_value, str):
                        if staged_value.lower() == 'true':
                            staged_value = True
                        elif staged_value.lower() == 'false':
                            staged_value = False
                        # If it's not 'true' or 'false', keep staged_value as is
                
                # Now compare the converted values
                if staged_value != condition_value:
                    condition_met = False
                    logger.debug(f"Condition failed: {condition_key} = {staged_value} != {condition_value}")
                    break
        
        if not condition_met:
            logger.debug(f"Conditions not met for {name}, setting value to None")
            staged_var["value"] = None
            return
        else:
            logger.debug(f"All conditions met for {name}, proceeding to load value")
    
    # Step 5: Process to load value from source
    value = None
    source = None
    
    if env_var.source.startswith('env-config:'):
        setting_key = env_var.source.split(':', 1)[1]
        
        # Check test config first, then env settings
        test_value = test_config.get(setting_key) if test_config else None
        config_value = getattr(env_settings, setting_key, None) if env_settings and hasattr(env_settings, setting_key) else None
        
        if test_value is not None:
            value = test_value
            source = 'test-config'
        elif config_value is not None:
            value = config_value
            source = 'env-config'
        
        # Use default value if no source provided one
        if value is None and env_var.default is not None:
            value = env_var.default
            source = 'default'
            
    elif env_var.source == 'app:id':
        if app_config and 'id' in app_config:
            value = app_config['id']
            source = 'app:id'
            
    elif env_var.source.startswith('secret:'):
        secret_name = env_var.source.split(':', 1)[1]
        logger.debug(f"Loading secret {secret_name} for {name}")
        
        # Use existing env_settings or create minimal one for secret loading
        if not env_settings:
            from .settings import Settings
            env_settings = Settings()
            logger.debug(f"Created minimal Settings object for {name}")
        
        logger.debug(f"Settings object has project_id: {getattr(env_settings, 'project_id', None)}")
        
        # Load the secret directly
        try:
            value = _get_secret_value(secret_name, env_settings, env_var.default, staged_env_vars)
            source = 'secret'
            logger.debug(f"Successfully loaded secret {secret_name} for {name}")
        except SecretUnavailableException:
            # Remove the staged variable before re-raising
            staged_env_vars.remove(staged_var)
            raise
        except Exception as e:
            logger.error(f"Failed to load secret {secret_name}: {e}")
            # Remove the staged variable before throwing
            staged_env_vars.remove(staged_var)
            raise ValueError(f"Failed to load secret {secret_name}: {e}")
            
    elif env_var.source == 'derived':
        if not env_var.method:
            staged_env_vars.remove(staged_var)
            raise ValueError(f"Derived variable {name} missing method")
            
        # Validate method name
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', env_var.method):
            staged_env_vars.remove(staged_var)
            raise ValueError(f"Invalid method name: {env_var.method}")
            
        # Check if method exists in this module
        if not hasattr(sys.modules[__name__], env_var.method):
            staged_env_vars.remove(staged_var)
            raise ValueError(f"Method {env_var.method} not found in {__name__}")
            
        # Call the method with available context
        method_func = getattr(sys.modules[__name__], env_var.method)
        try:
            value = method_func(staged_env_vars, env_settings)
            source = 'derived'
        except Exception as e:
            staged_env_vars.remove(staged_var)
            raise ValueError(f"Failed to derive {name} using {env_var.method}: {e}")
    
    # Handle default value expansion for placeholders like {env:app_id}
    if value and isinstance(value, str) and '{env:' in value:
        value = _expand_env_placeholders(value, staged_env_vars)
    
    # Step 6: Update final value in staged_env_vars
    if value is not None:
        # Convert boolean to lowercase string
        if isinstance(value, bool):
            value = str(value).lower()
        staged_var["value"] = str(value)
    else:
        # Remove the staged variable if no value could be loaded
        staged_env_vars.remove(staged_var)
        raise ValueError(f"Environment variable '{name}' could not be loaded from any source and has no default")


def _expand_env_placeholders(value: str, staged_env_vars: list) -> str:
    """Expand placeholders like {env:app_id} in default values.
    
    Args:
        value: String containing placeholders
        staged_env_vars: List of staged environment variables
        
    Returns:
        String with placeholders expanded
        
    Raises:
        ValueError: If a placeholder references a variable not in staged_env_vars
    """
    import re
    
    def replace_placeholder(match):
        placeholder = match.group(1)  # e.g., "env:app_id"
        if placeholder.startswith('env:'):
            var_name = placeholder[4:]  # e.g., "app_id"
            # Find the staged variable
            for staged in staged_env_vars:
                if staged["name"] == var_name.upper():
                    return staged["value"]
            raise ValueError(f"Placeholder {{env:{var_name}}} references undefined variable {var_name.upper()}")
        return match.group(0)  # Return unchanged if not env: placeholder
    
    return re.sub(r'\{([^}]+)\}', replace_placeholder, value)


def load_env(env_name: Optional[str] = None, test_mode: Optional[str] = None, 
             repo_root=None, quiet: bool = False, env_source: str = "unknown",
             env_var_names: Optional[list] = None) -> None:
    """Load configuration and set up all environment variables for build tasks.
    
    This is the single point of configuration loading. It stages environment variables
    from environment config, overlays test mode config, validates requirements, and
    applies all environment variables at once.
    
    Args:
        env_name: Environment name (e.g., 'dev', 'prod') - optional
        test_mode: Test mode name (e.g., 'unit', 'ai', 'db') - optional  
        repo_root: Repository root path (unused, kept for compatibility)
        quiet: If True, suppress environment variable display output
        env_source: How env_name was determined (e.g., '--config-env', 'task default')
        env_var_names: Optional list of environment variable names to load. If provided,
                      only these variables will be loaded from environment_variables.yaml.
                      All specified names must exist in the manifest.
        
    Raises:
        RuntimeError: If load_env has already been called
        ValueError: If configuration is insufficient
    """
    global _load_env_called
    if _load_env_called:
        raise RuntimeError("load_env() can only be called once per process")
    _load_env_called = True
    
    logger.debug(f"Loading configuration - env_name: {env_name}, test_mode: {test_mode}")
    
    # Step 1: Load environment variables manifest
    from .env_vars_manifest import load_env_vars_manifest
    full_env_vars_manifest = load_env_vars_manifest()
    
    # Step 1.5: Resolve groups and filter environment variables if specified
    if env_var_names:
        env_vars_manifest = _resolve_and_filter_env_vars(full_env_vars_manifest, env_var_names)
    else:
        env_vars_manifest = full_env_vars_manifest
    
    # Step 2: Stage environment variables from environment config and test mode
    staged_env_vars = []
    env_vars_info = []
    env_settings = None
    test_config = {}
    
    # Load environment config if specified
    if env_name:
        try:
            env_settings = load_settings(env_name)
            logger.debug(f"Loaded environment config for '{env_name}'")
        except Exception as e:
            print(f"❌ Failed to load environment '{env_name}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # Load test mode config if specified
    if test_mode:
        try:
            test_config = get_test_mode_config(test_mode)
            logger.debug(f"Loaded test mode config for '{test_mode}'")
        except Exception as e:
            print(f"❌ Failed to load test mode '{test_mode}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # We'll show CONFIGURATION SOURCE table after processing to get accurate counts
    
    # Step 3: Process environment variables from manifest
    app_config = _get_app_config()
    suite_settings_count = 0
    config_settings_count = 0
    
    for env_var in env_vars_manifest:
        # Skip if already set in environment
        if os.getenv(env_var.name):
            staged_env_vars.append({
                "name": env_var.name,
                "load": True,
                "value": os.getenv(env_var.name)
            })
            env_vars_info.append((env_var.name, os.getenv(env_var.name), 'environment'))
            continue
            
        # Skip TEST_* variables when not in test mode
        if env_var.name.startswith('TEST_') and not test_mode:
            logger.debug(f"Skipping {env_var.name} - not in test mode")
            continue
        
        # Use the new recursive stage_env_var function
        try:
            stage_env_var(env_var.name, True, staged_env_vars, full_env_vars_manifest, 
                         test_config, env_settings, app_config, repo_root)
        except SecretUnavailableException as e:
            print(f"❌ Secret '{e.secret_name}' is not available.", file=sys.stderr)
            print("\nTo resolve this, you can:", file=sys.stderr)
            print(f"  • Set PROJECT_ID environment variable to load from Google Secret Manager", file=sys.stderr)
            print(f"  • Use --config-env <environment> to load from environment config with project_id", file=sys.stderr)
            print(f"  • Add a 'default' value to the variable in environment_variables.yaml", file=sys.stderr)
            print(f"  • Set the {e.variable_name or e.secret_name} environment variable directly", file=sys.stderr)
            sys.exit(1)
        
        # Find the staged variable to get source info for display
        staged_var = None
        for staged in staged_env_vars:
            if staged["name"] == env_var.name:
                staged_var = staged
                break
        
        if staged_var and staged_var["value"] is not None:
            # Determine source for display
            if env_var.source.startswith('env-config:'):
                setting_key = env_var.source.split(':', 1)[1]
                test_value = test_config.get(setting_key) if test_config else None
                config_value = getattr(env_settings, setting_key, None) if env_settings and hasattr(env_settings, setting_key) else None
                
                if test_value is not None:
                    if config_value is not None:
                        source = 'test-config (\033[2;9menv-config\033[0m)'
                    else:
                        source = 'test-config'
                    suite_settings_count += 1
                elif config_value is not None:
                    source = 'env-config'
                    config_settings_count += 1
                else:
                    source = 'default'
            elif env_var.source == 'app:id':
                source = 'app:id'
            elif env_var.source.startswith('secret:'):
                source = 'secret'
            elif env_var.source == 'derived':
                source = 'derived'
            else:
                source = 'unknown'
            
            _stage_env_var({}, env_vars_info, env_var.name, staged_var["value"], source)
    
    # Step 4: All environment variables now processed via manifest loop above
    
    # Step 5: Validate that all processed variables have values
    # If conditions were met (variable was processed), it must have a value
    missing_vars = []
    for env_var in env_vars_manifest:
        # Skip TEST_* variables when not in test mode (same as processing loop)
        if env_var.name.startswith('TEST_') and not test_mode:
            continue
            
        # Check if variable was staged and has a value
        staged_var = None
        for staged in staged_env_vars:
            if staged["name"] == env_var.name:
                staged_var = staged
                break
        
        # If variable was staged but has no value, check if it's optional
        if staged_var and staged_var["value"] is None:
            # Skip if variable is marked as optional
            if not env_var.optional:
                missing_vars.append(env_var.name)
        elif staged_var is None:
            # Variable was not staged at all, check if it's optional
            if not env_var.optional:
                missing_vars.append(env_var.name)
    
    if missing_vars:
        if env_name:
            print(f"❌ Environment '{env_name}' incomplete. Missing: {', '.join(missing_vars)}", file=sys.stderr)
        else:
            print(f"❌ Test mode '{test_mode}' incomplete. Missing: {', '.join(missing_vars)}. Specify --config-env.", file=sys.stderr)
        sys.exit(1)
    
    # Step 6: Apply all staged environment variables to os.environ
    for staged_var in staged_env_vars:
        if staged_var["load"] and staged_var["value"] is not None:
            os.environ[staged_var["name"]] = staged_var["value"]
    
    # Step 7: Secrets are now handled directly in environment_variables.yaml
    # No need to call setup_secrets_environment since we consolidated secrets
    
    # Show CONFIGURATION SOURCE table (unless quiet)
    if not quiet:
        _show_configuration_source(env_name, test_mode, env_source, test_config, env_vars_manifest, suite_settings_count, config_settings_count)
    
    # Step 8: Display comprehensive environment variables table
    missing_count = _display_comprehensive_environment_variables(env_vars_manifest, staged_env_vars, test_mode, test_config, env_settings)
    
    # Exit with error if any variables are missing
    if missing_count > 0:
        sys.exit(1)


def _stage_env_var(staged_env_vars: Dict[str, str], env_vars_info: list, 
                   env_name: str, value: str, source: str) -> None:
    """Stage environment variable for later application."""
    staged_env_vars[env_name] = value
    env_vars_info.append((env_name, value, source))


def _display_comprehensive_environment_variables(env_vars_manifest: list, staged_env_vars: list, 
                                               test_mode: str, test_config: dict, env_settings) -> int:
    """Display comprehensive environment variables table showing all variables and their status.
    
    Returns:
        int: Number of missing variables (for exit code determination)
    """
    import sys
    
    print("\n" + "=" * 76, file=sys.stderr)
    print("🔧 ENVIRONMENT VARIABLES", file=sys.stderr)
    print("=" * 76, file=sys.stderr)
    print(f"{'VARIABLE':<24} {'VALUE':<23} {'SOURCE':<25}", file=sys.stderr)
    print("-" * 76, file=sys.stderr)
    
    processed_count = 0
    missing_count = 0
    skipped_count = 0
    
    for env_var in env_vars_manifest:
        # Skip TEST_* variables when not in test mode
        if env_var.name.startswith('TEST_') and not test_mode:
            continue
            
        # Find the staged variable
        staged_var = None
        for staged in staged_env_vars:
            if staged["name"] == env_var.name:
                staged_var = staged
                break
        
        # Determine display values based on status
        if staged_var is None:
            # Variable was not staged at all
            if env_var.optional:
                # Optional variable with no value - show as skipped
                variable_name = f"➖ {env_var.name}"
                display_value = "\033[90m(optional)\033[0m"  # Gray text
                status = "\033[90m(undefined)\033[0m"  # Gray text
                skipped_count += 1
            else:
                # Required variable missing - validation error
                variable_name = f"❌ {env_var.name}"
                display_value = "\033[90m(missing)\033[0m"  # Gray text
                status = "\033[31mREQUIRED\033[0m"  # Red text
                missing_count += 1
        elif staged_var["value"] is None:
            # Variable was staged but condition not met
            variable_name = f"➖ {env_var.name}"
            display_value = "\033[90m(skipped)\033[0m"  # Gray text
            status = "\033[90m(condition not met)\033[0m"  # Gray text
            skipped_count += 1
        else:
            # Variable was processed and has value
            variable_name = f"✅ {env_var.name}"
            value = staged_var["value"]
            # Truncate value to fit in column
            display_value = value if len(value) <= 23 else value[:20] + "..."
            
            # Determine source (this is simplified since we don't track source in staged_env_vars)
            status = 'staged'
            processed_count += 1
        
        # Handle alignment manually for colored text
        # Calculate visible length (excluding ANSI codes) for proper padding
        def visible_len(text):
            import re
            return len(re.sub(r'\033\[[0-9;]*m', '', text))
        
        def pad_to_width(text, width):
            visible = visible_len(text)
            padding = width - visible
            return text + ' ' * max(0, padding)
        
        variable_part = f"{variable_name:<24}"
        value_part = pad_to_width(display_value, 23)
        print(f"{variable_part} {value_part} {status}", file=sys.stderr)
    
    # Footer with validation summary
    print("-" * 76, file=sys.stderr)
    total_shown = processed_count + missing_count + skipped_count
    
    if missing_count > 0:
        status_text = f"\033[31mFAIL\033[0m"  # Red
        summary = f"📊 VALIDATION: {processed_count} of {total_shown} variables loaded - {status_text}"
    else:
        status_text = f"\033[32mPASS\033[0m"  # Green
        summary = f"📊 VALIDATION: {processed_count} of {total_shown} variables loaded - {status_text}"
    
    print(f"{summary}", file=sys.stderr)
    if skipped_count > 0:
        print(f"   └─ {skipped_count} skipped (conditions not met)", file=sys.stderr)
    if missing_count > 0:
        print(f"   └─ {missing_count} missing (validation failed)", file=sys.stderr)
    
    print("=" * 76, file=sys.stderr)
    
    return missing_count


def _get_app_config() -> Optional[Dict[str, Any]]:
    """Get application configuration from app.yaml."""
    from pathlib import Path
    import yaml
    
    app_yaml_path = Path.cwd() / "config" / "app.yaml"
    if not app_yaml_path.exists():
        return None
    
    try:
        with open(app_yaml_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _show_configuration_source(env_name: Optional[str], test_mode: Optional[str], 
                              env_source: str, test_config: dict, env_vars_manifest: list,
                              suite_settings_count: int, config_settings_count: int) -> None:
    """Display CONFIGURATION SOURCE table showing where configuration comes from."""
    import sys
    
    # Color codes
    CYAN = '\033[1;36m'  # Bright cyan for values
    GRAY = '\033[2m'     # Dim gray for "not specified"
    RESET = '\033[0m'
    
    print("\n" + "="*50, file=sys.stderr)
    print("🔧 CONFIGURATION SOURCE", file=sys.stderr)
    print("="*50, file=sys.stderr)
    
    # Show Suite section only when test_mode is provided
    if test_mode:
        print(f"Test Suite: {CYAN}{test_mode}{RESET}", file=sys.stderr)
        print(f"  └─ As per: invoke test <suite>", file=sys.stderr)
        print(f"  └─ Source: tests.yaml", file=sys.stderr)
        
        # Show test paths if available
        if test_config and 'tests' in test_config and 'paths' in test_config['tests']:
            test_paths = test_config['tests']['paths']
            colored_paths = [f"{CYAN}{path}{RESET}" for path in test_paths]
            paths_str = ", ".join(colored_paths)
            print(f"  └─ Test Paths: {paths_str}", file=sys.stderr)
        
        # Show count of settings from test mode
        print(f"  └─ {CYAN}{suite_settings_count}{RESET} settings from suite", file=sys.stderr)
        print("", file=sys.stderr)  # Empty line between sections
    
    # Show Config Environment section
    if env_name:
        print(f"Config Environment: {CYAN}{env_name}{RESET}", file=sys.stderr)
        print(f"  └─ As per: {env_source}", file=sys.stderr)
        print(f"  └─ Source: environments.yaml", file=sys.stderr)
        
        # Show count of settings from config environment
        print(f"  └─ {CYAN}{config_settings_count}{RESET} settings from config", file=sys.stderr)
        
        # Show helpful tip when config environment is unused
        if config_settings_count == 0:
            print(f"    └─ \033[33m💡 Tip: --config-env can be omitted for {CYAN}{test_mode}{RESET} suite\033[0m", file=sys.stderr)
    else:
        print(f"Config Environment: {GRAY}(none){RESET}", file=sys.stderr)
    
    print("="*50, file=sys.stderr)



def derive_api_url(staged_env_vars, env_settings):
    """Derive API URL based on available settings and staged environment variables."""
    
    # 1. Environment variable override (highest priority)
    if env_var := os.getenv("API_TESTING_URL"):
        return env_var
    
    # 2. Local execution (local=true) - use localhost with optional port
    if env_settings and env_settings.local:
        port = staged_env_vars.get("PORT")
        if port:
            return f"http://localhost:{port}"
        else:
            return "http://localhost"  # No port = use HTTP default (80)
    
    # 3. Cloud environment (project_id present) - get actual Cloud Run URL via GCP API
    project_id = staged_env_vars.get("PROJECT_ID")
    if project_id:
        app_id = staged_env_vars.get("APP_ID")
        if not app_id:
            raise RuntimeError("Cannot derive Cloud Run URL: APP_ID is required")
        from multi_eden.internal.gcp import get_cloud_run_service_url
        service_name = f"{app_id}-api"
        return get_cloud_run_service_url(project_id, service_name)
    
    # 4. No valid configuration - cannot derive URL
    raise RuntimeError("Cannot derive API URL: neither local=true nor project_id specified")





def _get_secret_value(secret_name: str, settings, default_value: str = None, staged_env_vars: list = None) -> str:
    """Get secret value from Secret Manager or use default.
    
    Args:
        secret_name: Name of the secret (e.g., 'gemini-api-key')
        settings: Settings object with project_id
        default_value: Default value to use if Secret Manager not available
        staged_env_vars: List of staged environment variables for placeholder expansion
        
    Returns:
        Secret value
        
    Raises:
        RuntimeError: If project_id is set but Secret Manager fails
    """
    project_id = getattr(settings, 'project_id', None)
    
    # If project_id is set, demand success from Secret Manager
    if project_id:
        from ..secrets.secrets_manager import get_secret_manager_value
        value = get_secret_manager_value(project_id, secret_name)
        if not value:
            raise RuntimeError(f"Secret '{secret_name}' not found in Secret Manager for project '{project_id}'")
        return value
    
    # Only use default value if no project_id (local development without Secret Manager)
    if default_value:
        # Expand placeholders in default value using staged environment variables
        if '{env:' in default_value:
            if staged_env_vars is None:
                raise RuntimeError(f"Secret '{secret_name}' requires staged environment variables for placeholder expansion")
            expanded = _expand_env_placeholders(default_value, staged_env_vars)
            return expanded
        return default_value
    
    raise SecretUnavailableException(secret_name)


def _resolve_and_filter_env_vars(env_vars_manifest: list, env_var_names: list) -> list:
    """Resolve groups and filter environment variables based on specified names.
    
    Args:
        env_vars_manifest: Full list of environment variable definitions
        env_var_names: List of environment variable names and group names to include
        
    Returns:
        Filtered list of environment variable definitions
        
    Raises:
        ValueError: If a specified variable name or group name is not found
    """
    import yaml
    from pathlib import Path
    
    # Load groups from environment_variables.yaml
    env_vars_yaml_path = Path(__file__).parent / 'environment_variables.yaml'
    if not env_vars_yaml_path.exists():
        raise FileNotFoundError(f"environment_variables.yaml not found: {env_vars_yaml_path}")
    
    with open(env_vars_yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    
    groups = config.get('groups', {})
    
    # Build set of required environment variable names
    required_names = set()
    
    for name in env_var_names:
        name = name.strip()
        
        # Check if it's a group name
        if name in groups:
            required_names.update(groups[name])
        else:
            # Check if it's an individual environment variable name
            var_exists = any(env_var.name == name for env_var in env_vars_manifest)
            if not var_exists:
                raise ValueError(f"Environment variable or group '{name}' not found in environment_variables.yaml")
            required_names.add(name)
    
    # Filter the manifest to only include required variables
    filtered_manifest = []
    for env_var in env_vars_manifest:
        if env_var.name in required_names:
            filtered_manifest.append(env_var)
    
    logger.debug(f"Filtered environment variables: {[var.name for var in filtered_manifest]}")
    return filtered_manifest
