"""
This module provides shared authentication functionality for:
- Test suites (via util.py)
- Makefiles and scripts (via cli.py)
"""

# Constant used as fallback project ID when cloud services are not enabled
NON_CLOUD_ENV_NAME = "non-cloud"

from multi_eden.run.config.settings import get_setting

# Constant used as fallback project ID when cloud services are not enabled
NON_CLOUD_ENV_NAME = "non-cloud"

# Base issuer URL for custom JWT authentication (lazy-loaded)
def get_custom_auth_base_issuer() -> str:
    """Get the base issuer URL for custom JWT authentication."""
    return f"https://auth.{get_setting('app-id')}.app"

# Legacy constant for backward compatibility
CUSTOM_AUTH_BASE_ISSUER = None  # Use get_custom_auth_base_issuer() instead
