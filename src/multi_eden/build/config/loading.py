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
        # Skip TEST_* variables when not in test mode
        if env_var.name.startswith('TEST_') and not test_mode:
            logger.debug(f"Skipping {env_var.name} - not in test mode")
            continue
            
        # Check explicit conditions
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
            
            # Use default value if no source provided one
            if value is None and env_var.default is not None:
                value = env_var.default
                source = 'default'
            
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
    
    # Step 4: All environment variables now processed via manifest loop above
    
    # Step 5: Validate that all processed variables have values
    # If conditions were met (variable was processed), it must have a value
    missing_vars = []
    for env_var in env_vars_manifest:
        # Skip TEST_* variables when not in test mode (same as processing loop)
        if env_var.name.startswith('TEST_') and not test_mode:
            continue
            
        # Check if explicit conditions are met (same logic as processing loop)
        condition_met = True
        if env_var.condition:
            for key, expected_value in env_var.condition.items():
                actual_value = test_config.get(key) if test_config else None
                if actual_value != expected_value:
                    condition_met = False
                    break
        
        # If conditions met but no value staged, check if it's optional
        if condition_met and env_var.name not in staged_env_vars:
            # Skip if variable is marked as optional
            if not env_var.optional:
                missing_vars.append(env_var.name)
    
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
    # Use dynamic mapping based on environment variable names
    for env_var_name, env_var_value in staged_env_vars.items():
        # Convert env var name to settings field name (lowercase with underscores)
        field_name = env_var_name.lower()
        
        # Skip if settings object doesn't have this field
        if not hasattr(env_settings, field_name):
            continue
            
        # Convert string values to appropriate types
        if env_var_value.lower() in ('true', 'false'):
            # Boolean conversion
            setattr(env_settings, field_name, env_var_value.lower() == 'true')
        elif env_var_value.isdigit():
            # Integer conversion
            setattr(env_settings, field_name, int(env_var_value))
        else:
            # String value
            setattr(env_settings, field_name, env_var_value)
    
    # Set defaults for fields not covered by environment variables
    env_settings.local = True  # Default for test scenarios
    
    try:
        setup_secrets_environment(env_settings)
    except Exception as e:
        print(f"❌ Failed to set up secrets: {e}", file=sys.stderr)
        sys.exit(1)
    
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


def _display_comprehensive_environment_variables(env_vars_manifest: list, staged_env_vars: dict, 
                                               test_mode: str, test_config: dict, env_settings) -> int:
    """Display comprehensive environment variables table showing all variables and their status.
    
    Returns:
        int: Number of missing variables (for exit code determination)
    """
    import sys
    
    print("\n" + "=" * 74, file=sys.stderr)
    print("🔧 ENVIRONMENT VARIABLES", file=sys.stderr)
    print("=" * 74, file=sys.stderr)
    print(f"{'VARIABLE':<24} {'VALUE':<21} {'SOURCE':<25}", file=sys.stderr)
    print("-" * 74, file=sys.stderr)
    
    processed_count = 0
    missing_count = 0
    skipped_count = 0
    
    for env_var in env_vars_manifest:
        # Skip TEST_* variables when not in test mode
        if env_var.name.startswith('TEST_') and not test_mode:
            continue
            
        # Check if conditions are met (same logic as processing loop)
        condition_met = True
        if env_var.condition:
            for condition_key, condition_value in env_var.condition.items():
                actual_value = None
                if condition_key in test_config:
                    actual_value = test_config[condition_key]
                elif env_settings and hasattr(env_settings, condition_key):
                    actual_value = getattr(env_settings, condition_key)
                
                if actual_value != condition_value:
                    condition_met = False
                    break
        
        # Determine display values based on status
        if not condition_met:
            # Condition not met - show as skipped
            variable_name = f"➖ {env_var.name}"
            display_value = "\033[90m(skipped)\033[0m"  # Gray text
            status = "\033[90m(condition not met)\033[0m"  # Gray text
            skipped_count += 1
        elif env_var.name in staged_env_vars:
            # Variable was processed and has value
            variable_name = f"✅ {env_var.name}"
            value = staged_env_vars[env_var.name]
            # Truncate value to fit in column
            display_value = value if len(value) <= 21 else value[:18] + "..."
            
            # Determine source
            if env_var.source.startswith('env-config:'):
                setting_key = env_var.source.split(':', 1)[1]
                test_value = test_config.get(setting_key) if test_config else None
                config_value = getattr(env_settings, setting_key, None) if env_settings and hasattr(env_settings, setting_key) else None
                
                if test_value is not None:
                    if config_value is not None:
                        status = 'test-config \033[90m(\033[9menv-config\033[0m\033[90m)\033[0m'
                    else:
                        status = 'test-config'
                elif config_value is not None:
                    status = 'env-config'
                else:
                    status = 'default'
            elif env_var.source == 'app:id':
                status = 'app:id'
            elif env_var.source == 'derived':
                status = 'derived'
            else:
                status = 'unknown'
            
            processed_count += 1
        else:
            # Variable should be processed but has no value
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
        value_part = pad_to_width(display_value, 21)
        print(f"{variable_part} {value_part} {status}", file=sys.stderr)
    
    # Footer with validation summary
    print("-" * 74, file=sys.stderr)
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
    
    print("=" * 74, file=sys.stderr)
    
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
