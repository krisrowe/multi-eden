"""
Multi-Environment SDK Environment Configuration Management

Handles creation and management of environment configurations
using the new environments.yaml and Secret Manager architecture.
"""

import yaml
import secrets
from pathlib import Path
from invoke import task
from typing import Optional


class CreateConfigEnvError(Exception):
    """Base exception for environment creation errors."""
    pass


class EnvironmentExistsError(CreateConfigEnvError):
    """Raised when trying to create an environment that already exists."""
    pass


class InvalidEnvironmentNameError(CreateConfigEnvError):
    """Raised when environment name is invalid."""
    pass


@task
def config_env_create(ctx, env_name: str, project_id: Optional[str] = None) -> None:
    """
    Create a new environment configuration using environments.yaml and Secret Manager.
    
    This task:
    - Adds the environment to config/environments.yaml
    - Sets up secrets in Google Secret Manager (required for cloud environments)
    - Validates the environment configuration
    
    Args:
        env_name: Name of the environment to create (e.g., 'staging', 'qa')
        project_id: GCP project ID for this environment (required for cloud environments)
        
    Raises:
        InvalidEnvironmentNameError: When environment name is invalid
        EnvironmentExistsError: When environment already exists
        CreateConfigEnvError: When creation fails
    
    Examples:
        invoke config-env-create --env-name=staging --project-id=my-staging-project
        invoke config-env-create --env-name=local-test  # Virtual environment (no secrets)
    """
    
    # Validate environment name
    if not env_name or not env_name.strip():
        raise InvalidEnvironmentNameError("Environment name cannot be empty")
    
    env_name = env_name.strip().lower()
    
    # Check for invalid patterns
    if env_name.startswith('--'):
        raise InvalidEnvironmentNameError("Environment name cannot start with '--' (conflicts with command-line flags)")
    
    # Check for invalid characters
    if not env_name.replace('-', '').replace('_', '').isalnum():
        raise InvalidEnvironmentNameError("Environment name can only contain letters, numbers, hyphens, and underscores")
    
    # Get repository root and environments file
    repo_root = Path.cwd()
    config_dir = repo_root / "config"
    environments_file = config_dir / "environments.yaml"
    
    if not config_dir.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Created config directory: {config_dir}")
    
    # Load existing environments or create new file
    environments = {}
    if environments_file.exists():
        with open(environments_file, 'r') as f:
            data = yaml.safe_load(f) or {}
            environments = data.get('environments', {})
    
    # Check if environment already exists
    if env_name in environments:
        raise EnvironmentExistsError(f"Environment '{env_name}' already exists in {environments_file}")
    
    print(f"🔧 Creating environment '{env_name}'...")
    
    try:
        # Add environment to environments.yaml
        if project_id:
            environments[env_name] = {'project_id': project_id}
            print(f"   ☁️  Added cloud environment with project: {project_id}")
        else:
            environments[env_name] = {}
            print(f"   🖥️  Added virtual/local environment")
        
        # Write updated environments.yaml
        config_data = {
            '# AI Food Log - Private Environment Overrides': None,
            '# This file contains app-specific settings like project IDs': None,
            '# It should NOT be committed to version control': None,
            'environments': environments
        }
        
        with open(environments_file, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        print(f"   ✅ Updated {environments_file}")
        
        # Set up secrets in Secret Manager for cloud environments
        if project_id:
            print(f"   🔐 Setting up secrets in Secret Manager for project {project_id}...")
            _setup_secret_manager_secrets(project_id, env_name)
        else:
            print(f"   ℹ️  Virtual environment - no secrets needed")
        
        print(f"   🎯 Environment '{env_name}' created successfully!")
        
        if project_id:
            print(f"   💡 This is a cloud environment. Secrets should be managed in Secret Manager.")
            print(f"   💡 Use: gcloud config set project {project_id}")
        else:
            print(f"   💡 This is a virtual environment. It will use default/stubbed services.")
        
        print(f"   💡 Test with: ./invoke config-env-list")
        
    except Exception as e:
        raise CreateConfigEnvError(f"Failed to create environment '{env_name}': {e}")


def _setup_secret_manager_secrets(project_id: str, env_name: str):
    """Set up secrets in Google Secret Manager for the environment."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}"
        
        # Define secrets to create
        secrets_to_create = [
            ('jwt-secret-key', secrets.token_urlsafe(32)),
            ('gemini-api-key', 'REPLACE_WITH_ACTUAL_GEMINI_API_KEY')
        ]
        
        for secret_name, secret_value in secrets_to_create:
            full_secret_name = f"{secret_name}-{env_name}"
            
            try:
                # Create the secret
                secret = client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": full_secret_name,
                        "secret": {"replication": {"automatic": {}}}
                    }
                )
                
                # Add the secret version
                client.add_secret_version(
                    request={
                        "parent": secret.name,
                        "payload": {"data": secret_value.encode("UTF-8")}
                    }
                )
                
                print(f"     ✅ Created secret: {full_secret_name}")
                
            except Exception as e:
                if "already exists" in str(e):
                    print(f"     ⚠️  Secret {full_secret_name} already exists")
                else:
                    print(f"     ❌ Failed to create secret {full_secret_name}: {e}")
                    
    except Exception as e:
        print(f"   ⚠️  Could not set up Secret Manager secrets: {e}")
        print(f"   💡 You may need to: gcloud auth application-default login")


@task
def config_env_update_secrets(ctx, env_name: str, project_id: Optional[str] = None) -> None:
    """
    Update secrets in Secret Manager for an existing environment.
    
    This task updates or creates secrets in Google Secret Manager for an environment
    that already exists in environments.yaml.
    
    Args:
        env_name: Name of the existing environment
        project_id: GCP project ID (if not provided, will try to get from environments.yaml)
        
    Raises:
        CreateConfigEnvError: When environment doesn't exist or update fails
    
    Examples:
        invoke config-env-update-secrets --env-name=staging
        invoke config-env-update-secrets --env-name=staging --project-id=my-project
    """
    
    # Validate environment name
    if not env_name or not env_name.strip():
        raise InvalidEnvironmentNameError("Environment name cannot be empty")
    
    env_name = env_name.strip().lower()
    
    # Check for invalid patterns
    if env_name.startswith('--'):
        raise InvalidEnvironmentNameError("Environment name cannot start with '--' (conflicts with command-line flags)")
    
    # Get repository root and environments file
    repo_root = Path.cwd()
    config_dir = repo_root / "config"
    environments_file = config_dir / "environments.yaml"
    
    if not environments_file.exists():
        raise CreateConfigEnvError(f"No environments.yaml found at {environments_file}")
    
    # Load existing environments
    with open(environments_file, 'r') as f:
        data = yaml.safe_load(f) or {}
        environments = data.get('environments', {})
    
    # Check if environment exists
    if env_name not in environments:
        available_envs = list(environments.keys())
        raise CreateConfigEnvError(
            f"Environment '{env_name}' not found. Available environments: {available_envs}"
        )
    
    # Get project_id from environments.yaml if not provided
    if not project_id:
        env_config = environments.get(env_name, {})
        project_id = env_config.get('project_id')
    
    if not project_id:
        raise CreateConfigEnvError(
            f"No project_id found for environment '{env_name}'. "
            f"Either provide --project-id or add project_id to environments.yaml"
        )
    
    print(f"🔐 Updating secrets for environment '{env_name}' in project {project_id}...")
    
    try:
        _setup_secret_manager_secrets(project_id, env_name)
        print(f"✅ Successfully updated secrets for environment '{env_name}'")
        print(f"💡 Secrets are now available in Secret Manager for project {project_id}")
        
    except Exception as e:
        raise CreateConfigEnvError(f"Failed to update secrets for environment '{env_name}': {e}")


@task
def config_env_list(ctx) -> None:
    """
    List all available environments from environments.yaml and unified settings.
    Shows real cloud environments (with project_id) first, then virtual environments.
    """
    import yaml
    
    repo_root = Path.cwd()
    environments_file = repo_root / "config" / "environments.yaml"
    
    # Get all available environment names
    try:
        all_environments = {
            'unit-testing': 'Virtual testing environment with all services stubbed',
            'ai-testing': 'Virtual testing environment with real AI, stubbed DB',
            'db-testing': 'Virtual testing environment with real DB, stubbed AI', 
            'local': 'Local development environment with in-memory API',
            'local-ai': 'Local development environment with real AI services',
            'local-docker': 'Local Docker environment on port 8001',
            'local-docker-ai': 'Local Docker environment with real AI services'
        }
        
        # Read project-specific environments from environments.yaml
        project_environments = {}
        if environments_file.exists():
            with open(environments_file, 'r') as f:
                env_config = yaml.safe_load(f)
                if env_config and 'environments' in env_config:
                    project_environments = env_config['environments']
        
        # Categorize environments
        real_environments = []  # Have project_id
        virtual_environments = []  # No project_id
        
        # Check project-specific environments first
        for env_name, env_config in project_environments.items():
            if isinstance(env_config, dict) and env_config.get('project_id'):
                real_environments.append((env_name, f"Cloud environment (project: {env_config['project_id']})"))
            else:
                virtual_environments.append((env_name, "Project-specific virtual environment"))
        
        # Add standard virtual environments
        for env_name, description in all_environments.items():
            if env_name not in project_environments:
                virtual_environments.append((env_name, description))
        
        # Display results
        if not real_environments and not virtual_environments:
            print("📁 No environments found")
            return
        
        print("🔧 Available Configuration Environments:")
        print()
        
        if real_environments:
            print("☁️  Real Cloud Environments:")
            for env_name, description in sorted(real_environments):
                print(f"   • {env_name:<20} - {description}")
            print()
        
        if virtual_environments:
            print("🖥️  Virtual/Local Environments:")
            for env_name, description in sorted(virtual_environments):
                print(f"   • {env_name:<20} - {description}")
        
        print()
        print("💡 Usage: ./invoke <task> --config-env=<environment>")
        
    except Exception as e:
        print(f"❌ Error reading environment configuration: {e}")
        print("💡 Try running: ./invoke config-env-create --env=<name> to create an environment")
