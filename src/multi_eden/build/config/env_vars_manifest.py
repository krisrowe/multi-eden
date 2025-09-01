"""
Environment variables manifest loader for build tasks.

Provides access to environment variable definitions without hardcoding names in code.
"""

import yaml
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class EnvVarDefinition:
    """Definition of an environment variable and how to load it."""
    name: str
    source: str = "setting"  # "setting" or "derived"
    setting_key: Optional[str] = None  # Auto-derived from name if not specified
    method: Optional[str] = None  # For derived variables
    condition: Optional[Dict[str, Any]] = None  # For conditional variables
    default: Optional[Any] = None  # Default value if no source provides one
    optional: bool = False


def load_env_vars_manifest() -> List[EnvVarDefinition]:
    """Load environment variables manifest from YAML."""
    manifest_path = Path(__file__).parent / 'environment_variables.yaml'
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Required environment variables manifest not found: {manifest_path}")
    
    try:
        with open(manifest_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'environment_variables' not in config:
            raise ValueError(f"Invalid environment variables manifest: missing 'environment_variables' key in {manifest_path}")
            
        env_vars = []
        for env_config in config['environment_variables']:
            env_vars.append(EnvVarDefinition(
                name=env_config['name'],
                source=env_config.get('source', 'setting'),
                setting_key=env_config.get('setting_key'),
                method=env_config.get('method'),
                condition=env_config.get('condition'),
                default=env_config.get('default'),
                optional=env_config.get('optional', False)
            ))
            
        return env_vars
        
    except Exception as e:
        raise RuntimeError(f"Failed to load environment variables manifest from {manifest_path}: {e}")


class EnvVarsManifest:
    """Provides access to environment variables manifest metadata for build tasks."""
    
    def __init__(self):
        self._manifest = None
    
    def _get_manifest(self) -> List[EnvVarDefinition]:
        """Get cached manifest."""
        if self._manifest is None:
            self._manifest = load_env_vars_manifest()
        return self._manifest
    
    def get_env_var_names(self) -> List[str]:
        """Get all environment variable names."""
        return [env_var.name for env_var in self._get_manifest()]


# Global instance for build tasks
env_vars_manifest = EnvVarsManifest()
