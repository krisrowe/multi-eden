#!/usr/bin/env python3
"""
Example usage of the new dynamic environment loading system.

This demonstrates how the new loading.yaml configuration works
and how task-level environment settings can be defined.
"""

import sys
from pathlib import Path

# Add the SDK to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from multi_eden.build.config.loading import load_env

def example_callback():
    """Example post-load callback that injects additional variables."""
    return [
        ('CALLBACK_VAR', 'callback-value', 'callback'),
        ('DYNAMIC_TIMESTAMP', str(int(__import__('time').time())), 'callback')
    ]

def main():
    """Demonstrate the new dynamic loading system."""
    print("🚀 Dynamic Environment Loading Example")
    print("=" * 50)
    
    # Example 1: Load with task-specific settings
    print("\n📋 Example 1: Loading with task 'prompt'")
    print("-" * 30)
    
    loaded_vars = load_env(
        env_name="local",  # Base environment
        task_name="prompt",  # Task-specific settings
        post_load_callback=example_callback,
        quiet=False
    )
    
    print(f"\n✅ Loaded {len(loaded_vars)} environment variables")
    
    # Example 2: Load with test mode
    print("\n📋 Example 2: Loading with test mode 'ai'")
    print("-" * 30)
    
    loaded_vars = load_env(
        test_mode="ai",
        quiet=False
    )
    
    print(f"\n✅ Loaded {len(loaded_vars)} environment variables")
    
    # Example 3: Show how layers are processed
    print("\n📋 Example 3: Layer Processing Order")
    print("-" * 30)
    print("Based on loading.yaml configuration:")
    print("1. Environment Variables (highest priority)")
    print("2. Post-load Callback")
    print("3. Test Config (tests.yaml)")
    print("4. Task Config (tasks.yaml)")
    print("5. App Environment Config (config/environments.yaml)")
    print("6. SDK Environment Config (environments.yaml)")
    print("7. Base Config (lowest priority)")

if __name__ == "__main__":
    main()
