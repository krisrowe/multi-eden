"""
Secrets manifest metadata for build tasks.

Provides access to secret definitions without hardcoding names or env vars.
"""

import os
import yaml
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class SecretDefinition:
    """Definition of a secret and how to load it."""
    name: str
    local_default: Optional[str] = None  # Local testing value with {app-id} and {env} placeholder support
    required_when: Optional[Dict[str, Any]] = None
    
    @property
    def env_var(self) -> str:
        """Derive environment variable name from secret name.
        
        Converts 'secret-name' to 'SECRET_NAME'
        """
        return self.name.replace('-', '_').upper()


def load_secrets_manifest() -> List[SecretDefinition]:
    """Load secrets configuration from YAML manifest."""
    # Load from build package manifest
    manifest_path = Path(__file__).parent.parent / 'config' / 'secrets.yaml'
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Required secrets manifest not found: {manifest_path}")
    
    try:
        with open(manifest_path, 'r') as f:
            config = yaml.safe_load(f)
            
        if not config or 'secrets' not in config:
            raise ValueError(f"Invalid secrets manifest: missing 'secrets' key in {manifest_path}")
            
        secrets = []
        for secret_config in config['secrets']:
            secrets.append(SecretDefinition(
                name=secret_config['name'],
                local_default=secret_config.get('local_default'),
                required_when=secret_config.get('required_when')
            ))
            
        return secrets
        
    except Exception as e:
        raise RuntimeError(f"Failed to load secrets manifest from {manifest_path}: {e}")


class SecretsManifest:
    """Provides access to secrets manifest metadata for build tasks."""
    
    def __init__(self):
        self._manifest = None
    
    def _get_manifest(self) -> List[SecretDefinition]:
        """Get cached manifest."""
        if self._manifest is None:
            self._manifest = load_secrets_manifest()
        return self._manifest
    
    def get_env_var_names(self) -> List[str]:
        """Get all secret environment variable names."""
        return [secret.env_var for secret in self._get_manifest()]
    
    def copy_set_env_vars_to_dict(self, target_dict: dict) -> None:
        """Copy all currently set secret environment variables to target dict."""
        for secret in self._get_manifest():
            value = os.environ.get(secret.env_var)
            if value:
                target_dict[secret.env_var] = value


# Global instance for build tasks
secrets_manifest = SecretsManifest()
