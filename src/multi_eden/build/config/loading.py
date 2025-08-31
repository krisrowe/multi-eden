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

logger = logging.getLogger(__name__)

# Global flag to track if load_env has been called
_load_env_called = False


def load_env(env_name: Optional[str] = None, test_mode: Optional[str] = None, 
             repo_root=None, quiet: bool = False, env_source: str = "unknown") -> None:
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
    env_vars_manifest = load_env_vars_manifest()
    
    # Step 2: Stage environment variables from environment config and test mode
    staged_env_vars = {}
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
        # Check conditions first
        if env_var.condition:
            condition_met = True
            for condition_key, condition_value in env_var.condition.items():
                # Check condition in test config first, then env settings
                actual_value = None
                if condition_key in test_config:
                    actual_value = test_config[condition_key]
                elif env_settings and hasattr(env_settings, condition_key):
                    actual_value = getattr(env_settings, condition_key)
                
                if actual_value != condition_value:
                    condition_met = False
                    break
            
            if not condition_met:
                logger.debug(f"Skipping {env_var.name} - condition not met: {env_var.condition}")
                continue
        
        # Process the environment variable based on its source
        if env_var.source.startswith('env-config:'):
            setting_key = env_var.source.split(':', 1)[1]
            
            # Check test config first (overlay), then env settings
            value = None
            source = None
            
            # Check both sources to detect overrides
            test_value = test_config.get(setting_key) if test_config else None
            config_value = getattr(env_settings, setting_key, None) if env_settings and hasattr(env_settings, setting_key) else None
            
            # Determine final value and source description
            if test_value is not None:
                value = test_value
                if config_value is not None:
                    source = 'test-config (\033[2;9menv-config\033[0m)'
                else:
                    source = 'test-config'
                suite_settings_count += 1
            elif config_value is not None:
                value = config_value
                source = 'env-config'
                config_settings_count += 1
            else:
                value = None
                source = None
            
            if value is not None:
                # Convert boolean to lowercase string
                if isinstance(value, bool):
                    value = str(value).lower()
                _stage_env_var(staged_env_vars, env_vars_info, env_var.name, str(value), source)
                
        elif env_var.source == 'app:id':
            if app_config and 'id' in app_config:
                _stage_env_var(staged_env_vars, env_vars_info, env_var.name, app_config['id'], 'app:id')
                
        elif env_var.source == 'derived' and env_var.method == 'derive_api_url':
            # Derive API URL for out-of-process API
            project_id = staged_env_vars.get('PROJECT_ID')
            app_id = staged_env_vars.get('APP_ID', 'multi-eden-app')
            if project_id and app_id:
                api_url = f"https://{app_id}-api-djxpmqqvhq-uc.a.run.app"
                _stage_env_var(staged_env_vars, env_vars_info, env_var.name, api_url, 'derived')
    
    # Step 4: Add test-specific environment variables not in manifest
    if test_mode:
        # These are test framework specific and not in the general manifest
        if 'api_in_memory' in test_config:
            _stage_env_var(staged_env_vars, env_vars_info, 'TEST_API_IN_MEMORY', str(test_config['api_in_memory']).lower(), 'test-config')
        if 'omit_integration' in test_config:
            _stage_env_var(staged_env_vars, env_vars_info, 'TEST_OMIT_INTEGRATION', str(test_config['omit_integration']).lower(), 'test-config')
    
    # Step 5: Validate minimum requirements
    required_vars = ['STUB_AI', 'STUB_DB', 'CUSTOM_AUTH_ENABLED']
    missing_vars = [var for var in required_vars if var not in staged_env_vars]
    
    if missing_vars:
        if env_name:
            print(f"❌ Environment '{env_name}' incomplete. Missing: {', '.join(missing_vars)}", file=sys.stderr)
        else:
            print(f"❌ Test mode '{test_mode}' incomplete. Missing: {', '.join(missing_vars)}. Specify --config-env.", file=sys.stderr)
        sys.exit(1)
    
    # Step 6: Apply all staged environment variables to os.environ
    for var_name, var_value in staged_env_vars.items():
        os.environ[var_name] = var_value
    
    # Step 7: Set up secrets (create Settings object from staged vars)
    if not env_settings:
        from .settings import Settings
        env_settings = Settings()
        
    # Update settings object with staged values for secrets setup
    env_settings.stub_ai = staged_env_vars.get('STUB_AI', 'true').lower() == 'true'
    env_settings.stub_db = staged_env_vars.get('STUB_DB', 'true').lower() == 'true'
    env_settings.custom_auth_enabled = staged_env_vars.get('CUSTOM_AUTH_ENABLED', 'true').lower() == 'true'
    env_settings.api_in_memory = staged_env_vars.get('TEST_API_IN_MEMORY', 'true').lower() == 'true'
    env_settings.local = True  # Default for test scenarios
    env_settings.project_id = staged_env_vars.get('PROJECT_ID')
    env_settings.app_id = staged_env_vars.get('APP_ID')
    
    try:
        setup_secrets_environment(env_settings)
    except Exception as e:
        print(f"❌ Failed to set up secrets: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Show CONFIGURATION SOURCE table (unless quiet)
    if not quiet:
        _show_configuration_source(env_name, test_mode, env_source, test_config, env_vars_manifest, suite_settings_count, config_settings_count)
    
    # Step 8: Display build environment variables (always shown)
    _display_environment_variables(env_vars_info)
    if not staged_env_vars.get('PROJECT_ID'):
        print(f"   ✅ No project ID - using local configuration", file=sys.stderr)


def _stage_env_var(staged_env_vars: Dict[str, str], env_vars_info: list, 
                   env_name: str, value: str, source: str) -> None:
    """Stage environment variable for later application."""
    staged_env_vars[env_name] = value
    env_vars_info.append((env_name, value, source))


def _display_environment_variables(env_vars_info: list) -> None:
    """Display environment variables table."""
    if not env_vars_info:
        return
        
    print("\n" + "=" * 74, file=sys.stderr)
    print("🔧 ENVIRONMENT VARIABLES", file=sys.stderr)
    print("=" * 74, file=sys.stderr)
    print(f"{'VARIABLE':<21} {'VALUE':<21} {'SOURCE':<26}", file=sys.stderr)
    print("-" * 74, file=sys.stderr)
    
    for env_var, value, source in env_vars_info:
        # Truncate long values for display (max 21 chars)
        display_value = value if len(value) <= 21 else value[:18] + "..."
        print(f"{env_var:<21} {display_value:<21} {source:<26}", file=sys.stderr)
    
    print("=" * 74, file=sys.stderr)


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
        total_settings = len(env_vars_manifest)
        print(f"  └─ {CYAN}{suite_settings_count} of {total_settings}{RESET} settings from suite", file=sys.stderr)
        print("", file=sys.stderr)  # Empty line between sections
    
    # Show Config Environment section
    if env_name:
        print(f"Config Environment: {CYAN}{env_name}{RESET}", file=sys.stderr)
        print(f"  └─ As per: {env_source}", file=sys.stderr)
        print(f"  └─ Source: environments.yaml", file=sys.stderr)
        
        # Show count of settings from config environment
        total_settings = len(env_vars_manifest)
        print(f"  └─ {CYAN}{config_settings_count} of {total_settings}{RESET} settings from config", file=sys.stderr)
        
        # Show helpful tip when config environment is unused
        if config_settings_count == 0:
            print(f"    └─ \033[33m💡 Tip: --config-env can be omitted for {CYAN}{test_mode}{RESET} suite\033[0m", file=sys.stderr)
    else:
        print(f"Config Environment: {GRAY}(not specified){RESET}", file=sys.stderr)
    
    print("="*50, file=sys.stderr)
