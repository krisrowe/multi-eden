"""
App configuration loading utilities.
"""

from pathlib import Path
from typing import Dict, Any
import yaml


def load_app_config(repo_root: Path) -> Dict[str, Any]:
    """
    Load application configuration from config/app.yaml.
    
    Args:
        repo_root: Repository root path
        
    Returns:
        Dictionary containing app configuration
        
    Raises:
        FileNotFoundError: If config/app.yaml doesn't exist
        ValueError: If config/app.yaml is invalid
    """
    app_yaml = repo_root / "config" / "app.yaml"
    
    if not app_yaml.exists():
        raise FileNotFoundError(f"Missing config/app.yaml at {app_yaml}")
    
    try:
        with open(app_yaml) as f:
            config = yaml.safe_load(f)
            
        if not config:
            raise ValueError("config/app.yaml is empty")
            
        return config
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config/app.yaml: {e}")


def get_api_config(repo_root: Path) -> Dict[str, Any]:
    """
    Get API configuration from app.yaml.
    
    Args:
        repo_root: Repository root path
        
    Returns:
        Dictionary containing API configuration
        
    Raises:
        ValueError: If API configuration is missing or invalid
    """
    app_config = load_app_config(repo_root)
    api_config = app_config.get('api')
    
    if not api_config:
        raise ValueError("Missing 'api' configuration in config/app.yaml")
    
    # Validate required fields
    if not api_config.get('module'):
        raise ValueError("Missing 'api.module' in config/app.yaml")
    
    return api_config


def get_api_module_info(repo_root: Path) -> Dict[str, str]:
    """
    Extract API module information from configuration.
    
    Args:
        repo_root: Repository root path
        
    Returns:
        Dictionary with module info:
        - module: Full module specification (e.g., "core.api:app")
        - module_name: Module directory name (e.g., "core")
        - app_name: Application variable name (e.g., "app")
        - venv_path: Virtual environment path (always "venv")
        - working_dir: Working directory (always ".")
        - serve_args: Server command arguments (always ["serve"])
    """
    api_config = get_api_config(repo_root)
    
    module_spec = api_config['module']
    if ':' not in module_spec:
        raise ValueError(f"Invalid module specification '{module_spec}' - must be 'module.path:app'")
    
    module_path, app_name = module_spec.split(':', 1)
    module_name = module_path.split('.')[0]
    
    return {
        'module': module_spec,
        'module_name': module_name,
        'module_path': module_path,
        'app_name': app_name,
        'venv_path': 'venv',  # Standard location
        'working_dir': '.',   # Always repo root
        'serve_args': ['serve']  # Standard command
    }
