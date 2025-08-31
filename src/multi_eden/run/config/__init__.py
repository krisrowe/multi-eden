"""
Unified configuration management.

Provides environment-specific configuration for auth and data settings.
Provides mode-specific configuration for testing and operational scenarios.
"""

from .settings import get_setting, is_setting_available, is_project_id_set, is_cloud_run, get_project_id, is_secrets_available, get_authorization, print_settings, print_stub_usage_table, print_runtime_config
from ..auth.config import Authorization, get_authorization_config, set_authorization, reset_authorization
from .testing import get_mode, is_mode_available
from .providers import is_db_in_memory, is_custom_auth_enabled, is_ai_mocked, get_provider_config

def get_test_mode():
    """Get test mode configuration - clear naming for test-related configuration."""
    return get_mode()

# Create module-level objects that behave like the old global instances
# but use the proper accessor functions under the hood
class _ConfigProxy:
    """Proxy object that forwards attribute access to the actual config."""
    def __init__(self, getter_func):
        self._getter = getter_func
    
    def __getattr__(self, name):
        config_obj = self._getter()
        return getattr(config_obj, name)
    
    def __repr__(self):
        try:
            config_obj = self._getter()
            return repr(config_obj)
        except Exception as e:
            return f"<ConfigProxy: {e}>"

__all__ = [
    'Authorization',
    'get_authorization_config', 
    'set_authorization',
    'reset_authorization',
    'get_setting',
    'is_project_id_set',
    'is_cloud_run',
    'get_project_id',
    'is_secrets_available',
    'get_authorization',
    'get_mode',
    'is_mode_available',
    'is_db_in_memory',
    'is_custom_auth_enabled',
    'is_ai_mocked',
    'get_provider_config',
    'print_stub_usage_table',
    'print_runtime_config'
]
