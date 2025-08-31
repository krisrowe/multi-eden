"""
Test mode configuration loading.

Provides get_test_mode_config() which reads tests.yaml and returns configuration
for a specific test mode. No caching - reads fresh every time to ensure correctness.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def get_test_mode_config(mode: str) -> Dict[str, Any]:
    """
    Get test mode configuration for the specified mode.
    
    Reads tests.yaml fresh every time - no caching to ensure correctness.
    Should only be called once per process execution.
    
    Args:
        mode: Test mode name (e.g., 'unit', 'ai', 'db', 'api')
        
    Returns:
        Dictionary containing test mode configuration
        
    Raises:
        FileNotFoundError: If tests.yaml doesn't exist
        KeyError: If the specified mode doesn't exist
        yaml.YAMLError: If tests.yaml is malformed
    """
    # Find tests.yaml - check current working directory first, then SDK default
    tests_yaml_paths = [
        Path.cwd() / "config" / "tests.yaml",
        Path(__file__).parent / "tests.yaml"
    ]
    
    tests_yaml_path = None
    for path in tests_yaml_paths:
        if path.exists():
            tests_yaml_path = path
            break
    
    if not tests_yaml_path:
        raise FileNotFoundError(
            f"tests.yaml not found in any of these locations: {[str(p) for p in tests_yaml_paths]}"
        )
    
    # Read and parse tests.yaml
    try:
        with open(tests_yaml_path, 'r') as f:
            tests_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Failed to parse {tests_yaml_path}: {e}")
    
    # Validate structure
    if not isinstance(tests_config, dict) or 'modes' not in tests_config:
        raise ValueError(f"Invalid tests.yaml structure - missing 'modes' section")
    
    modes = tests_config['modes']
    if not isinstance(modes, dict):
        raise ValueError(f"Invalid tests.yaml structure - 'modes' must be a dictionary")
    
    # Get the specific mode
    if mode not in modes:
        available_modes = list(modes.keys())
        raise KeyError(f"Test mode '{mode}' not found. Available modes: {available_modes}")
    
    mode_config = modes[mode]
    if not isinstance(mode_config, dict):
        raise ValueError(f"Invalid configuration for mode '{mode}' - must be a dictionary")
    
    # Return a copy to prevent accidental mutation
    return dict(mode_config)


def get_available_test_modes() -> list[str]:
    """
    Get list of available test modes from tests.yaml.
    
    Returns:
        List of available test mode names
    """
    try:
        # Use a dummy mode to trigger the file reading logic
        get_test_mode_config("__dummy__")
    except KeyError:
        # Expected - we just want to trigger file reading
        pass
    except Exception:
        # If we can't read the file, return empty list
        return []
    
    # Re-read the file to get available modes
    tests_yaml_paths = [
        Path.cwd() / "config" / "tests.yaml",
        Path(__file__).parent / "tests.yaml"
    ]
    
    for path in tests_yaml_paths:
        if path.exists():
            try:
                with open(path, 'r') as f:
                    tests_config = yaml.safe_load(f)
                    return list(tests_config.get('modes', {}).keys())
            except Exception:
                continue
    
    return []
