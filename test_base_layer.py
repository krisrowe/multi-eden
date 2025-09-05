#!/usr/bin/env python3
"""Test script for base layer functionality."""

import sys
import os
sys.path.insert(0, 'src')

from multi_eden.build.config.loading import load_env

print("Testing base layer functionality...")
try:
    # Test loading with a base layer
    result = load_env('unit', base_layer='local')
    print(f"Success! Loaded {len(result)} variables with base layer 'local'")
    for var_name, (value, source) in result.items():
        print(f"  {var_name} = {value} (from {source})")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
