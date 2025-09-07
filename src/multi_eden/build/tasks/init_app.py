"""
Multi-Eden App Initialization Task

Creates a new Multi-Eden application with proper project structure,
configuration, and Secret Manager integration.
"""

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from invoke import task

# Secret manager functions available in secrets_setup module if needed


@dataclass
class InitPlan:
    """Plan for app initialization showing what will be done."""
    app_id: str
    dev_project_id: str
    registry_project_id: str
    jwt_secret: str
    gemini_api_key: str
    repo_root: Path
    actions_needed: List[str]
    actions_completed: List[str]
    existing_secrets: dict


@dataclass
class ActionResult:
    """Result of an initialization action."""
    name: str
    status: str  # DONE, SKIPPED, PENDING, FAILED
    details: str


def _validate_repo_structure(repo_root: Path) -> List[str]:
    """Validate that we're in a proper app repo structure."""
    issues = []
    
    # Check we're not in the SDK repo
    if (repo_root / "src" / "multi_eden").exists():
        issues.append("❌ Cannot run in Multi-Eden SDK repository")
    
    # Check for git repo
    if not (repo_root / ".git").exists():
        issues.append("❌ Not in a git repository root")
    
    # Check for app.yaml with API configuration
    app_yaml = repo_root / "config" / "app.yaml"
    if not app_yaml.exists():
        issues.append("❌ Missing config/app.yaml - not a Multi-Eden app")
    else:
        # Validate API configuration exists
        import yaml
        try:
            with open(app_yaml) as f:
                app_config = yaml.safe_load(f)
                if not app_config.get('api'):
                    issues.append("❌ Missing 'api' configuration in config/app.yaml")
        except Exception as e:
            issues.append(f"❌ Invalid config/app.yaml: {e}")
    
    return issues


def _load_api_config(repo_root: Path) -> Dict[str, Any]:
    """Load API configuration from app.yaml or return defaults."""
    app_yaml = repo_root / "config" / "app.yaml"
    if app_yaml.exists():
        import yaml
        try:
            with open(app_yaml) as f:
                app_config = yaml.safe_load(f)
                api_config = app_config.get('api', {})
                if api_config:
                    return api_config
        except Exception:
            pass
    
    # No fallback - force proper configuration
    raise ValueError("Missing 'api' configuration in config/app.yaml")


def _check_existing_config(config_dir: Path) -> Optional[Dict[str, Any]]:
    """Check for existing configuration and return project info."""
    app_yaml = config_dir / "app.yaml"
    projects_file = config_dir.parent / ".projects"
    
    existing_config = {}
    
    if app_yaml.exists():
        import yaml
        with open(app_yaml) as f:
            app_config = yaml.safe_load(f)
            existing_config['app_id'] = app_config.get('id')
            existing_config['registry'] = app_config.get('registry')
    
    if projects_file.exists():
        with open(projects_file) as f:
            content = f.read()
            for line in content.split('\n'):
                if line.startswith('dev='):
                    existing_config['dev_project_id'] = line.split('=', 1)[1].strip()
                    break
    
    return existing_config if existing_config else None


def _generate_secret_value(secret_type: str, app_id: str) -> str:
    """Generate a secure secret value."""
    import secrets
    import string
    
    if secret_type == 'jwt':
        # Generate a 32-byte base64 secret for JWT
        return secrets.token_urlsafe(32)
    elif secret_type == 'gemini':
        # Generate an obviously fake API key for testing
        return f"FAKE-GEMINI-API-KEY-FOR-TESTING-{app_id.upper()}-{secrets.token_hex(8).upper()}"
    else:
        return secrets.token_urlsafe(32)


def _create_app_yaml(config_dir: Path, app_id: str, registry_project_id: str, api_module: str = None) -> None:
    """Create config/app.yaml with registry and API configuration."""
    # Default API module based on app structure
    if not api_module:
        api_module = f"{app_id.replace('-', '_')}.api:app"
    
    app_yaml_content = f"""# Multi-Eden Application Configuration
id: {app_id}
registry:
  project_id: {registry_project_id}
  tag: {app_id}

# API Server Configuration
api:
  # ASGI application specification (module.path:variable)
  module: "{api_module}"
"""
    
    with open(config_dir / "app.yaml", "w") as f:
        f.write(app_yaml_content)


def _create_pytest_ini(repo_root: Path) -> None:
    """Create pytest.ini with plugin registration."""
    pytest_content = '''[pytest]
plugins = multi_eden
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
'''
    with open(repo_root / "pytest.ini", "w") as f:
        f.write(pytest_content)


def _create_projects_file(repo_root: Path, dev_project_id: str) -> None:
    """Create .projects file with project IDs."""
    projects_content = f"""# Multi-Eden Project IDs
# This file contains project IDs for different environments
# Used by environments.yaml with $.projects syntax

dev={dev_project_id}
prod={dev_project_id}  # TODO: Update with production project ID
"""
    with open(repo_root / ".projects", "w") as f:
        f.write(projects_content)




def _handle_gitignore_projects(repo_root: Path) -> ActionResult:
    """Handle .gitignore entry for .projects file."""
    gitignore_path = repo_root / ".gitignore"
    
    if not gitignore_path.exists():
        return ActionResult(
            name=".gitignore: .projects",
            status="FAILED",
            details="No .gitignore file found"
        )
    
    with open(gitignore_path, "r") as f:
        content = f.read()
    
    # Check if it's already ignored (not commented)
    if ".projects" in content and not content.count("#.projects"):
        return ActionResult(
            name=".gitignore: .projects",
            status="SKIPPED",
            details="Already in .gitignore"
        )
    
    # Check if it's commented out (developer wants it tracked)
    if "#.projects" in content or "# .projects" in content:
        return ActionResult(
            name=".gitignore: .projects",
            status="SKIPPED",
            details="Explicitly commented out (will be tracked)"
        )
    
    # Add it to .gitignore
    with open(gitignore_path, "a") as f:
        f.write("\n# Multi-Eden project IDs (contains sensitive project information)\n.projects\n")
    
    return ActionResult(
        name=".gitignore: .projects",
        status="DONE",
        details="Added to .gitignore"
    )


def _copy_provider_tests(repo_root: Path, sdk_root: Path) -> None:
    """Copy provider tests from SDK to app."""
    src_providers = sdk_root / "tests" / "providers"
    dst_providers = repo_root / "tests" / "providers"
    
    if src_providers.exists():
        if dst_providers.exists():
            shutil.rmtree(dst_providers)
        shutil.copytree(src_providers, dst_providers)


def _create_base_api(api_dir: Path, api_module_name: str) -> None:
    """Create api.py with base health/system endpoints."""
    api_content = f'''"""
FastAPI application with Multi-Eden base endpoints.
"""

from fastapi import FastAPI
from multi_eden.run.api.base import BaseAPI


class API(BaseAPI):
    """Application API with Multi-Eden base functionality."""
    
    def __init__(self):
        super().__init__()
        self.setup_routes()
    
    def setup_routes(self):
        """Set up application-specific routes."""
        # Add your custom routes here
        pass


# Create the FastAPI app instance
app = API().app
'''
    
    with open(api_dir / "api.py", "w") as f:
        f.write(api_content)


def _create_api_test(tests_dir: Path, api_module_name: str) -> None:
    """Create tests/unit/test_api.py for system endpoint testing."""
    test_content = f'''"""
Test API system endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from {api_module_name}.api import app


class TestSystemEndpoints:
    """Test system health and info endpoints."""
    
    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_system_info_endpoint(self):
        """Test system info endpoint."""
        response = self.client.get("/api/system")
        assert response.status_code == 200
        data = response.json()
        assert "SYS_AP" in data
        assert "SYS_DP" in data
'''
    
    with open(tests_dir / "test_api.py", "w") as f:
        f.write(test_content)


def _check_existing_secrets(project_id: str) -> dict:
    """Check if secrets already exist in Google Secret Manager and retrieve their values."""
    try:
        from google.cloud import secretmanager
        
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}"
        
        existing_secrets = {}
        secret_names = ["jwt-secret-key", "gemini-api-key"]
        
        for secret_name in secret_names:
            try:
                secret_path = f"projects/{project_id}/secrets/{secret_name}"
                secret = client.get_secret(request={"name": secret_path})
                
                # Check if secret has versions
                versions = client.list_secret_versions(request={"parent": secret_path})
                version_list = list(versions)
                
                if version_list:
                    # Get the latest version
                    latest_version = max(version_list, key=lambda v: v.create_time)
                    
                    # Try to get the actual secret value
                    try:
                        secret_value_response = client.access_secret_version(request={"name": latest_version.name})
                        secret_value = secret_value_response.payload.data.decode("UTF-8")
                    except Exception:
                        secret_value = None
                    
                    existing_secrets[secret_name] = {
                        "exists": True,
                        "has_versions": True,
                        "latest_version": latest_version.name,
                        "created": latest_version.create_time,
                        "value": secret_value
                    }
                else:
                    existing_secrets[secret_name] = {
                        "exists": True,
                        "has_versions": False,
                        "value": None
                    }
                    
            except Exception:
                # Secret doesn't exist or we can't access it
                existing_secrets[secret_name] = {
                    "exists": False,
                    "value": None
                }
        
        return existing_secrets
        
    except ImportError:
        return {name: {"exists": False, "error": "Secret Manager library not available", "value": None} for name in secret_names}
    except Exception as e:
        return {name: {"exists": False, "error": str(e), "value": None} for name in secret_names}


def _setup_secrets_in_manager(project_id: str, app_id: str, jwt_secret: str, gemini_api_key: str, existing_secrets: dict = None) -> ActionResult:
    """Set up secrets in Google Secret Manager."""
    try:
        from google.cloud import secretmanager
        
        client = secretmanager.SecretManagerServiceClient()
        parent = f"projects/{project_id}"
        
        secrets_created = []
        secrets_updated = []
        secrets_skipped = []
        
        # Define secrets to create
        secrets_to_setup = [
            ("jwt-secret-key", jwt_secret),
            ("gemini-api-key", gemini_api_key)
        ]
        
        for secret_name, secret_value in secrets_to_setup:
            # Skip if secret already exists and has versions
            if existing_secrets and existing_secrets.get(secret_name, {}).get('exists', False) and existing_secrets.get(secret_name, {}).get('has_versions', False):
                secrets_skipped.append(secret_name)
                continue
            try:
                # Try to create the secret
                secret = {
                    "replication": {"automatic": {}}
                }
                
                try:
                    response = client.create_secret(
                        request={
                            "parent": parent,
                            "secret_id": secret_name,
                            "secret": secret
                        }
                    )
                    secrets_created.append(secret_name)
                except Exception as create_error:
                    if "already exists" in str(create_error).lower():
                        # Secret exists, we'll update it
                        pass
                    else:
                        raise create_error
                
                # Add the secret version
                secret_path = f"projects/{project_id}/secrets/{secret_name}"
                client.add_secret_version(
                    request={
                        "parent": secret_path,
                        "payload": {"data": secret_value.encode("UTF-8")}
                    }
                )
                
                if secret_name not in secrets_created:
                    secrets_updated.append(secret_name)
                    
            except Exception as e:
                return ActionResult(
                    name="Secret Manager setup",
                    status="FAILED",
                    details=f"Failed to setup {secret_name}: {str(e)}"
                )
        
        # Build success message
        details_parts = []
        if secrets_created:
            details_parts.append(f"Created: {', '.join(secrets_created)}")
        if secrets_updated:
            details_parts.append(f"Updated: {', '.join(secrets_updated)}")
        if secrets_skipped:
            details_parts.append(f"Skipped (existing): {', '.join(secrets_skipped)}")
        
        details = "; ".join(details_parts) if details_parts else "No changes needed"
        
        return ActionResult(
            name="Secret Manager setup",
            status="DONE",
            details=details
        )
        
    except ImportError:
        return ActionResult(
            name="Secret Manager setup",
            status="FAILED",
            details="Google Cloud Secret Manager library not available"
        )
    except Exception as e:
        return ActionResult(
            name="Secret Manager setup",
            status="FAILED",
            details=f"Secret Manager setup failed: {str(e)}"
        )


def _create_init_plan(
    app_id: str,
    dev_project_id: str,
    registry_project_id: Optional[str],
    jwt_secret: Optional[str],
    gemini_api_key: Optional[str],
    repo_root: Path
) -> Tuple[InitPlan, List[ActionResult]]:
    """Create initialization plan and return planned actions."""
    
    # Use dev project as registry if not specified
    if not registry_project_id:
        registry_project_id = dev_project_id
    
    # Check for existing secrets in Secret Manager
    existing_secrets = _check_existing_secrets(dev_project_id)
    
    # Generate secrets if not provided, but check if they already exist
    if not jwt_secret:
        if existing_secrets.get('jwt-secret-key', {}).get('exists', False):
            jwt_secret = "EXISTING"  # Placeholder to indicate existing secret
        else:
            jwt_secret = _generate_secret_value('jwt', app_id)
    
    if not gemini_api_key:
        if existing_secrets.get('gemini-api-key', {}).get('exists', False):
            gemini_api_key = "EXISTING"  # Placeholder to indicate existing secret
        else:
            gemini_api_key = _generate_secret_value('gemini', app_id)
    
    # Load API configuration to determine structure
    api_config = _load_api_config(repo_root)
    api_module = api_config.get('module', 'core.api:app')
    api_module_name = api_module.split('.')[0]  # Extract module name (e.g., 'core' from 'core.api:app')
    
    config_dir = repo_root / "config"
    tests_dir = repo_root / "tests"
    api_dir = repo_root / api_module_name
    
    planned_actions = []
    
    # Plan configuration files
    if not (config_dir / "app.yaml").exists():
        planned_actions.append(ActionResult("config/app.yaml", "PLANNED", "Will create app configuration"))
    else:
        planned_actions.append(ActionResult("config/app.yaml", "EXISTS", "Already exists"))
    
    # Plan .gitignore handling
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            content = f.read()
        
        if ".projects" in content and not content.count("#.projects"):
            planned_actions.append(ActionResult(".gitignore: .projects", "EXISTS", "Already in .gitignore"))
        elif "#.projects" in content or "# .projects" in content:
            planned_actions.append(ActionResult(".gitignore: .projects", "SKIP", "Explicitly commented out (will be tracked)"))
        else:
            planned_actions.append(ActionResult(".gitignore: .projects", "PLANNED", "Will add to .gitignore"))
    else:
        planned_actions.append(ActionResult(".gitignore: .projects", "ERROR", "No .gitignore file found"))
    
    # Plan test structure
    if not (tests_dir / "providers").exists():
        planned_actions.append(ActionResult("tests/providers", "PLANNED", "Will copy provider tests from SDK"))
    else:
        planned_actions.append(ActionResult("tests/providers", "EXISTS", "Already exists"))
    
    # Plan API files
    api_file_path = f"{api_module_name}/api.py"
    if not (api_dir / "api.py").exists():
        planned_actions.append(ActionResult(api_file_path, "PLANNED", "Will create base API class"))
    else:
        planned_actions.append(ActionResult(api_file_path, "EXISTS", "Already exists"))
    
    if not (tests_dir / "unit" / "test_api.py").exists():
        planned_actions.append(ActionResult("tests/unit/test_api.py", "PLANNED", "Will create API tests"))
    else:
        planned_actions.append(ActionResult("tests/unit/test_api.py", "EXISTS", "Already exists"))
    
    # Plan Secret Manager setup
    planned_actions.append(ActionResult("Secret Manager setup", "PLANNED", "Will create secrets in Google Secret Manager"))
    
    plan = InitPlan(
        app_id=app_id,
        dev_project_id=dev_project_id,
        registry_project_id=registry_project_id,
        jwt_secret=jwt_secret,
        gemini_api_key=gemini_api_key,
        repo_root=repo_root,
        actions_needed=[],  # Legacy field, not used
        actions_completed=[],  # Legacy field, not used
        existing_secrets=existing_secrets
    )
    
    return plan, planned_actions


def _show_plan_and_confirm(plan: InitPlan) -> bool:
    """Show initialization plan and get user confirmation."""
    print("\n" + "="*60)
    print("🚀 MULTI-EDEN APP INITIALIZATION PLAN")
    print("="*60)
    print(f"📱 App ID: {plan.app_id}")
    print(f"🏗️ Dev Project: {plan.dev_project_id}")
    print(f"📦 Registry Project: {plan.registry_project_id}")
    print(f"📂 Repository: {plan.repo_root}")
    
    print(f"\n🔐 Secrets Configuration:")
    
    # JWT Secret status
    jwt_status = plan.existing_secrets.get('jwt-secret-key', {})
    if jwt_status.get('exists', False):
        if jwt_status.get('has_versions', False):
            # Show actual secret value if available
            if jwt_status.get('value'):
                secret_preview = jwt_status['value'][:8] + "..."
            else:
                secret_preview = plan.jwt_secret[:8] + "..."
            print(f"   JWT Secret: {secret_preview} (existing in Secret Manager)")
        else:
            print(f"   JWT Secret: {plan.jwt_secret[:8]}... (existing but no versions)")
    else:
        print(f"   JWT Secret: {plan.jwt_secret[:8]}... (will be generated)")
    
    # Gemini API Key status
    gemini_status = plan.existing_secrets.get('gemini-api-key', {})
    if gemini_status.get('exists', False):
        if gemini_status.get('has_versions', False):
            # Show actual secret value if available
            if gemini_status.get('value'):
                secret_preview = gemini_status['value'][:12] + "..."
            else:
                secret_preview = plan.gemini_api_key[:12] + "..."
            print(f"   Gemini API Key: {secret_preview} (existing in Secret Manager)")
        else:
            print(f"   Gemini API Key: {plan.gemini_api_key[:12]}... (existing but no versions)")
    else:
        print(f"   Gemini API Key: {plan.gemini_api_key[:12]}... (will be generated)")
    
    if plan.actions_completed:
        print(f"\n✅ Already Completed:")
        for action in plan.actions_completed:
            print(f"   {action}")
    
    if plan.actions_needed:
        print(f"\n📋 Actions Needed:")
        for action in plan.actions_needed:
            print(f"   {action}")
    
    print("\n" + "="*60)
    
    response = input("Proceed with initialization? [y/N]: ").strip().lower()
    return response in ['y', 'yes']


def _execute_plan(plan: InitPlan) -> List[ActionResult]:
    """Execute the initialization plan."""
    results = []
    
    try:
        # Find SDK root for copying tests
        sdk_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Load API configuration and create directories
        api_config = _load_api_config(plan.repo_root)
        api_module = api_config.get('module', 'core.api:app')
        api_module_name = api_module.split('.')[0]
        
        config_dir = plan.repo_root / "config"
        tests_dir = plan.repo_root / "tests"
        api_dir = plan.repo_root / api_module_name
        
        config_dir.mkdir(exist_ok=True)
        (tests_dir / "unit").mkdir(parents=True, exist_ok=True)
        
        # Create configuration files
        if not (config_dir / "app.yaml").exists():
            _create_app_yaml(config_dir, plan.app_id, plan.registry_project_id, api_module)
            results.append(ActionResult("config/app.yaml", "DONE", "Created app configuration"))
        else:
            results.append(ActionResult("config/app.yaml", "SKIPPED", "Already exists"))
        
        # Handle .gitignore for .projects
        gitignore_result = _handle_gitignore_projects(plan.repo_root)
        results.append(gitignore_result)
        
        # Create pytest.ini
        if not (plan.repo_root / "pytest.ini").exists():
            _create_pytest_ini(plan.repo_root)
            results.append(ActionResult("pytest.ini", "DONE", "Created pytest configuration"))
        else:
            results.append(ActionResult("pytest.ini", "SKIPPED", "Already exists"))
        
        
        # Create .projects file
        if not (plan.repo_root / ".projects").exists():
            _create_projects_file(plan.repo_root, plan.dev_project_id)
            results.append(ActionResult(".projects", "DONE", "Created project IDs file"))
        else:
            results.append(ActionResult(".projects", "SKIPPED", "Already exists"))
        
        # Copy provider tests
        if not (tests_dir / "providers").exists():
            _copy_provider_tests(plan.repo_root, sdk_root)
            results.append(ActionResult("tests/providers", "DONE", "Copied provider tests from SDK"))
        else:
            results.append(ActionResult("tests/providers", "SKIPPED", "Already exists"))
        
        # Create API files
        api_dir.mkdir(exist_ok=True)
        api_file_path = f"{api_module_name}/api.py"
        
        if not (api_dir / "api.py").exists():
            _create_base_api(api_dir, api_module_name)
            results.append(ActionResult(api_file_path, "DONE", "Created base API class"))
        else:
            results.append(ActionResult(api_file_path, "SKIPPED", "Already exists"))
        
        if not (tests_dir / "unit" / "test_api.py").exists():
            _create_api_test(tests_dir / "unit", api_module_name)
            results.append(ActionResult("tests/unit/test_api.py", "DONE", "Created API tests"))
        else:
            results.append(ActionResult("tests/unit/test_api.py", "SKIPPED", "Already exists"))
        
        # Set up secrets (TODO for now)
        # Setup secrets in Secret Manager
        secret_result = _setup_secrets_in_manager(
            project_id=plan.dev_project_id,
            app_id=plan.app_id,
            jwt_secret=plan.jwt_secret,
            gemini_api_key=plan.gemini_api_key,
            existing_secrets=plan.existing_secrets
        )
        results.append(secret_result)
        
    except Exception as e:
        results.append(ActionResult("Execution", "FAILED", f"Error: {e}"))
    
    return results


def _display_actions_table(actions: List[ActionResult], title: str) -> None:
    """Display actions in a formatted table."""
    print("\n" + "="*60)
    print(f"📋 {title}")
    print("="*60)
    
    # Calculate column width for component names
    max_name_width = max(len(action.name) for action in actions)
    name_width = max(max_name_width, 25)
    
    # Header
    print(f"{'COMPONENT':<{name_width}} STATUS")
    print("-" * 60)
    
    # Status icons and descriptions
    status_display = {
        # Execution results
        "DONE": "[✓] Completed",
        "SKIPPED": "[-] Skipped",
        "PENDING": "[~] Pending",
        "FAILED": "[✗] Failed",
        # Planning statuses - using same symbols as execution for consistency
        "PLANNED": "[✓] Will create",
        "EXISTS": "[-] Already exists",
        "SKIP": "[-] Will skip",
        "TODO": "[~] Not implemented",
        "ERROR": "[✗] Error"
    }
    
    # Results
    for action in actions:
        status_text = status_display.get(action.status, f"❓ {action.status}")
        print(f"{action.name:<{name_width}} {status_text}")
        # Show details for failed actions
        if action.status == "FAILED" and action.details:
            print(f"{'':>{name_width}} Error: {action.details}")
    
    # Summary (different for planning vs results)
    if any(a.status in ["DONE", "SKIPPED", "PENDING", "FAILED"] for a in actions):
        # Execution summary
        done_count = sum(1 for a in actions if a.status == "DONE")
        skipped_count = sum(1 for a in actions if a.status == "SKIPPED")
        pending_count = sum(1 for a in actions if a.status == "PENDING")
        failed_count = sum(1 for a in actions if a.status == "FAILED")
        print("-" * 60)
        print(f"Summary: {done_count} completed, {skipped_count} skipped, {pending_count} pending, {failed_count} failed")
    else:
        # Planning summary
        planned_count = sum(1 for a in actions if a.status == "PLANNED")
        exists_count = sum(1 for a in actions if a.status == "EXISTS")
        skip_count = sum(1 for a in actions if a.status == "SKIP")
        todo_count = sum(1 for a in actions if a.status == "TODO")
        error_count = sum(1 for a in actions if a.status == "ERROR")
        print("-" * 60)
        print(f"Summary: {planned_count} planned, {exists_count} existing, {skip_count} skipped, {todo_count} todo, {error_count} errors")
    
    print("="*60)


@task
def init_app(c, app_id, dev_project_id, registry_project_id=None, jwt_secret_key=None, gemini_api_key=None):
    """
    Initialize a new Multi-Eden application.
    
    Args:
        app_id: Application identifier (e.g., 'my-food-app')
        dev_project_id: Google Cloud project ID for development
        registry_project_id: Project ID for container registry (defaults to dev_project_id)
        jwt_secret_key: JWT secret (generated if not provided)
        gemini_api_key: Gemini API key (generated if not provided)
    """
    
    repo_root = Path.cwd()
    
    print("🔍 Validating repository structure...")
    
    # Validate repo structure
    issues = _validate_repo_structure(repo_root)
    if issues:
        print("❌ Repository validation failed:")
        for issue in issues:
            print(f"   {issue}")
        sys.exit(1)
    
    # Check for existing configuration
    config_dir = repo_root / "config"
    existing_config = _check_existing_config(config_dir)
    
    if existing_config:
        existing_app_id = existing_config.get('app_id')
        existing_project = existing_config.get('dev_project_id')
        
        if existing_app_id and existing_app_id != app_id:
            print(f"❌ Existing app ID '{existing_app_id}' conflicts with '{app_id}'")
            print(f"💡 Run with: --app-id={existing_app_id} --dev-project-id={existing_project or 'UNKNOWN'}")
            sys.exit(1)
        
        if existing_project and existing_project != dev_project_id:
            print(f"❌ Existing project ID '{existing_project}' conflicts with '{dev_project_id}'")
            print(f"💡 Run with: --app-id={existing_app_id or app_id} --dev-project-id={existing_project}")
            sys.exit(1)
    
    # Create initialization plan
    plan, planned_actions = _create_init_plan(
        app_id=app_id,
        dev_project_id=dev_project_id,
        registry_project_id=registry_project_id,
        jwt_secret=jwt_secret_key,
        gemini_api_key=gemini_api_key,
        repo_root=repo_root
    )
    
    # Show planned actions
    _display_actions_table(planned_actions, "INITIALIZATION PLAN")
    
    # Show plan summary and get confirmation
    if not _show_plan_and_confirm(plan):
        print("❌ Initialization cancelled")
        sys.exit(0)
    
    # Execute plan
    print("\n🚀 Executing initialization plan...")
    results = _execute_plan(plan)
    
    # Show results in formatted table
    _display_actions_table(results, "INITIALIZATION RESULTS")
    
    # Check if there were any failures
    failed_count = sum(1 for r in results if r.status == "FAILED")
    if failed_count > 0:
        print(f"\n⚠️  Initialization completed with {failed_count} failure(s). Please review and fix issues.")
    else:
        print(f"\n🎉 Multi-Eden app '{app_id}' initialized successfully!")
        print(f"💡 Next steps:")
        print(f"   1. Run: ./invoke test unit")
        print(f"   2. Develop your app in the {plan.app_id.replace('-', '_')}/ directory")
        print(f"   3. Deploy with: ./invoke deploy dev")
