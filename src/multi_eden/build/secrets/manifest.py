"""
Secrets manifest metadata for build tasks.

Provides access to secret definitions without hardcoding names or env vars.
"""

import os
from typing import List
from ...run.config.secrets import load_secrets_manifest, SecretDefinition


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
