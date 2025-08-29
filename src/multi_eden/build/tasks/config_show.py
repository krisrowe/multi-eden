"""
Configuration Display Task

Shows merged configuration settings with diagnostic information.
"""

import sys
import yaml
import logging
from invoke import task
from pathlib import Path

logger = logging.getLogger(__name__)


@task
def show_config(ctx, env="unit-testing"):
    """
    Show merged configuration settings for an environment.
    
    Args:
        env: Config environment name (default: unit-testing)
    
    Outputs:
        stdout: YAML configuration (parseable)
        stderr: Diagnostic information
    """
    try:
        from ..config.settings import Settings
        
        # Load settings with diagnostic info
        print(f"🔍 Loading configuration for environment: {env}", file=sys.stderr)
        
        settings = Settings.from_config_env(env)
        
        # Convert to dictionary for YAML output
        config_dict = {
            'environment': env,
            'settings': settings.to_dict()
        }
        
        # Add diagnostic information to stderr
        print(f"✅ Configuration loaded successfully", file=sys.stderr)
        print(f"📍 Project ID: {settings.project_id or 'None (local)'}", file=sys.stderr)
        print(f"🔧 API Mode: {'In-memory' if settings.api_in_memory else 'Out-of-process'}", file=sys.stderr)
        print(f"🤖 AI: {'Stubbed' if settings.stub_ai else 'Real'}", file=sys.stderr)
        print(f"💾 DB: {'Stubbed' if settings.stub_db else 'Real'}", file=sys.stderr)
        
        if not settings.api_in_memory:
            api_url = settings.derive_api_url()
            print(f"🌐 API URL: {api_url}", file=sys.stderr)
        
        # Output parseable YAML to stdout
        yaml.dump(config_dict, sys.stdout, default_flow_style=False, sort_keys=True)
        
    except Exception as e:
        print(f"❌ Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)


@task  
def list_environments(ctx):
    """
    List all available configuration environments.
    
    Shows both SDK defaults and app-specific overrides.
    """
    try:
        from ..config.settings import Settings
        
        print("📋 Available Configuration Environments:", file=sys.stderr)
        print("", file=sys.stderr)
        
        # Load SDK defaults
        sdk_envs = Settings._load_sdk_environments()
        print(f"🔧 SDK Defaults ({len(sdk_envs)} environments):", file=sys.stderr)
        for env_name in sorted(sdk_envs.keys()):
            env_config = sdk_envs[env_name]
            project_id = env_config.get('project_id', 'None')
            api_mode = 'in-memory' if env_config.get('api_in_memory', True) else 'out-of-process'
            print(f"   • {env_name:15} (project: {project_id:12}, api: {api_mode})", file=sys.stderr)
        
        print("", file=sys.stderr)
        
        # Load app overrides
        app_envs = Settings._load_app_environments("config/env/settings.yaml")
        if app_envs:
            print(f"🏢 App Overrides ({len(app_envs)} environments):", file=sys.stderr)
            for env_name in sorted(app_envs.keys()):
                env_config = app_envs[env_name]
                project_id = env_config.get('project_id', 'None')
                api_mode = 'in-memory' if env_config.get('api_in_memory', True) else 'out-of-process'
                print(f"   • {env_name:15} (project: {project_id:12}, api: {api_mode})", file=sys.stderr)
        else:
            print("🏢 App Overrides: None found (config/env/settings.yaml missing)", file=sys.stderr)
        
        print("", file=sys.stderr)
        
        # Output environment names to stdout (parseable)
        all_envs = {**sdk_envs, **app_envs}
        for env_name in sorted(all_envs.keys()):
            print(env_name)
            
    except Exception as e:
        print(f"❌ Error listing environments: {e}", file=sys.stderr)
        sys.exit(1)
