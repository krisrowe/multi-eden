#!/usr/bin/env python3
"""
Lightweight CLI interface for Authentication utilities.

Configuration Environment Strategy: Lazy Loading from Command Line
==============================================================

This CLI utility uses lazy loading for configuration environment detection.
Configuration is automatically loaded when first needed via --config-env arguments
in sys.argv. The ensure_env_config_loaded() call triggers lazy loading and
verifies the configuration is valid.

Usage: python -m auth.cli generate-static-test-user-token --config-env ENV

No need to call set_config_env() - the SDK handles it automatically.
"""

import sys
import json
import logging

from multi_eden.run.config.settings import ensure_env_config_loaded
from .testing import get_static_test_user_token

# Set up logger
logger = logging.getLogger(__name__)

def main():
    """
    Main CLI entry point. Provides a single command to get a token for the
    default static test user. The authentication method (custom JWT or Firebase)
    is determined by the environment configuration.

    Usage: python -m auth.cli generate-static-test-user-token --config-env ENV
    """
    try:
        # Ensure configuration is loaded and verified
        ensure_env_config_loaded()
        
        # Get the token (configuration will be loaded lazily when needed)
        token_data = get_static_test_user_token()
        
        # Output the token data
        print(json.dumps(token_data, indent=2))

    except Exception as e:
        logger.error(f"Failed to generate token: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
