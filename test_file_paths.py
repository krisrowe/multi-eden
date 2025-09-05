#!/usr/bin/env python3
"""Test script for file path resolution."""

import sys
import os
sys.path.insert(0, 'src')

from pathlib import Path

# Test file path resolution
print("Current working directory:", os.getcwd())
print("Script location:", __file__)

# Test the file path resolution logic
file_path = "environments.yaml"
resolved_path = file_path.replace("{cwd}", str(Path.cwd()))
if not resolved_path.startswith("/"):
    # Relative path - resolve from SDK root
    sdk_root = Path("src/multi_eden/build/config")
    resolved_path = sdk_root / resolved_path

print(f"Resolved path: {resolved_path}")
print(f"File exists: {Path(resolved_path).exists()}")

# List files in the config directory
config_dir = Path("src/multi_eden/build/config")
print(f"Files in {config_dir}:")
for f in config_dir.iterdir():
    print(f"  {f.name}")




