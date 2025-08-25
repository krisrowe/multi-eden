"""
Configuration environment setup tasks for multi-env-sdk.

This module provides tasks for managing configuration environments,
including setting up default environments and retrieving configuration.
"""

import yaml
import sys
from pathlib import Path
from invoke import task
from typing import Optional, Dict, Any


def get_sdk_root() -> Path:
    """Get the SDK root directory for finding internal files."""
    # For SDK internal files, use the library location
    return Path(__file__).parent.parent.parent.parent


def get_task_defaults() -> Dict[str, Any]:
    """Load task defaults from the centralized config system."""
    try:
        from multi_eden.build.config import get_tasks_config
        config = get_tasks_config()
        return config.get('tasks', {})
    except Exception as e:
        print(f"⚠️  Warning: Could not load tasks config: {e}")
        return {}


def get_task_default_env(task_name: str) -> Optional[str]:
    """Get the default environment for a specific task."""
    defaults = get_task_defaults()
    task_config = defaults.get(task_name, {})
    return task_config.get('env')


def get_task_description(task_name: str) -> Optional[str]:
    """Get the description for a specific task."""
    defaults = get_task_defaults()
    task_config = defaults.get(task_name, {})
    return task_config.get('description')


@task(help={
    'env': 'Environment name to set up (e.g., local-docker, local-server)',
    'file': 'Path to configuration file to use',
    'content': 'Configuration content as string (alternative to file)',
    'validate': 'Validate configuration after setting (default: True)'
})
def set_env_config(ctx, env: str, file: Optional[str] = None, content: Optional[str] = None, validate: bool = True):
    """
    Set up a configuration environment.
    
    Examples:
        invoke set-env-config local-docker --file=config/local-docker.yaml
        invoke set-env-config local-server --content="api_url: http://localhost:8000"
        echo "api_url: http://localhost:8000" | invoke set-env-config local-docker --content=-
    """
    try:
        print(f"🔧 Setting up configuration environment: {env}")
        
        # Determine configuration source
        if file and content:
            print("❌ Error: Cannot specify both --file and --content")
            return False
        
        if not file and not content:
            print("❌ Error: Must specify either --file or --content")
            return False
        
        # Read configuration
        if file:
            if file == '-':
                # Read from stdin
                print("📖 Reading configuration from stdin...")
                config_content = sys.stdin.read()
            else:
                # Read from file
                config_path = Path(file)
                if not config_path.exists():
                    print(f"❌ Error: Configuration file not found: {file}")
                    return False
                print(f"📖 Reading configuration from: {file}")
                with open(config_path, 'r') as f:
                    config_content = f.read()
        else:
            config_content = content
        
        # Parse YAML
        try:
            config = yaml.safe_load(config_content)
        except yaml.YAMLError as e:
            print(f"❌ Error: Invalid YAML content: {e}")
            return False
        
        # Validate configuration structure
        if validate:
            if not isinstance(config, dict):
                print("❌ Error: Configuration must be a YAML object")
                return False
            
            # Add basic validation here as needed
            print("✅ Configuration structure validated")
        
        # Create environment directory
        env_dir = Path("config/settings") / env
        env_dir.mkdir(parents=True, exist_ok=True)
        
        # Write configuration
        config_file = env_dir / "config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        print(f"✅ Configuration environment '{env}' set up successfully")
        print(f"📁 Configuration written to: {config_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to set up configuration environment: {e}")
        return False


@task(help={
    'env': 'Environment name to retrieve (e.g., local-docker, local-server)',
    'format': 'Output format: yaml, json, or raw (default: yaml)'
})
def get_env_config(ctx, env: str, format: str = 'yaml'):
    """
    Retrieve configuration for a specific environment.
    
    Examples:
        invoke get-env-config local-docker
        invoke get-env-config local-server --format=json
        invoke get-env-config local-docker | jq '.api_url'
    """
    try:
        print(f"🔍 Retrieving configuration for environment: {env}")
        
        # Check if environment exists
        env_dir = Path("config/settings") / env
        config_file = env_dir / "config.yaml"
        
        if not config_file.exists():
            print(f"❌ Error: Configuration environment '{env}' not found")
            print(f"💡 Use 'invoke set-env-config {env}' to create it")
            return False
        
        # Read configuration
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Output in requested format
        if format == 'json':
            import json
            output = json.dumps(config, indent=2)
        elif format == 'raw':
            output = str(config)
        else:  # yaml
            output = yaml.dump(config, default_flow_style=False, indent=2)
        
        print(output)
        return True
        
    except Exception as e:
        print(f"❌ Failed to retrieve configuration: {e}")
        return False


@task
def list_env_configs(ctx):
    """List all available configuration environments."""
    try:
        print("🔍 Available configuration environments:")
        
        settings_dir = Path("config/settings")
        if not settings_dir.exists():
            print("ℹ️  No configuration environments found")
            return True
        
        for env_dir in sorted(settings_dir.iterdir()):
            if env_dir.is_dir():
                config_file = env_dir / "config.yaml"
                if config_file.exists():
                    print(f"  ✅ {env_dir.name}")
                else:
                    print(f"  ⚠️  {env_dir.name} (incomplete)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to list configuration environments: {e}")
        return False
