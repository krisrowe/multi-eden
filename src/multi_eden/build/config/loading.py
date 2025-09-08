"""
New environment loading system with inheritance, caching, and clean state management.
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel
import yaml

from .exceptions import (
    ConfigException,
    ProjectIdRequiredException,
    NoProjectIdForGoogleSecretsException,
    NoKeyCachedForLocalSecretsException,
    LocalSecretNotFoundException,
    GoogleSecretNotFoundException,
    # Legacy exceptions for backward compatibility
    EnvironmentLoadError,
    EnvironmentNotFoundError,
    SecretUnavailableException,
    ProjectIdNotFoundException,
    ProjectsFileNotFoundException
)
from .secrets import get_secret

logger = logging.getLogger(__name__)


class StagingResult(BaseModel):
    """Result of staging environment variables with validators."""
    staged_vars: Dict[str, Tuple[str, str]]
    validator_names: List[str]

# Track last successful load: {"params": {...}, "loaded_vars": {...}}
_last_load = None


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


def _load_environment_variables_staged(env_config: Dict[str, Any], layer_name: str, fail_on_secret_error: bool) -> Dict[str, Tuple[str, str]]:
    """
    Load environment variables into a staging dictionary without touching os.environ.
    
    Args:
        env_config: Environment configuration dictionary
        layer_name: Name of the environment layer being loaded
        fail_on_secret_error: If True, raise SecretUnavailableException on any secret failure.
                             If False, skip failed secrets and continue with others.
    
    Returns:
        Dictionary of staged variables: {var_name: (value, source)}
        
    Raises:
        SecretUnavailableException: If fail_on_secret_error=True and any secret fails
    """
    staged_vars = {}
    
    for key, value in env_config.get('env', {}).items():
        env_var_name = key.upper()
        logger.debug(f"Processing variable '{env_var_name}' from layer '{layer_name}'")
        
        # Check if already in os.environ (highest priority)
        if env_var_name in os.environ:
            existing_value = os.environ[env_var_name]
            logger.debug(f"Variable '{env_var_name}' already set to '{existing_value}' - keeping existing")
            staged_vars[env_var_name] = (existing_value, 'os.environ')
            continue
        
        # Process new value (not in os.environ)
        try:
            processed_value = _process_value(value, env_var_name, layer_name)
            # Simple decision: if it's a secret, don't log the value
            if isinstance(value, str) and value.startswith('secret:'):
                logger.debug(f"Variable '{env_var_name}' not set - loading new secret value from layer '{layer_name}'")
            else:
                logger.debug(f"Variable '{env_var_name}' not set - loading new value '{processed_value}' from layer '{layer_name}'")
            staged_vars[env_var_name] = (processed_value, 'env')
            
        except (SecretUnavailableException, ProjectIdNotFoundException, ProjectsFileNotFoundException, 
                NoKeyCachedForLocalSecretsException, LocalSecretNotFoundException, GoogleSecretNotFoundException, 
                NoProjectIdForGoogleSecretsException, ProjectIdRequiredException) as e:
            if fail_on_secret_error:
                logger.error(f"Failed to load configuration for {env_var_name}: {e}")
                raise  # Re-raise the exception to fail the entire load
            else:
                logger.error(f"Failed to load configuration for {env_var_name}: {e}")
                logger.debug(f"Variable '{env_var_name}' not set - skipping due to configuration error: {e}")
                # Don't set any value - continue loading other variables
                
        except Exception as e:
            logger.error(f"Failed to process {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to processing error: {e}")
            # Don't set any value - continue loading other variables
    
    return staged_vars


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

def get_project_id_from_projects_file(env_name: str, var_name: str = "PROJECT_ID", configured_layer: str = None) -> str:
    """Get project ID from .projects file for specific environment."""
    projects_file = Path(".projects")
    
    if not projects_file.exists():
        raise ProjectsFileNotFoundException(
            f".projects file not found. Create it with: invoke register-project {env_name} your-project-id",
            env_name=env_name,
            var_name=var_name,
            configured_layer=configured_layer
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
        f"Add it with: invoke register-project {env_name} your-project-id",
        env_name=env_name,
        var_name=var_name,
        configured_layer=configured_layer,
        projects_file_exists=True
    )


def _process_value(value: Any, var_name: str = None, layer_name: str = None) -> str:
    """Process value with different source schemes (secret:, $.projects., etc.)."""
    if not isinstance(value, str):
        logger.debug(f"Converting non-string value to string: {value}")
        return str(value)
    
    if value.startswith('secret:'):
        secret_name = value[7:]  # Remove 'secret:' prefix
        logger.debug(f"Processing secret reference: {value} -> {secret_name}")
        return get_secret(secret_name)  # Uses cached version, throws appropriate exceptions
    elif value.startswith('$.projects.'):
        # Handle project IDs from .projects file
        env_name = value.replace('$.projects.', '')
        project_id = get_project_id_from_projects_file(env_name, var_name, layer_name)
        logger.debug(f"Processing project ID reference: {value} -> {project_id}")
        return project_id
    else:
        logger.debug(f"Using literal value: {value}")
        return value


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
                processed_value = _process_value(value, env_var_name, layer_name)
                
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
            processed_value = _process_value(value, env_var_name, layer_name)
            # Simple decision: if it's a secret, don't log the value
            if isinstance(value, str) and value.startswith('secret:'):
                logger.debug(f"Variable '{env_var_name}' not set - loading new secret value from layer '{layer_name}'")
            else:
                logger.debug(f"Variable '{env_var_name}' not set - loading new value '{processed_value}' from layer '{layer_name}'")
            loaded_vars[env_var_name] = (processed_value, 'env')
        except SecretUnavailableException as e:
            logger.error(f"Failed to load secret for {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to secret error")
            # Don't set any value - continue loading other variables
        except Exception as e:
            logger.error(f"Failed to process {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to processing error")
    
    return loaded_vars


def _load_and_merge_files(files: List[str]) -> Dict[str, Any]:
    """Load and merge multiple configuration files."""
    merged_environments = {}
    
    for file_path in files:
        # Resolve file path (handle {cwd} placeholder)
        resolved_path = file_path.replace("{cwd}", str(Path.cwd()))
        if not resolved_path.startswith("/"):
            # Relative path - resolve from config directory
            config_dir = Path(__file__).parent
            resolved_path = config_dir / resolved_path
        
        logger.debug(f"Loading config file: {resolved_path}")
        
        if not Path(resolved_path).exists():
            logger.debug(f"Config file not found: {resolved_path}")
            continue
        
        try:
            with open(resolved_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            
            if 'layers' in config:
                # Merge layers (later files override earlier ones)
                for layer_name, layer_config in config['layers'].items():
                    if layer_name in merged_environments:
                        # Merge app overrides into SDK defaults
                        if 'env' in layer_config:
                            if 'env' not in merged_environments[layer_name]:
                                merged_environments[layer_name]['env'] = {}
                            merged_environments[layer_name]['env'].update(layer_config.get('env', {}))
                        # Update other fields
                        merged_environments[layer_name].update({k: v for k, v in layer_config.items() if k != 'env'})
                    else:
                        # Add new layer
                        merged_environments[layer_name] = layer_config
                
                logger.debug(f"Loaded {len(config['layers'])} layers from {resolved_path}")
        
        except Exception as e:
            logger.error(f"Failed to load config file {resolved_path}: {e}")
            raise EnvironmentLoadError(f"Failed to load config file {resolved_path}: {e}")
    
    return {'environments': merged_environments}

def _process_inheritance(top_layer: str, base_layer: Optional[str], merged_config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Process environment inheritance with optional base layer.
    
    Returns:
        Tuple of (final_config, validator_names)
    """
    loaded_layers = set()  # Track loaded layers in this call
    validator_names = []  # Collect validators as we process layers
    
    def _load_layer(layer_name: str) -> Dict[str, Any]:
        # Check for circular inheritance
        _check_circular_inheritance(layer_name)
        
        if layer_name in loaded_layers:
            logger.warning(f"Circular dependency detected: {layer_name} already loaded")
            return {}  # Return empty config to break cycle
        
        loaded_layers.add(layer_name)
        logger.debug(f"Loading layer '{layer_name}'")
        
        if layer_name not in merged_config['environments']:
            raise EnvironmentNotFoundError(f"Environment '{layer_name}' not found")
        
        env_config = merged_config['environments'][layer_name]
        final_config = {'env': {}}
        
        # Collect validators from this layer
        layer_validators = _collect_validators_from_config(env_config, layer_name)
        validator_names.extend(layer_validators)
        
        # Load base layer first if specified
        if base_layer and base_layer != layer_name:
            logger.debug(f"Loading base environment layer: '{base_layer}'")
            base_config = _load_layer(base_layer)
            final_config['env'].update(base_config.get('env', {}))
            logger.debug(f"Applied {len(base_config.get('env', {}))} variables from base layer '{base_layer}'")
        
        # Process inheritance
        if 'inherits' in env_config:
            parent_names = env_config['inherits']
            if isinstance(parent_names, str):
                parent_names = [parent_names]
            
            for parent_name in parent_names:
                logger.debug(f"Layer '{layer_name}' inherits from '{parent_name}'")
                parent_config = _load_layer(parent_name)
                # Parent config has 'env' key, current layer has 'env' key
                parent_env = parent_config.get('env', {})
                final_config['env'].update(parent_env)
                logger.debug(f"Inherited {len(parent_env)} variables from '{parent_name}'")
        
        # Apply current layer's config (overrides inherited)
        current_env = env_config.get('env', {})
        final_config['env'].update(current_env)
        logger.debug(f"Applied {len(current_env)} variables from layer '{layer_name}'")
        
        # Remove from processing stack when done
        _LAYER_PROCESSING_STACK.pop()
        
        return final_config
    
    result_config = _load_layer(top_layer)
    return result_config, validator_names

def load_env(top_layer: str, base_layer: Optional[str] = None, files: Optional[List[str]] = None, force_reload: bool = False, fail_on_secret_error: bool = True, target_profile: Optional[str] = None) -> Dict[str, Tuple[str, str]]:
    """
    Load environment with atomic staging/clearing/applying phases.
    
    Args:
        top_layer: Primary environment layer to load
        base_layer: Optional base layer to load first
        files: List of config files to load (defaults to SDK + app configs)
        force_reload: Force reload even if same environment already loaded
        fail_on_secret_error: If True, raise SecretUnavailableException on any secret failure.
                             If False, skip failed secrets and continue with others.
        target_profile: Optional target profile for side-loading with TARGET_ prefix
        
    Returns:
        Dictionary of loaded variables with source info: {var_name: (value, source)}
    """
    
    if files is None:
        # Default file sources
        files = [
            "config.yaml",  # SDK environments
            "{cwd}/config/config.yaml"  # App environments
        ]
    
    # Clear processing state
    _clear_layer_processing_stack()
    
    # Check if this is the same load request as current
    if not force_reload and _is_same_load(top_layer, base_layer, files):
        logger.debug(f"Skipping reload - same environment already loaded: '{top_layer}'")
        return {}  # Return empty dict since nothing changed
    
    # PHASE 1: STAGING - Load all new values without touching os.environ
    staging_result = _stage_environment_variables(top_layer, base_layer, files, fail_on_secret_error)
    staged_vars = staging_result.staged_vars
    validator_names = staging_result.validator_names
    
    # PHASE 1.5: SIDE-LOADING - Load target profile with TARGET_ prefix if specified
    if target_profile:
        target_staging_result = _stage_environment_variables(target_profile, None, files, fail_on_secret_error)
        target_vars = target_staging_result.staged_vars
        target_validators = target_staging_result.validator_names
        
        # Add TARGET_ prefix to all target profile variables
        for var_name, (value, source) in target_vars.items():
            staged_vars[f"TARGET_{var_name}"] = (value, f"side-loaded from {source}")
        
        # Add target validators to our list
        validator_names.extend(target_validators)
    
    # PHASE 1.6: VALIDATION - Run collected validators
    _run_validators(staged_vars, validator_names, top_layer, target_profile)
    
    # PHASE 2: CLEARING - Remove old variables (only after staging succeeds)
    _clear_previous_variables()
    
    # PHASE 3: APPLYING - Apply all new variables atomically
    _apply_staged_variables(staged_vars)
    _commit_load_state(top_layer, base_layer, files, staged_vars)
    
    # Display environment variables table
    _display_environment_variables_table(staged_vars)
    
    return staged_vars


def _stage_environment_variables(top_layer: str, base_layer: Optional[str], files: List[str], fail_on_secret_error: bool) -> StagingResult:
    """
    PHASE 1: STAGING - Load all new values into a temporary dictionary without touching os.environ.
    
    Args:
        top_layer: Primary environment layer to load
        base_layer: Optional base layer to load first
        files: List of config files to load
        fail_on_secret_error: If True, raise SecretUnavailableException on any secret failure.
                             If False, skip failed secrets and continue with others.
    
    Returns:
        StagingResult with staged variables and validator names
        
    Raises:
        SecretUnavailableException: If fail_on_secret_error=True and any secret fails
    """
    logger.debug(f"STAGING: Loading environment '{top_layer}' from files: {files}")
    if base_layer:
        logger.debug(f"STAGING: With base environment layer: '{base_layer}'")
    
    # Load and merge configuration files
    merged_config = _load_and_merge_files(files)
    
    # Process inheritance and load new variables
    env_config, validator_names = _process_inheritance(top_layer, base_layer, merged_config)
    staged_vars = _load_environment_variables_staged(env_config, top_layer, fail_on_secret_error)
    
    logger.debug(f"STAGING: Successfully staged {len(staged_vars)} variables with {len(validator_names)} validators")
    return StagingResult(staged_vars=staged_vars, validator_names=validator_names)


def _clear_previous_variables() -> None:
    """
    PHASE 2: CLEARING - Remove old variables from os.environ.
    
    Only called after staging succeeds completely.
    """
    logger.debug("CLEARING: Removing variables from previous load")
    if _last_load and "loaded_vars" in _last_load:
        for var_name in _last_load["loaded_vars"]:
            if var_name in os.environ:
                logger.debug(f"CLEARING: Removing variable '{var_name}' from os.environ")
                del os.environ[var_name]
    logger.debug("CLEARING: Completed clearing previous variables")


def _apply_staged_variables(staged_vars: Dict[str, Tuple[str, str]]) -> None:
    """
    PHASE 3: APPLYING - Apply all staged variables to os.environ atomically.
    
    Args:
        staged_vars: Dictionary of staged variables: {var_name: (value, source)}
    """
    logger.debug(f"APPLYING: Setting {len(staged_vars)} variables in os.environ")
    for var_name, (value, source) in staged_vars.items():
        logger.debug(f"APPLYING: Setting '{var_name}' = '{value}' (source: {source})")
        os.environ[var_name] = value
    logger.debug("APPLYING: Completed applying staged variables")


def _commit_load_state(top_layer: str, base_layer: Optional[str], files: List[str], staged_vars: Dict[str, Tuple[str, str]]) -> None:
    """
    PHASE 3: COMMIT - Update global _last_load tracker with successful load.
    
    Args:
        top_layer: Primary environment layer that was loaded
        base_layer: Base layer that was loaded
        files: Files that were loaded
        staged_vars: Variables that were loaded: {var_name: (value, source)}
    """
    global _last_load
    _last_load = {
        "params": {
            "top_layer": top_layer,
            "base_layer": _resolve_base_layer(base_layer),
            "files": files
        },
        "loaded_vars": {var_name: value for var_name, (value, source) in staged_vars.items()}
    }
    logger.debug(f"COMMIT: Updated global state for environment '{top_layer}'")


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


# Validator system
_LAYER_PROCESSING_STACK = []  # Track layer processing to detect circular refs


def _resolve_validator_class(validator_name: str):
    """Resolve a validator class from a name or classpath.
    
    Args:
        validator_name: Either a simple class name (resolved in build.config.validators)
                       or a full classpath
        
    Returns:
        Validator class or None if resolution fails
    """
    try:
        if '.' in validator_name:
            # Full classpath provided
            module_path, class_name = validator_name.rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            return getattr(module, class_name)
        else:
            # Simple class name, resolve in build.config.validators
            # Try different module naming conventions
            possible_modules = [
                f"multi_eden.build.config.validators.{validator_name.lower()}",
                f"multi_eden.build.config.validators.{validator_name}",
                f"multi_eden.build.config.validators.testing"  # Default to testing module
            ]
            
            for module_path in possible_modules:
                try:
                    module = __import__(module_path, fromlist=[validator_name])
                    return getattr(module, validator_name)
                except (ImportError, AttributeError):
                    continue
            
            raise ImportError(f"Could not find validator '{validator_name}' in any expected module")
    except Exception as e:
        logger.error(f"Failed to resolve validator '{validator_name}': {e}")
        return None


def _collect_validators_from_config(config: Dict[str, Any], layer_name: str) -> List[str]:
    """Collect validator names from configuration.
    
    Args:
        config: Configuration dictionary
        layer_name: Name of the layer being processed
        
    Returns:
        List of validator names found in the configuration
    """
    validators = []
    
    # Check for validators in the layer config
    if 'validators' in config:
        validator_list = config['validators']
        if isinstance(validator_list, list):
            validators.extend(validator_list)
        elif isinstance(validator_list, str):
            validators.append(validator_list)
    
    return validators


def _check_circular_inheritance(layer_name: str) -> None:
    """Check for circular inheritance in layer processing.
    
    Args:
        layer_name: Name of the layer being processed
        
    Raises:
        ConfigException: If circular inheritance is detected
    """
    if layer_name in _LAYER_PROCESSING_STACK:
        cycle = ' -> '.join(_LAYER_PROCESSING_STACK + [layer_name])
        raise ConfigException(f"Circular inheritance detected in layer configuration: {cycle}")
    
    _LAYER_PROCESSING_STACK.append(layer_name)


def _clear_layer_processing_stack():
    """Clear the layer processing stack."""
    _LAYER_PROCESSING_STACK.clear()


def _run_validators(staged_vars: Dict[str, Tuple[str, str]], 
                   validator_names: List[str], top_layer: str, target_profile: Optional[str] = None) -> None:
    """Run all collected validators on the staged variables.
    
    Args:
        staged_vars: Dictionary of staged environment variables with source info
        validator_names: List of validator names to run
        top_layer: The primary environment layer being loaded
        target_profile: Optional target profile for side-loading
        
    Raises:
        ConfigException: If any validator fails validation
    """
    # Remove duplicates while preserving order
    unique_validators = list(dict.fromkeys(validator_names))
    
    for validator_name in unique_validators:
        try:
            validator_class = _resolve_validator_class(validator_name)
            if validator_class:
                validator = validator_class()
                if validator.should_validate(staged_vars, top_layer, target_profile):
                    validator.validate(staged_vars, top_layer, target_profile)
            else:
                logger.error(f"Could not resolve validator '{validator_name}' - skipping")
        except Exception as e:
            # Re-raise ConfigException as-is, wrap others
            from multi_eden.build.config.exceptions import ConfigException
            if isinstance(e, ConfigException):
                raise
            else:
                raise ConfigException(f"Validator {validator_name} failed: {e}")


def _display_environment_variables_table(staged_vars: Dict[str, Tuple[str, str]]) -> None:
    """Display environment variables table with status indicators.
    
    Args:
        staged_vars: Dictionary of staged environment variables with source info
    """
    import sys
    
    if not staged_vars:
        return
    
    print("\n" + "=" * 76, file=sys.stderr)
    print("🔧 ENVIRONMENT VARIABLES", file=sys.stderr)
    print("=" * 76, file=sys.stderr)
    
    # Prepare variables for display
    all_vars = []
    for name, (value, source) in staged_vars.items():
        # Limit value to 24 chars max to ensure space before SOURCE column
        if len(value) > 24:
            display_value = value[:21] + "..."
        else:
            display_value = value
        
        # Determine status based on value availability
        if value and value != "(not available)":
            status = "✅"
        else:
            status = "❌"
            display_value = "(not available)"
        
        all_vars.append((name, status, display_value, source))
    
    # Sort variables by name for consistent display
    all_vars.sort(key=lambda x: x[0])
    
    # Show column headers and rows
    print(f"{'VARIABLE':<25} {'VALUE':<25} {'SOURCE':<25}", file=sys.stderr)
    print("-" * 76, file=sys.stderr)
    
    for name, status, value, source in all_vars:
        print(f"{status} {name:<23} {value:<24} {source:<25}", file=sys.stderr)
    
    print("=" * 76, file=sys.stderr)

