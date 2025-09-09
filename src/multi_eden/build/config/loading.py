"""
New environment loading system with inheritance, caching, and clean state management.
"""
import os
import sys
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from .models import LoadParams, StagedVariable, StagingResult
import yaml
from pydantic import BaseModel

from .exceptions import (
    ConfigException,
    ProjectIdRequiredException,
    NoProjectIdForGoogleSecretsException,
    NoKeyCachedForLocalSecretsException,
    LocalSecretNotFoundException,
    GoogleSecretNotFoundException,
    EnvironmentCorruptionError,
    # Legacy exceptions for backward compatibility
    EnvironmentLoadError,
    EnvironmentNotFoundError,
    SecretUnavailableException,
    ProjectIdNotFoundException,
    ProjectsFileNotFoundException
)
from .secrets import get_secret

logger = logging.getLogger(__name__)


def _calculate_integrity_hash(staged_vars: Dict[str, StagedVariable]) -> str:
    """
    Calculate integrity hash of all os.environ values that were written in Phase 3 (applying).
    
    Args:
        staged_vars: Dictionary of staged variables that were applied to os.environ
        
    Returns:
        MD5 hash string of the environment variable values
    """
    # Create a sorted list of key=value pairs for consistent hashing
    env_pairs = []
    for var_name, staged_var in staged_vars.items():
        env_pairs.append(f"{var_name}={staged_var.value}")
    
    # Sort to ensure consistent hash regardless of order
    env_pairs.sort()
    
    # Create hash of the environment variable values
    env_string = "\n".join(env_pairs)
    return hashlib.md5(env_string.encode()).hexdigest()


def _verify_integrity_hash(cached_integrity_hash: str, staged_vars: Dict[str, StagedVariable]) -> bool:
    """
    Verify that current os.environ values match the cached integrity hash.
    
    Args:
        cached_integrity_hash: The integrity hash stored in cache
        staged_vars: Dictionary of staged variables that should be in os.environ
        
    Returns:
        True if integrity hash matches, False otherwise
    """
    current_hash = _calculate_integrity_hash(staged_vars)
    return current_hash == cached_integrity_hash


class LayerValue(BaseModel):
    """Pydantic model for a layer-value pair in the inheritance chain."""
    layer: str
    value: str

class LoadedVariable(BaseModel):
    """Pydantic model for a loaded environment variable with metadata."""
    name: str
    value: str  # Current value (highest priority)
    source: str  # The layer name where the current value came from
    overrides: List[LayerValue] = []  # Ordered list of layer-value pairs (highest to lowest priority)
    
    def found(self, value: str, layer: str) -> None:
        """
        Record a new value from a layer, pushing previous value to overrides.
        
        Args:
            value: The new value found
            layer: The layer where this value was found
        """
        # If we already have a value, push it to the front of overrides
        if self.value is not None and self.source is not None:
            self.overrides.insert(0, LayerValue(layer=self.source, value=self.value))
        
        # Update current value and source
        self.value = value
        self.source = layer
    
    @property
    def is_override(self) -> bool:
        """True if this variable overrode a value from a lower layer."""
        return len(self.overrides) > 0


# Track last successful load: {"params": {...}, "loaded_vars": {...}, "integrity_hash": "..."}
_last_load = None


def _is_same_load(params: LoadParams) -> bool:
    """Check if this is the same load request as the current one using hash comparison and integrity verification."""
    if _last_load is None:
        return False
    
    # Compare using hash keys for robust comparison
    current_key = params.get_cache_key()
    last_key = _last_load.get("cache_key")
    cache_key_matches = current_key == last_key
    
    if cache_key_matches:
        # If cache key matches, verify integrity hash BEFORE returning True
        cached_integrity_hash = _last_load.get("integrity_hash")
        if cached_integrity_hash:
            # We need to stage the variables to verify integrity
            # This is a bit of a chicken-and-egg problem, so we'll do a lightweight check
            # by comparing the expected variables from the cache manifest
            cached_loaded_vars = _last_load.get("loaded_vars", {})
            
            # Create staged variables from current os.environ for integrity check
            staged_vars_for_check = {}
            for var_name, var_value in cached_loaded_vars.items():
                # Use current os.environ value, not cached value
                current_value = os.environ.get(var_name, var_value)
                staged_vars_for_check[var_name] = StagedVariable(
                    name=var_name,
                    value=current_value,
                    source="os.environ",
                    is_override=False,
                    layer_name="os.environ"
                )
            
            integrity_matches = _verify_integrity_hash(cached_integrity_hash, staged_vars_for_check)
            
            
            if not integrity_matches:
                logger.warning(f"Cache key matches but integrity hash mismatch detected. Cache key: {last_key}, Cached integrity: {cached_integrity_hash}")
                # Find which variables are corrupted
                corrupted_vars = []
                for var_name, staged_var in staged_vars_for_check.items():
                    if var_name in os.environ:
                        current_value = os.environ[var_name]
                        if current_value != staged_var.value:
                            corrupted_vars.append(var_name)
                
                raise EnvironmentCorruptionError(
                    f"Environment variables have been corrupted since last load. Cache key: {last_key}",
                    corrupted_vars=corrupted_vars
                )
        
        return True
    
    return False




def _clear_our_vars():
    """Clear only the variables that WE previously loaded."""
    if _last_load is None:
        return
    
    for var_name in _last_load["loaded_vars"]:
        if var_name in os.environ:
            del os.environ[var_name]


def _load_staged_vars(staged_vars: Dict[str, StagedVariable]) -> Dict[str, str]:
    """Load staged variables into os.environ after clearing our previous vars."""
    # Clear our previously loaded variables
    _clear_our_vars()
    
    # Load staged variables into os.environ
    for var_name, staged_var in staged_vars.items():
        os.environ[var_name] = staged_var.value
    
    # Return the loaded variables for tracking
    return {var_name: staged_var.value for var_name, staged_var in staged_vars.items()}



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

def _process_inheritance(top_layer: str, merged_config: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Process environment inheritance.
    
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
                # Track original layer for inherited variables
                for var_name, var_data in parent_env.items():
                    if isinstance(var_data, dict) and 'original_layer' in var_data:
                        # Already has layer tracking, preserve it
                        final_config['env'][var_name] = var_data
                    else:
                        # New variable, add layer tracking
                        final_config['env'][var_name] = {
                            'value': var_data,
                            'original_layer': parent_name
                        }
                logger.debug(f"Inherited {len(parent_env)} variables from '{parent_name}'")
        
        # Apply current layer's config (overrides inherited)
        current_env = env_config.get('env', {})
        for var_name, var_value in current_env.items():
            final_config['env'][var_name] = {
                'value': var_value,
                'original_layer': layer_name
            }
        logger.debug(f"Applied {len(current_env)} variables from layer '{layer_name}'")
        
        # Remove from processing stack when done
        _LAYER_PROCESSING_STACK.pop()
        
        return final_config
    
    result_config = _load_layer(top_layer)
    return result_config, validator_names

def load_env(params: LoadParams) -> List[LoadedVariable]:
    """
    Load environment with atomic staging/clearing/applying phases.
    
    Args:
        params: Load parameters including top_layer, files, base_layer, etc.
        
    Returns:
        Dictionary of staged variables that were loaded: {var_name: StagedVariable}
    """
    
    if params.files is None:
        # Default file sources
        params.files = [
            "config.yaml",  # SDK environments
            "{cwd}/config/config.yaml"  # App environments
        ]
    
    # Clear processing state
    _clear_layer_processing_stack()
    
    # Check if this is the same load request as current
    if not params.force_reload and _is_same_load(params):
        cache_key = params.get_cache_key()
        cached_key = _last_load.get('cache_key') if _last_load else 'None'
        cached_integrity = _last_load.get('integrity_hash') if _last_load else 'None'
        
        print(f"DEBUG: Cache hit! Current cache: {cached_key}, Request cache: {cache_key}", file=sys.stderr)
        print(f"DEBUG: Cached integrity hash: {cached_integrity}", file=sys.stderr)
        
        _display_load_params_table(params, cache_key, "SKIPPING LOAD - SAME ENVIRONMENT ALREADY LOADED")
        logger.debug(f"Skipping reload - same environment already loaded: '{params.top_layer}' with cache_key={cache_key}, integrity_hash={cached_integrity}")
        return []  # Return empty list since nothing changed
    
    # Display load parameters before processing
    cache_key = params.get_cache_key()
    _display_load_params_table(params, cache_key, "LOADING ENVIRONMENT")
    
    # PHASE 1: CLEARING - Remove old variables first to ensure clean state
    _clear_previous_variables()
    
    # PHASE 2: STAGING - Load all new values without touching os.environ
    loaded_vars_dict = _stage_environment_variables(params)
    
    # PHASE 3: APPLYING - Apply all new variables atomically to os.environ
    _apply_loaded_variables(loaded_vars_dict)
    
    # PHASE 4: CACHING - Update cache only after os.environ update succeeds
    _commit_load_state(params, loaded_vars_dict)
    
    # Display environment variables table
    _display_environment_variables_table(loaded_vars_dict, params.top_layer)
    
    # Convert dictionary to list
    loaded_vars = list(loaded_vars_dict.values())
    
    return loaded_vars


def _stage_environment_variables(params: LoadParams) -> Dict[str, LoadedVariable]:
    """
    PHASE 1: STAGING - Load all new values into a temporary dictionary without touching os.environ.
    
    This function builds a prioritized layer list by walking inheritance chains,
    then processes layers from lowest to highest priority, tracking the full inheritance chain.
    
    Args:
        params: Load parameters including top_layer, base_layer, etc.
    
    Returns:
        Dictionary of loaded variables: {var_name: LoadedVariable}
    """
    logger.debug(f"STAGING: Loading environment '{params.top_layer}' from files: {params.files}")
    
    # Load and merge configuration files
    merged_config = _load_and_merge_files(params.files)
    
    # Build prioritized layer list
    layer_names = _build_prioritized_layer_list(params.top_layer, merged_config, params.base_layer)
    logger.debug(f"STAGING: Processing layers in order: {layer_names}")
    
    # Process layers from lowest to highest priority (reverse order)
    loaded_vars = {}  # Dictionary of LoadedVariable objects
    validators = []
    
    for layer_name in reversed(layer_names):
        logger.debug(f"STAGING: Processing layer '{layer_name}'")
        layer_vars, layer_validators = _load_layer_variables(layer_name, merged_config)
        
        # Process each variable from this layer
        for var_name, layer_var in layer_vars.items():
            if var_name in loaded_vars:
                # Variable already exists, use found() method to track inheritance
                loaded_vars[var_name].found(layer_var.value, layer_name)
                logger.debug(f"STAGING: Override {var_name} = {layer_var.value} (from {layer_name})")
            else:
                # New variable, use the LoadedVariable from the layer
                loaded_vars[var_name] = layer_var
                logger.debug(f"STAGING: New {var_name} = {layer_var.value} (from {layer_name})")
        
        validators.extend(layer_validators)
    
    # PHASE 1.5: VALIDATION - Run collected validators
    # Use LoadedVariable objects directly for validation
    _run_validators_loaded_vars(loaded_vars, validators, params.top_layer, params.base_layer)
    
    logger.debug(f"STAGING: Successfully staged {len(loaded_vars)} variables")
    return loaded_vars


def _build_prioritized_layer_list(top_layer: str, merged_config: Dict[str, Any], base_layer: Optional[str] = None) -> List[str]:
    """
    Build a prioritized list of layer names by walking inheritance chains.
    
    Args:
        top_layer: The top layer to start from
        merged_config: Merged configuration from all files
        base_layer: Optional base layer to add at the bottom
        
    Returns:
        List of layer names in priority order (lowest to highest)
    """
    layer_names = []
    visited = set()
    
    def _add_layer_recursive(layer_name: str):
        """Recursively add layer and its inheritance chain, avoiding duplicates."""
        if layer_name in visited:
            logger.warning(f"Circular dependency detected: {layer_name} already in chain")
            return
        
        visited.add(layer_name)
        
        if layer_name not in merged_config['environments']:
            logger.warning(f"Layer '{layer_name}' not found in configuration")
            return
        
        env_config = merged_config['environments'][layer_name]
        
        # Process inheritance first (add parents before this layer)
        if 'inherits' in env_config:
            parent_names = env_config['inherits']
            if isinstance(parent_names, str):
                parent_names = [parent_names]
            
            for parent_name in parent_names:
                _add_layer_recursive(parent_name)
        
        # Add this layer
        layer_names.append(layer_name)
        logger.debug(f"Added layer '{layer_name}' to priority list")
    
    # Add base layer first (lowest priority)
    if base_layer:
        _add_layer_recursive(base_layer)
    
    # Add top layer and its inheritance chain
    _add_layer_recursive(top_layer)
    
    return layer_names


def _load_layer_variables(layer_name: str, merged_config: Dict[str, Any]) -> Tuple[Dict[str, LoadedVariable], List[Any]]:
    """
    Load variables from a single layer.
    
    Args:
        layer_name: Name of the layer to load
        merged_config: Merged configuration from all files
        
    Returns:
        Tuple of (loaded_vars, validators)
    """
    if layer_name not in merged_config['environments']:
        logger.warning(f"Layer '{layer_name}' not found in configuration")
        return {}, []
    
    env_config = merged_config['environments'][layer_name]
    loaded_vars = {}
    validators = []
    
    # Collect validators from this layer
    layer_validators = _collect_validators_from_config(env_config, layer_name)
    validators.extend(layer_validators)
    
    # Load environment variables from this layer
    for key, value in env_config.get('env', {}).items():
        env_var_name = key.upper()
        
        # Process new value
        try:
            processed_value = _process_value(value, env_var_name, layer_name)
            loaded_vars[env_var_name] = LoadedVariable(
                name=env_var_name,
                value=processed_value,
                source=layer_name,
                overrides=[]
            )
        except Exception as e:
            logger.error(f"Failed to process {env_var_name}: {e}")
            raise
    
    return loaded_vars, validators


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


def _apply_loaded_variables(loaded_vars: Dict[str, LoadedVariable]) -> None:
    """
    PHASE 3: APPLYING - Apply all loaded variables to os.environ atomically.
    
    Args:
        loaded_vars: Dictionary of loaded variables with metadata
    """
    logger.debug(f"APPLYING: Setting {len(loaded_vars)} variables in os.environ")
    for var_name, loaded_var in loaded_vars.items():
        logger.debug(f"APPLYING: Setting '{var_name}' = '{loaded_var.value}' (source: {loaded_var.source})")
        os.environ[var_name] = loaded_var.value
    logger.debug("APPLYING: Completed applying loaded variables")


def _commit_load_state(params: LoadParams, loaded_vars: Dict[str, LoadedVariable]) -> None:
    """
    PHASE 4: CACHING - Update global _last_load tracker with successful load and integrity hash.
    
    Args:
        params: Load parameters used for this load
        loaded_vars: Variables that were loaded with metadata
    """
    import sys
    global _last_load
    
    # Calculate integrity hash of all os.environ values that were written in Phase 3
    # Convert LoadedVariable to StagedVariable for integrity hash calculation
    staged_vars = {}
    for var_name, loaded_var in loaded_vars.items():
        staged_vars[var_name] = StagedVariable(
            name=loaded_var.name,
            value=loaded_var.value,
            source=f"config.yaml:{loaded_var.source}",
            is_override=loaded_var.is_override,
            layer_name=loaded_var.source
        )
    
    integrity_hash = _calculate_integrity_hash(staged_vars)
    
    _last_load = {
        "cache_key": params.get_cache_key(),
        "params": params.model_dump(),
        "loaded_vars": {var_name: loaded_var.value for var_name, loaded_var in loaded_vars.items()},
        "integrity_hash": integrity_hash
    }
    
    print(f"DEBUG: _last_load set to top_layer={params.top_layer}, cache_key={params.get_cache_key()}", file=sys.stderr)
    logger.debug(f"CACHING: Updated global state for environment '{params.top_layer}' with cache_key={params.get_cache_key()}, integrity_hash={integrity_hash}")




# Validator system
_LAYER_PROCESSING_STACK = []  # Track layer processing to detect circular refs


def _resolve_validator_class(validator_name: str):
    """Resolve a validator instance from a name or classpath.
    
    Args:
        validator_name: Either a simple class name (resolved in build.config.validators)
                       or a full classpath
        
    Returns:
        Validator instance or None if resolution fails
    """
    try:
        validator_class = None
        if '.' in validator_name:
            # Full classpath provided
            module_path, class_name = validator_name.rsplit('.', 1)
            module = __import__(module_path, fromlist=[class_name])
            validator_class = getattr(module, class_name)
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
                    validator_class = getattr(module, validator_name)
                    break
                except (ImportError, AttributeError):
                    continue
            
            if validator_class is None:
                raise ImportError(f"Could not find validator '{validator_name}' in any expected module")
        
        # Create and return an instance
        return validator_class()
        
    except Exception as e:
        logger.error(f"Failed to resolve validator '{validator_name}': {e}")
        return None


def _collect_validators_from_config(config: Dict[str, Any], layer_name: str) -> List[Any]:
    """Collect validator instances from configuration.
    
    Args:
        config: Configuration dictionary
        layer_name: Name of the layer being processed
        
    Returns:
        List of validator instances found in the configuration
    """
    validators = []
    validator_names = []
    
    # Check for validators in the layer config
    if 'validators' in config:
        validator_list = config['validators']
        if isinstance(validator_list, list):
            validator_names.extend(validator_list)
        elif isinstance(validator_list, str):
            validator_names.append(validator_list)
    
    # Convert validator names to instances, avoiding duplicates
    seen_validators = set()
    for validator_name in validator_names:
        if validator_name in seen_validators:
            logger.debug(f"Skipping duplicate validator '{validator_name}' in layer '{layer_name}'")
            continue
            
        try:
            validator_instance = _resolve_validator_class(validator_name)
            if validator_instance:
                validators.append(validator_instance)
                seen_validators.add(validator_name)
                logger.debug(f"Successfully loaded validator '{validator_name}' for layer '{layer_name}'")
            else:
                logger.error(f"Could not resolve validator class '{validator_name}' for layer '{layer_name}' - skipping")
        except Exception as e:
            logger.error(f"Failed to load validator '{validator_name}' for layer '{layer_name}': {e} - skipping")
    
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


def clear_env(known_vars=None):
    """Clear all environment variables that were set by load_env and clear the cache.
    
    This method removes all environment variables that were loaded by previous
    load_env calls and clears the global cache. Useful for testing to ensure
    clean state between tests.
    
    Args:
        known_vars: Optional set of known environment variable names that load_env can set.
                   If None, uses the default set of production environment variables.
    """
    global _last_load
    
    # Default known variables that load_env can set in production
    if known_vars is None:
        known_vars = {
            'APP_ID', 'CUSTOM_AUTH_ENABLED', 'STUB_AI', 'STUB_DB', 'LOCAL', 'PORT',
            'GEMINI_API_KEY', 'JWT_SECRET_KEY', 'ALLOWED_USER_EMAILS', 'TEST_API_MODE',
            'TEST_OMIT_INTEGRATION', 'PROJECT_ID', 'GCP_REGION', 'GCP_ZONE'
        }
    
    # Get currently loaded variables from cache
    loaded_vars = set()
    if _last_load and 'loaded_vars' in _last_load:
        loaded_vars = set(_last_load['loaded_vars'])
        
        # Check that all loaded variables are in our known list
        unknown_vars = loaded_vars - known_vars
        if unknown_vars:
            raise RuntimeError(
                f"clear_env found unknown variables in cache that are not in known_vars: {unknown_vars}. "
                f"Please add these variables to the known_vars set when calling clear_env() method."
            )
    
    # Check for rogue variables: variables in os.environ that are in our known list
    # but NOT in the cache manifest - this means they were set outside our tracking
    current_env_vars = set(os.environ.keys())
    known_vars_in_env = current_env_vars & known_vars
    rogue_vars = known_vars_in_env - loaded_vars
    
    if rogue_vars:
        raise RuntimeError(
            f"clear_env found rogue variables in os.environ that are in known_vars but not in cache manifest: {rogue_vars}. "
            f"This indicates variables are being set outside of load_env tracking or cache manifest is incomplete. "
            f"Loaded vars from cache: {loaded_vars}, Rogue vars: {rogue_vars}"
        )
    
    # Clear all variables that were loaded
    for var_name in loaded_vars:
        if var_name in os.environ:
            del os.environ[var_name]
    
    # Clear the cache after clearing environment
    _last_load = None


def _run_validators(staged_vars: Dict[str, StagedVariable], 
                   validators: List[Any], top_layer: str, target_profile: Optional[str] = None) -> None:
    """Run all collected validators on the staged variables.
    
    Args:
        staged_vars: Dictionary of staged environment variables with source info
        validators: List of validator instances to run
        top_layer: The primary environment layer being loaded
        target_profile: Optional target profile for base layer
        
    Raises:
        ConfigException: If any validator fails validation
    """
    # Remove duplicates while preserving order
    unique_validators = list(dict.fromkeys(validators))
    
    for validator in unique_validators:
        try:
            if validator.should_validate(staged_vars, top_layer, target_profile):
                validator.validate(staged_vars, top_layer, target_profile)
        except Exception as e:
            # Re-raise ConfigException as-is, wrap others
            from multi_eden.build.config.exceptions import ConfigException
            if isinstance(e, ConfigException):
                raise
            else:
                raise ConfigException(f"Validator {validator.__class__.__name__} failed: {e}")


def _run_validators_loaded_vars(loaded_vars: Dict[str, LoadedVariable], 
                               validators: List[Any], top_layer: str, target_profile: Optional[str] = None) -> None:
    """Run all collected validators on the loaded variables.
    
    Args:
        loaded_vars: Dictionary of loaded environment variables with inheritance tracking
        validators: List of validator instances to run
        top_layer: The primary environment layer being loaded
        target_profile: Optional target profile for base layer
        
    Raises:
        ConfigException: If any validator fails validation
    """
    # Remove duplicates while preserving order
    unique_validators = list(dict.fromkeys(validators))
    
    for validator in unique_validators:
        try:
            # Convert LoadedVariable objects to StagedVariable for validator compatibility
            # TODO: Update validators to work with LoadedVariable directly
            staged_vars = {}
            for var_name, loaded_var in loaded_vars.items():
                staged_vars[var_name] = StagedVariable(
                    name=loaded_var.name,
                    value=loaded_var.value,
                    source=f"config.yaml:{loaded_var.source}",
                    is_override=loaded_var.is_override,
                    layer_name=loaded_var.source
                )
            
            if validator.should_validate(staged_vars, top_layer, target_profile):
                validator.validate(staged_vars, top_layer, target_profile)
        except Exception as e:
            # Re-raise ConfigException as-is, wrap others
            from multi_eden.build.config.exceptions import ConfigException
            if isinstance(e, ConfigException):
                raise
            else:
                raise ConfigException(f"Validator {validator.__class__.__name__} failed: {e}")


def _format_source_display(staged_var: StagedVariable) -> str:
    """Format the source display for a staged variable."""
    if staged_var.source.startswith("config.yaml:"):
        layer_name = staged_var.source.replace("config.yaml:", "")
        if staged_var.is_override:
            return f"{layer_name}* (top layer)"
        else:
            return f"{layer_name} (top layer)"
    else:
        return staged_var.source


def _display_load_params_table(params: LoadParams, cache_key: str, header: str) -> None:
    """Display LoadParams and cache key in a table format with cache and integrity information.
    
    Args:
        params: LoadParams object to display
        cache_key: Cache key string to display
        header: Header message for the table
    """
    import sys
    
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"🔧 {header}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    # Display LoadParams details
    print(f"{'PARAMETER':<20} {'VALUE':<50}", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    print(f"{'top_layer':<20} {params.top_layer:<50}", file=sys.stderr)
    print(f"{'base_layer':<20} {str(params.base_layer):<50}", file=sys.stderr)
    print(f"{'files':<20} {str(params.files):<50}", file=sys.stderr)
    print(f"{'force_reload':<20} {str(params.force_reload):<50}", file=sys.stderr)
    print(f"{'cache_key':<20} {cache_key:<50}", file=sys.stderr)
    
    # Display cache information if available
    if _last_load is not None:
        cached_key = _last_load.get("cache_key", "None")
        cached_integrity = _last_load.get("integrity_hash", "None")
        cache_key_matches = cached_key == cache_key
        
        print(f"{'cached_key':<20} {cached_key:<50}", file=sys.stderr)
        print(f"{'cached_integrity':<20} {cached_integrity:<50}", file=sys.stderr)
        print(f"{'cache_match':<20} {str(cache_key_matches):<50}", file=sys.stderr)
        
        if not cache_key_matches:
            print(f"{'new_params':<20} {str(params.model_dump()):<50}", file=sys.stderr)
    else:
        print(f"{'cached_key':<20} {'None':<50}", file=sys.stderr)
        print(f"{'cached_integrity':<20} {'None':<50}", file=sys.stderr)
        print(f"{'cache_match':<20} {'False':<50}", file=sys.stderr)
    
    print("=" * 70, file=sys.stderr)


def _display_environment_variables_table(loaded_vars: Dict[str, LoadedVariable], layer_name: str) -> None:
    """Display environment variables table with status indicators.
    
    Args:
        loaded_vars: Dictionary of loaded environment variables with source info
        layer_name: Name of the environment layer that was loaded
    """
    import sys
    
    if not loaded_vars:
        return
    
    print("\n" + "=" * 70, file=sys.stderr)
    print(f"🔧 ENVIRONMENT VARIABLES ({layer_name})", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    # Prepare variables for display
    all_vars = []
    for name, loaded_var in loaded_vars.items():
        # Truncate variable name if too long (18 chars max to fit column + space)
        if len(name) > 18:
            display_name = name[:15] + "..."
        else:
            display_name = name
        
        # Truncate value if too long (18 chars max to fit column + space)
        if len(loaded_var.value) > 18:
            display_value = loaded_var.value[:15] + "..."
        else:
            display_value = loaded_var.value
        
        # Determine status based on value availability
        if loaded_var.value and loaded_var.value != "(not available)":
            status = "✅"
        else:
            status = "❌"
            display_value = "(not available)"
        
        # Process source display - create a temporary StagedVariable for display formatting
        temp_staged_var = StagedVariable(
            name=loaded_var.name,
            value=loaded_var.value,
            source=f"config.yaml:{loaded_var.source}",
            is_override=loaded_var.is_override,
            layer_name=loaded_var.source
        )
        display_source = _format_source_display(temp_staged_var)
        all_vars.append((name, display_name, status, display_value, display_source))
    
    # Sort variables by original name for consistent display
    all_vars.sort(key=lambda x: x[0])
    
    # Show column headers and rows
    print(f"{'VARIABLE':<20} {'VALUE':<20} {'SOURCE':<30}", file=sys.stderr)
    print("-" * 70, file=sys.stderr)
    
    for original_name, display_name, status, value, source in all_vars:
        print(f"{status} {display_name:<18} {value:<19} {source:<29}", file=sys.stderr)
    
    print("=" * 70, file=sys.stderr)

