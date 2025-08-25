"""
This module provides shared authentication functionality for:
- Test suites (via util.py)
- Makefiles and scripts (via cli.py)
"""

# Constant used as fallback project ID when cloud services are not enabled
NON_CLOUD_ENV_NAME = "non-cloud"

from multi_eden.run.config.settings import get_app_id

# Constant used as fallback project ID when cloud services are not enabled
NON_CLOUD_ENV_NAME = "non-cloud"

# Base issuer URL for custom JWT authentication
CUSTOM_AUTH_BASE_ISSUER = f"https://auth.{get_app_id()}.app"
