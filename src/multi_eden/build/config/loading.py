"""
Environment loading system with inheritance, caching, and clean state management.
"""
import os
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from .exceptions import (
    EnvironmentLoadError,
    EnvironmentNotFoundError,
    SecretUnavailableException,
    ProjectIdNotFoundException,
    ProjectsFileNotFoundException
)
from .secrets import get_secret

logger = logging.getLogger(__name__)

# Global state tracking
_last_load = None  # Track last successful load: {"params": {...}, "loaded_vars": {...}}


def load_env(top_layer: str, base_layer: Optional[str] = None, files: Optional[List[str]] = None, force_reload: bool = False) -> Dict[str, Tuple[str, str]]:
    """
    Load environment with optional base layer and configurable file sources.
    
    Args:
        top_layer: Primary environment layer to load
        base_layer: Optional base layer to load first
        files: List of config files to load (defaults to SDK + app configs)
        force_reload: Force reload even if same environment already loaded
        
    Returns:
        Dictionary of loaded variables with source info: {var_name: (value, source)}
    """
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
    """
    Internal load environment function with required parameters.
    
    Args:
        top_layer: Primary environment layer to load
        base_layer: Optional base layer to load first
        files: List of config files to load
        
        Returns:
        Dictionary of loaded variables with source info
    """
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


def _load_and_merge_files(files: List[str]) -> Dict[str, Any]:
    """Load and merge multiple configuration files."""
    merged_environments = {}
    
    for file_path in files:
        # Resolve file path (handle {cwd} placeholder)
        resolved_path = file_path.replace("{cwd}", str(Path.cwd()))
        if not resolved_path.startswith("/"):
            # Relative path - resolve from SDK config directory
            sdk_root = Path(__file__).parent
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
            if isinstance(value, str) and value.startswith('secret:'):
                logger.debug(f"Variable '{env_var_name}' not set - loading new secret value from layer '{layer_name}'")
            else:
                logger.debug(f"Variable '{env_var_name}' not set - loading new value '{processed_value}' from layer '{layer_name}'")
            loaded_vars[env_var_name] = (processed_value, 'environment')
        except SecretUnavailableException as e:
            logger.error(f"Failed to load secret for {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to secret error")
            # Don't set any value - continue loading other variables
        except Exception as e:
            logger.error(f"Failed to process {env_var_name}: {e}")
            logger.debug(f"Variable '{env_var_name}' not set - skipping due to processing error")
    
    return loaded_vars


def _process_value(value: Any) -> str:
    """Process value with different source schemes (secret:, $.projects, etc.)."""
    if not isinstance(value, str):
        logger.debug(f"Converting non-string value to string: {value}")
        return str(value)
    
    if value.startswith('secret:'):
        secret_name = value[7:]  # Remove 'secret:' prefix
        logger.debug(f"Processing secret reference: {value} -> {secret_name}")
        return get_secret(secret_name)  # Uses cached version
    elif value.startswith('$.projects.'):
        # Handle project IDs from .projects file
        env_name = value.replace('$.projects.', '')
        project_id = _get_project_id_from_projects_file(env_name)
        if project_id:
            logger.debug(f"Processing project ID reference: {value} -> {project_id}")
            return project_id
        else:
            raise ProjectIdNotFoundException(
                f"Project ID not found for environment '{env_name}' in .projects file"
            )
    else:
        logger.debug(f"Using literal value: {value}")
        return value


def _get_project_id_from_projects_file(env_name: str) -> str:
    """Get project ID from .projects file for specific environment."""
    projects_file = Path(".projects")
    
    if not projects_file.exists():
        raise ProjectsFileNotFoundException(
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