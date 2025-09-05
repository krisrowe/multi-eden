#!/usr/bin/env python3
"""Test script for local environment loading with inheritance."""

import sys
import os
sys.path.insert(0, 'src')

from multi_eden.build.config.loading import load_env

print("Testing local environment loading with inheritance...")
try:
    result = load_env('local')
    print(f"Success! Loaded {len(result)} variables")
    for var_name, (value, source) in result.items():
        print(f"  {var_name} = {value} (from {source})")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
