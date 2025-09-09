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
        "--dproj",
        action="store",
        default=None,
        help="Specify project alias for PROJECT_ID resolution (e.g., dev, prod)"
    )
    parser.addoption(
        "--target",
        action="store",
        default=None,
        help="Specify target profile for side-loading (e.g., dev, prod)"
    )


def pytest_configure(config):
    """Configure pytest with environment-specific settings."""
    # The pytest plugin handles --dproj and --target parameters
    # for PROJECT_ID resolution and side-loading
    pass


def pytest_sessionstart(session):
    """Called after the Session object has been created and before performing collection and entering the run test loop."""
    # Clear the cache at the start of each test session to ensure fresh loads
    from multi_eden.build.config.loading import clear_env
    clear_env()


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
        # Handle --dproj parameter by setting PROJECT_ID before load_env
        dproj = None
        target_profile = None
        if hasattr(item, 'config') and hasattr(item.config, 'getoption'):
            try:
                dproj = item.config.getoption("--dproj")
                target_profile = item.config.getoption("--target")
                
                if dproj:
                    # Set PROJECT_ID from .projects file
                    from multi_eden.build.config.loading import get_project_id_from_projects_file
                    project_id = get_project_id_from_projects_file(dproj)
                    os.environ['PROJECT_ID'] = project_id

            except:
                pass
        
        try:
            # Load environment with target as base layer
            from multi_eden.build.config.models import LoadParams
            params = LoadParams(
                top_layer=env_layer,
                base_layer=target_profile
            )
            load_env(params)
                    
        except ConfigException as e:
            # Use the exception's built-in guidance
            pytest.skip(f"Test requires {env_layer} environment but configuration is missing: {e.guidance}")
        except Exception as e:
            # For other errors, log and let test decide
            print(f"Warning: Failed to load environment '{env_layer}' for {test_file_path}: {e}")




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


def _get_api_module_from_config() -> Optional[str]:
    """
    Get the API module path from app.yaml configuration.
    
    Returns the module path (e.g., "core.api:app") or None if not found.
    """
    try:
        # Look for app.yaml in current working directory
        app_yaml_path = Path.cwd() / 'config' / 'app.yaml'
        if not app_yaml_path.exists():
            app_yaml_path = Path.cwd() / 'app.yaml'
        
        if app_yaml_path.exists():
            with open(app_yaml_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('api', {}).get('module')
        
        return None
    except Exception:
        return None


@pytest.fixture(scope="function")
def api_client():
    """
    API client that chooses type based on TEST_API_MODE environment variable.
    
    - TEST_API_MODE=IN_MEMORY: Returns InMemoryAPITestClient
    - TEST_API_MODE=REMOTE: Returns RemoteAPITestClient
    - TEST_API_MODE not set: Returns None
    """
    from multi_eden.build.api_client.in_memory_client import InMemoryAPITestClient
    from multi_eden.build.api_client.remote_client import RemoteAPITestClient
    
    test_api_mode = os.environ.get('TEST_API_MODE')
    
    if test_api_mode is None:
        return None
    
    if test_api_mode == 'IN_MEMORY':
        # In-memory API client
        try:
            from fastapi.testclient import TestClient
            # Try to import the app module - this will be configured per app
            # Read the API module from app.yaml configuration
            app_module = _get_api_module_from_config()
            if not app_module:
                pytest.skip("API module not configured in app.yaml")
            
            import importlib
            module_path, app_name = app_module.split(':')
            module = importlib.import_module(module_path)
            app = getattr(module, app_name)
            fastapi_client = TestClient(app)
            return InMemoryAPITestClient(fastapi_client)
        except ImportError as e:
            pytest.skip(f"InMemoryAPITestClient not available: {e}")
    
    elif test_api_mode == 'REMOTE':
        # Remote API client - build URL based on environment
        api_url = _build_remote_api_url()
        print(f"DEBUG: test_api_mode=REMOTE, api_url={api_url}")
        if not api_url:
            pytest.skip("❌ Remote API testing requires a target server. Options:\n"
                       "  • Run with --target=local to test against local server\n"
                       "  • Set TEST_API_URL environment variable manually\n"
                       "  • Use IN_MEMORY mode instead of REMOTE mode")
        
        print(f"DEBUG: Creating RemoteAPITestClient with URL: {api_url}")
        return RemoteAPITestClient(api_url, auth_required=True)
    
    else:
        pytest.skip(f"Invalid TEST_API_MODE value: {test_api_mode}. Use IN_MEMORY or REMOTE.")


def _build_remote_api_url() -> Optional[str]:
    """
    Build the remote API URL based on environment variables.
    
    Returns None if unable to build a valid URL.
    """
    # Check if we have a pre-built URL
    if 'TEST_API_URL' in os.environ:
        return os.environ['TEST_API_URL']
    
    # Check if we're targeting local
    local = os.environ.get('LOCAL', '').lower()
    print(f"DEBUG: LOCAL={local}")
    if local == 'true':
        # Use localhost with default port
        port = os.environ.get('PORT', '8000')
        url = f"http://localhost:{port}"
        print(f"DEBUG: Built URL: {url}")
        return url
    
    # Check if we have cloud testing configuration
    project_id = os.environ.get('PROJECT_ID')
    app_id = os.environ.get('APP_ID')
    if project_id and app_id:
        # Build URL for cloud project
        # This would need to be configured based on your deployment setup
        # For now, return None to indicate we can't build it
        return None
    
    # No way to build URL
    return None

