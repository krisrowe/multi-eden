#!/usr/bin/env python3
"""Test script for environment loading."""

from src.multi_eden.build.config.loading import load_env

print("Testing basic load_env...")
try:
    result = load_env('unit')
    print(f"Success! Loaded {len(result)} variables")
    for var_name, (value, source) in result.items():
        print(f"  {var_name} = {value} (from {source})")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
