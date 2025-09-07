"""
Pytest plugin for automatic environment loading based on test file paths.

This plugin automatically loads the appropriate environment configuration
for each test based on the test file's path, using YAML-driven pattern matching.
"""

import os
import yaml
import pytest
import sys
from pathlib import Path
from typing import Dict, Optional, Any, List
from multi_eden.build.config.loading import load_env
from multi_eden.build.config.exceptions import ConfigException


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--env-name",
        action="store",
        default=None,
        help="Specify environment name for PROJECT_ID resolution"
    )


def pytest_configure(config):
    """Configure pytest with environment-specific settings."""
    env_name = config.getoption("--env-name")
    
    if env_name:
        # If --env-name is provided, try to resolve PROJECT_ID from .projects file
        try:
            project_id = _resolve_project_id_from_projects_file(env_name)
            if project_id:
                os.environ['PROJECT_ID'] = project_id
            else:
                # Fail fast if PROJECT_ID cannot be resolved
                print(f"❌ Environment '{env_name}' not found in .projects file", file=sys.stderr)
                print("💡 Available environments:", file=sys.stderr)
                _list_available_environments()
                sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to resolve PROJECT_ID for environment '{env_name}': {e}", file=sys.stderr)
            sys.exit(1)


def pytest_runtest_setup(item):
    """
    Called before each test runs to load the appropriate environment.
    
    This hook runs before each individual test, ensuring proper environment
    isolation between tests that require different environment configurations.
    """
    # Get the test file path
    test_file_path = str(item.fspath)
    # Load environment based on test file path
    env_layer = _get_environment_for_test_path(test_file_path)
    
    if env_layer:
        try:
            load_env(top_layer=env_layer, fail_on_secret_error=True)
        except ConfigException as e:
            # Use the exception's built-in guidance
            pytest.skip(f"Test requires {env_layer} environment but configuration is missing: {e.guidance}")
        except Exception as e:
            # For other errors, log and let test decide
            print(f"Warning: Failed to load environment '{env_layer}' for {test_file_path}: {e}")


def _resolve_project_id_from_projects_file(env_name: str) -> Optional[str]:
    """Resolve PROJECT_ID from .projects file for given environment name."""
    projects_file = Path.cwd() / '.projects'
    
    if not projects_file.exists():
        return None
    
    try:
        with open(projects_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == env_name:
                        return value.strip()
    except Exception:
        pass
    
    return None


def _list_available_environments():
    """List available environments from .projects file."""
    projects_file = Path.cwd() / '.projects'
    
    if not projects_file.exists():
        print("   No .projects file found", file=sys.stderr)
        return
    
    try:
        with open(projects_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    print(f"   {key.strip()}={value.strip()}", file=sys.stderr)
    except Exception:
        print("   Error reading .projects file", file=sys.stderr)


def _get_environment_for_test_path(test_path: str) -> Optional[str]:
    """
    Determine which environment layer to load based on the test file path.
    
    Uses tests.yaml paths section for direct path-to-environment mapping.
    """
    # Load test configuration
    test_config = _load_test_config()
    
    # Get paths from config (for pytest path-based mapping)
    paths = test_config.get('paths', {})
    
    # Find the first path pattern that matches this test file
    for path_pattern, env_layer in paths.items():
        if path_pattern in test_path:
            return env_layer
    
    # No pattern matched
    return None


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add skip summary with guidance to the terminal output."""
    if not terminalreporter.stats.get('skipped'):
        return
    
    terminalreporter.write_sep("=", "SKIP SUMMARY")
    terminalreporter.write_line("")
    
    # Group skipped tests by reason
    skip_reasons = {}
    for report in terminalreporter.stats['skipped']:
        reason = getattr(report, 'longrepr', 'No reason provided')
        if reason not in skip_reasons:
            skip_reasons[reason] = []
        skip_reasons[reason].append(report.nodeid)
    
    # Display each skip reason with guidance
    for reason, test_ids in skip_reasons.items():
        terminalreporter.write_line(f"❌ {len(test_ids)} tests skipped:")
        # Split the reason by newlines and write each line separately
        reason_lines = str(reason).split('\\n')
        for line in reason_lines:
            terminalreporter.write_line(line)
        terminalreporter.write_line("")
    
    terminalreporter.write_line("")


def _load_test_config() -> Dict[str, Any]:
    """
    Load test configuration from tests.yaml.
    
    Looks for tests.yaml in the current working directory,
    falling back to SDK config if not found.
    """
    # Try to load app-specific tests.yaml first
    config_path = Path.cwd() / 'tests.yaml'
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load tests.yaml: {e}")
    
    # Fall back to SDK config
    sdk_config_path = Path(__file__).parent / 'build' / 'config' / 'tests.yaml'
    if sdk_config_path.exists():
        try:
            with open(sdk_config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load SDK tests.yaml: {e}")
    
    # No configuration found
    return {}


@pytest.fixture(scope="function")
def api_client():
    """
    Optional API client that chooses type based on TEST_API_IN_MEMORY environment variable.
    
    Only provided if TEST_API_IN_MEMORY is explicitly set:
    - TEST_API_IN_MEMORY=true: Returns InMemoryAPITestClient
    - TEST_API_IN_MEMORY=false: Returns RemoteAPITestClient  
    - TEST_API_IN_MEMORY not set: Returns None (fixture not provided)
    """
    import os
    
    test_api_in_memory = os.environ.get('TEST_API_IN_MEMORY')
    if not test_api_in_memory:
        # Don't provide fixture if TEST_API_IN_MEMORY is not set
        pytest.skip("TEST_API_IN_MEMORY not set - api_client fixture not available")
    
    from multi_eden.build.api_client.in_memory_client import InMemoryAPITestClient
    from multi_eden.build.api_client.remote_client import RemoteAPITestClient
    
    if test_api_in_memory.lower() == 'true':
        # In-memory API client
        try:
            from fastapi.testclient import TestClient
            # Try to import the app module - this will be configured per app
            from core.api import app
            fastapi_client = TestClient(app)
            return InMemoryAPITestClient(fastapi_client, auth_required=True)
        except ImportError as e:
            pytest.skip(f"InMemoryAPITestClient not available: {e}")
    
    elif test_api_in_memory.lower() == 'false':
        # Remote API client
        api_url = os.environ.get('TEST_API_URL', 'http://localhost:8000')
        return RemoteAPITestClient(api_url, auth_required=True)
    
    else:
        pytest.skip(f"Invalid TEST_API_IN_MEMORY value: {test_api_in_memory}")