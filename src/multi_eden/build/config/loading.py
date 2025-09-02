"""Dynamic environment configuration loading for build tasks.

This simplified approach:
1. Load everything from env-config first
2. Load everything from test-config (which overwrites/takes priority)  
3. Track what we've loaded along the way
4. Only display what we actually loaded (not all system env vars)

No manifests needed - configs define their own environment variables.
"""

import os
import sys
import logging
from typing import Optional

from .test_mode import get_test_mode_config
from ...run.config.settings import SettingValueNotFoundException
import yaml
from pathlib import Path


def _load_yaml_config(file_path: str) -> dict:
    """Load YAML config file, return empty dict if not found."""
    try:
        with open(file_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        logger.warning(f"Failed to load config from {file_path}: {e}")
        return {}


def _load_environment_config(env_name: str) -> dict:
    """Load environment config by merging SDK defaults with app overrides."""
    # Load SDK default environments
    sdk_path = Path(__file__).parent / "environments.yaml"
    sdk_config = _load_yaml_config(str(sdk_path))
    sdk_environments = sdk_config.get('environments', {})
    
    # Load app-specific environment overrides (may not exist)
    app_config = _load_yaml_config("config/environments.yaml")
    app_environments = app_config.get('environments', {})
    
    # Merge environments: for each environment, merge SDK defaults with app overrides
    merged_environments = {}
    for env_name_key in sdk_environments:
        merged_environments[env_name_key] = sdk_environments[env_name_key].copy()
        if env_name_key in app_environments:
            # Merge app-specific overrides into SDK defaults
            merged_environments[env_name_key].update(app_environments[env_name_key])
    
    # Add any app-only environments (not in SDK)
    for env_name_key in app_environments:
        if env_name_key not in merged_environments:
            merged_environments[env_name_key] = app_environments[env_name_key]
    
    if env_name not in merged_environments:
        available_envs = list(merged_environments.keys())
        raise ValueError(f"Unknown config environment '{env_name}'. Available: {available_envs}")
    
    return merged_environments[env_name]


class SecretUnavailableException(SettingValueNotFoundException):
    """Exception raised when a required secret cannot be loaded."""
    def __init__(self, secret_name: str, variable_name: str = None):
        self.secret_name = secret_name
        self.variable_name = variable_name
        super().__init__(variable_name or secret_name, f"secret:{secret_name}", 
                        "Secret requires either project_id for Secret Manager or local: true with default value")

# Bootstrap logging configuration
try:
    from ...run.config.logging import bootstrap_logging
    bootstrap_logging()
except ImportError:
    pass  # Logging bootstrap not available

logger = logging.getLogger(__name__)

# Global flag to track if load_env has been called
_load_env_called = False


def _get_secret_from_manager(project_id: str, secret_name: str) -> str:
    """Load secret from Google Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": secret_path})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        raise ValueError(f"Failed to load secret '{secret_name}' from Secret Manager: {e}")


def load_env_dynamic(env_name: Optional[str] = None, test_mode: Optional[str] = None, 
                    repo_root=None, quiet: bool = False, env_source: str = "unknown",
                    env_var_names: Optional[list] = None) -> None:
    """Load environment variables dynamically from available sources.
    
    Process:
    1. Load everything from env-config first
    2. Load everything from test-config (overwrites/takes priority)
    3. Track what we've loaded along the way
    4. Only display what we actually loaded
    """
    global _load_env_called
    if _load_env_called:
        raise RuntimeError("load_env() can only be called once per process")
    _load_env_called = True
    
    logger.debug(f"Dynamic loading - env_name: {env_name}, test_mode: {test_mode}")
    
    # Track variables we load: name -> (value, source)
    loaded_vars = {}
    project_id = None
    
    # Step 1: Load from base environment (if exists)
    try:
        base_config = _load_environment_config('base')
        for key, value in base_config.items():
            env_var_name = key.upper()
            if key == 'project_id':
                project_id = value
            loaded_vars[env_var_name] = (value, 'base-config')
        logger.debug(f"Loaded {len(base_config)} variables from base-config")
    except Exception:
        # Base config is optional, ignore if not found
        logger.debug("No base environment config found")
    
    # Step 2: Load from environment config (overwrites base)
    if env_name:
        try:
            env_config = _load_environment_config(env_name)
            for key, value in env_config.items():
                env_var_name = key.upper()
                if key == 'project_id':
                    project_id = value
                loaded_vars[env_var_name] = (value, 'env-config')
            logger.debug(f"Loaded {len(env_config)} variables from env-config '{env_name}'")
        except Exception as e:
            print(f"❌ Failed to load environment '{env_name}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # Step 3: Load from test config (overwrites base and env-config)
    if test_mode:
        try:
            test_config = get_test_mode_config(test_mode)
            if hasattr(test_config, 'environment'):
                for key, value in test_config.environment.items():
                    env_var_name = key.upper()
                    if key == 'project_id':
                        project_id = value
                    # Overwrite any existing value from env-config
                    loaded_vars[env_var_name] = (value, 'test-config')
                logger.debug(f"Loaded {len(test_config.environment)} variables from test-config '{test_mode}'")
        except Exception as e:
            print(f"❌ Failed to load test mode '{test_mode}': {e}", file=sys.stderr)
            sys.exit(1)
    
    # Step 3: Process and set all loaded variables (collect errors, don't exit immediately)
    processed_vars = []
    failed_vars = []
    
    for name, (value, source) in loaded_vars.items():
        try:
            # Check if this declared variable is already set in environment (takes highest priority)
            if name in os.environ:
                env_value = os.environ[name]
                processed_vars.append((name, env_value, 'env-var'))
                logger.debug(f"Using existing {name}={env_value} (from env-var)")
                continue
            
            # Handle secret: prefix
            original_source = source
            if isinstance(value, str) and value.startswith('secret:'):
                secret_name = value[7:]  # Remove 'secret:' prefix
                if project_id:
                    value = _get_secret_from_manager(project_id, secret_name)
                    source = 'secret'  # Change source to indicate it's a secret
                    logger.debug(f"Loaded secret '{secret_name}' from Secret Manager")
                else:
                    raise SecretUnavailableException(secret_name, name)
            
            # Convert value to string for environment variable
            if isinstance(value, bool):
                env_value = 'true' if value else 'false'
            else:
                env_value = str(value)
            
            # Set environment variable
            os.environ[name] = env_value
            processed_vars.append((name, env_value, source))
            logger.debug(f"Set {name}={env_value} (from {source})")
            
        except SecretUnavailableException as e:
            failed_vars.append((name, e))
            logger.debug(f"Failed to load secret for {name}: {e.secret_name}")
        except Exception as e:
            failed_vars.append((name, e))
            logger.debug(f"Failed to process {name}: {e}")
    
    # Step 4: Display results (if not quiet)
    if not quiet:
        display_env_vars_dynamic(processed_vars, failed_vars, test_mode, env_name, env_source)
    
    # Step 5: Exit with error code if there were failures
    if failed_vars:
        print("\n" + "=" * 50, file=sys.stderr)
        print("❌ CONFIGURATION ERRORS", file=sys.stderr)
        print("=" * 50, file=sys.stderr)
        
        for name, error in failed_vars:
            if isinstance(error, SecretUnavailableException):
                print(f"\n❌ Secret '{error.secret_name}' is not available for {name}.", file=sys.stderr)
                print("\nTo resolve this, you can:", file=sys.stderr)
                print(f"  • Set MULTI_EDEN_ENV=<environment> where environment config has project_id set", file=sys.stderr)
                print(f"  • Use --config-env <environment> where environment config has project_id set", file=sys.stderr)
                print(f"  • Replace 'secret:{error.secret_name}' with a literal value in the config", file=sys.stderr)
                print(f"  • Set the {error.variable_name or error.secret_name} environment variable directly", file=sys.stderr)
                print(f"\nNote: PROJECT_ID env var won't work - only declared config variables are processed.", file=sys.stderr)
            else:
                print(f"\n❌ Failed to process {name}: {error}", file=sys.stderr)
        sys.exit(1)


def display_env_vars_dynamic(processed_vars, failed_vars, test_mode, env_name, env_source):
    """Display the environment variables table for dynamic loading."""
    
    # Configuration source table
    print("\n" + "=" * 50)
    print("🔧 CONFIGURATION SOURCE")
    print("=" * 50)
    
    if test_mode:
        print(f"Test Suite: {test_mode}")
        print(f"  └─ As per: invoke test <suite>")
        print(f"  └─ Source: tests.yaml")
        
        # Get test paths if available
        try:
            test_config = get_test_mode_config(test_mode)
            if hasattr(test_config, 'tests') and isinstance(test_config.tests, dict):
                test_paths = test_config.tests.get('paths', [])
                if test_paths:
                    print(f"  └─ Test Paths: {', '.join(test_paths)}")
        except:
            pass
    
    if env_name:
        print(f"Config Environment: {env_name}")
    else:
        print("Config Environment: (none)")
    
    print("=" * 50)
    
    # Environment variables table
    print("\n" + "=" * 76)
    print("🔧 ENVIRONMENT VARIABLES")
    print("=" * 76)
    print(f"{'VARIABLE':<25} {'VALUE':<25} {'SOURCE':<25}")
    print("-" * 76)
    
    # Sort variables by name for consistent display
    processed_vars.sort(key=lambda x: x[0])
    
    # Combine all variables for sorted display
    all_vars = []
    
    # Add successful variables
    for name, value, source in processed_vars:
        # Limit value to 24 chars max to ensure space before SOURCE column
        if len(value) > 24:
            display_value = value[:21] + "..."
        else:
            display_value = value
        all_vars.append((name, "✅", display_value, source))
    
    # Add failed variables
    for name, error in failed_vars:
        if isinstance(error, SecretUnavailableException):
            all_vars.append((name, "❌", "(missing)", "secret"))
        else:
            all_vars.append((name, "❌", "(error)", "unknown"))
    
    # Sort all variables by name and display
    all_vars.sort(key=lambda x: x[0])
    for name, status, value, source in all_vars:
        print(f"{status} {name:<23} {value:<24} {source:<25}")
    
    print("-" * 76)
    total_vars = len(processed_vars) + len(failed_vars)
    status = "PASS" if len(failed_vars) == 0 else "FAIL"
    print(f"📊 VALIDATION: {len(processed_vars)} of {total_vars} variables loaded - {status}")
    print("=" * 76)


# Alias the new dynamic function as the main load_env function
load_env = load_env_dynamic
