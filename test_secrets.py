#!/usr/bin/env python3
"""Test script for secrets module."""

import sys
import os
sys.path.insert(0, 'src')

try:
    from multi_eden.build.config.secrets import get_secret
    print("Secrets module imported successfully")
except Exception as e:
    print(f"Error importing secrets module: {e}")
    import traceback
    traceback.print_exc()

try:
    from multi_eden.build.config.exceptions import SecretUnavailableException
    print("SecretUnavailableException imported successfully")
except Exception as e:
    print(f"Error importing SecretUnavailableException: {e}")
    import traceback
    traceback.print_exc()
