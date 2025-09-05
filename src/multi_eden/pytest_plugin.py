"""
Pytest plugin for automatic environment loading based on test file paths.

This plugin automatically loads the appropriate environment configuration
for each test based on the test file's path, using YAML-driven pattern matching.
"""

import os
import yaml
import pytest
from pathlib import Path
from typing import Dict, Optional, Any, List
from multi_eden.build.config.loading import load_env
from multi_eden.build.config.exceptions import (
    ProjectIdNotFoundException, 
    ProjectsFileNotFoundException,
    SecretUnavailableException
)

# Global collection to store guidance information
_guidance_messages: List[Dict[str, Any]] = []


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
        except (ProjectIdNotFoundException, ProjectsFileNotFoundException, SecretUnavailableException) as e:
            # For missing configuration, capture guidance information and skip
            _capture_guidance_info_from_exception(env_layer, e, test_file_path)
            pytest.skip(f"Test requires {env_layer} environment but configuration is missing: {e}")
        except Exception as e:
            # For other errors, log and let test decide
            print(f"Warning: Failed to load environment '{env_layer}' for {test_file_path}: {e}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Provide helpful footer output when tests are skipped due to missing configuration.
    """
    if not _guidance_messages:
        return
    
    # Group guidance messages by suite name
    guidance_by_suite = {}
    for msg in _guidance_messages:
        suite_name = msg['suite_name']
        if suite_name not in guidance_by_suite:
            guidance_by_suite[suite_name] = []
        guidance_by_suite[suite_name].append(msg)
    
    # Print guidance for each suite
    for suite_name, messages in guidance_by_suite.items():
        if not messages:
            continue
        
        # Use the guidance from the first message (they should all be the same for same suite)
        guidance = messages[0]['guidance']
        
        # Print header
        terminalreporter.write_sep("=", f"{suite_name.upper()} TESTS SKIPPED")
        
        # Print guidance lines
        for line in guidance:
            terminalreporter.write_line(line)
        
        terminalreporter.write_line("")


def _capture_guidance_info_from_exception(env_layer: str, exception: Exception, test_file_path: str):
    """
    Capture guidance information from strongly-typed exceptions.
    
    This uses the exception properties to build precise guidance.
    """
    # Determine environment type from config
    test_config = _load_test_config()
    suites = test_config.get('suites', {})
    env_type = env_layer
    for suite_name, suite_config in suites.items():
        if suite_config.get('env') == env_layer:
            env_type = suite_name
            break
    
    # Determine secrets configuration
    secrets_config = 'unknown'
    app_config_path = Path.cwd() / 'config' / 'app.yaml'
    if app_config_path.exists():
        try:
            with open(app_config_path, 'r') as f:
                app_config = yaml.safe_load(f) or {}
                secrets_manager = app_config.get('secrets', {}).get('manager', '')
                if secrets_manager:
                    secrets_config = secrets_manager
        except Exception:
            pass
    elif (Path.cwd() / '.secrets').exists():
        secrets_config = 'local'
    elif 'multi-eden' in str(Path.cwd()):
        secrets_config = 'sdk'
    
    # Generate guidance based on exception type and properties
    if isinstance(exception, (ProjectIdNotFoundException, ProjectsFileNotFoundException)):
        # Generate PROJECT_ID guidance
        suite_description = suites.get(env_type, {}).get('description', f'{env_type.title()} tests')
        guidance = [f"❌ {suite_description} were skipped due to missing {exception.var_name}"]
        guidance.append("💡 To run these tests:")
        
        if isinstance(exception, ProjectsFileNotFoundException):
            # .projects file doesn't exist
            guidance.extend([
                "   1. Create .projects file with project ID:",
                f"      {exception.env_name or 'dev'}=my-google-cloud-project-id",
                "   2. Or configure PROJECT_ID directly in environments.yaml:",
                f"      Add {exception.var_name}: \"my-project-id\" under {exception.configured_layer or env_layer} layer"
            ])
        else:
            # ProjectIdNotFoundException - file exists but environment not found
            guidance.extend([
                "   1. Add project ID to .projects file:",
                f"      {exception.env_name or 'dev'}=my-google-cloud-project-id",
                "   2. Or configure PROJECT_ID directly in environments.yaml:",
                f"      Add {exception.var_name}: \"my-project-id\" under {exception.configured_layer or env_layer} layer"
            ])
        
        missing_config = exception.var_name or "PROJECT_ID"
        
    elif isinstance(exception, SecretUnavailableException):
        # Generate secret guidance
        suite_description = suites.get(env_type, {}).get('description', f'{env_type.title()} tests')
        secret_name = exception.secret_name or exception.var_name or "secret"
        guidance = [f"❌ {suite_description} were skipped due to missing {secret_name}"]
        guidance.append("💡 To run these tests:")
        
        if secrets_config == 'local':
            guidance.append(f"   1. Run: invoke secrets set {secret_name.lower().replace('_', '-')}")
            guidance.append("      (This uses the local secrets manager per your app.yaml configuration)")
        elif secrets_config == 'google':
            guidance.append(f"   1. Run: invoke secrets set {secret_name.lower().replace('_', '-')} --config-env=dev")
        else:
            guidance.append(f"   1. Configure {secret_name} in your environment")
        
        missing_config = exception.var_name or exception.secret_name or "unknown"
        
    else:
        # Fallback for unknown exceptions
        suite_description = suites.get(env_type, {}).get('description', f'{env_type.title()} tests')
        guidance = [
            f"❌ {suite_description} were skipped due to configuration error",
            "💡 Check your environment configuration",
            f"   Error: {str(exception)}"
        ]
        missing_config = "unknown"
    
    # Store guidance information
    _guidance_messages.append({
        'suite_name': env_type,
        'env_layer': env_layer,
        'missing_config': missing_config,
        'secrets_config': secrets_config,
        'test_file_path': test_file_path,
        'error_message': str(exception),
        'guidance': guidance
    })


def _capture_guidance_info(env_layer: str, error_message: str, test_file_path: str):
    """
    Legacy function for backward compatibility.
    """
    # Determine environment type and missing configuration
    env_type, missing_config = _analyze_environment_error(env_layer, error_message)
    
    # Determine secrets configuration
    secrets_config = _detect_secrets_config()
    
    # Generate guidance based on environment type and secrets configuration
    guidance = _generate_guidance(env_type, missing_config, secrets_config)
    
    # Store guidance information
    _guidance_messages.append({
        'suite_name': env_type,
        'env_layer': env_layer,
        'missing_config': missing_config,
        'secrets_config': secrets_config,
        'test_file_path': test_file_path,
        'error_message': error_message,
        'guidance': guidance
    })


def _analyze_environment_error(env_layer: str, error_message: str) -> tuple[str, str]:
    """
    Analyze the environment error to determine the type and missing configuration.
    """
    # Get environment type from test configuration
    env_type = _get_environment_type_from_config(env_layer)
    
    # Extract missing configuration from error message using regex
    missing_config = _extract_missing_config_from_error(error_message)
    
    return env_type, missing_config


def _get_environment_type_from_config(env_layer: str) -> str:
    """
    Get environment type from test configuration, falling back to env_layer name.
    """
    test_config = _load_test_config()
    suites = test_config.get('suites', {})
    
    # Find the suite that uses this environment layer
    for suite_name, suite_config in suites.items():
        if suite_config.get('env') == env_layer:
            # Use suite name as environment type
            return suite_name
    
    # Fallback to env_layer name if not found in config
    return env_layer


def _extract_missing_config_from_error(error_message: str) -> str:
    """
    Extract missing configuration from error message using pattern matching.
    """
    import re
    
    # Look for common patterns in error messages
    patterns = [
        r"Setting '([^']+)' is defined but value not found",
        r"Secret '([^']+)' not found",
        r"Environment variable '([^']+)' not set",
        r"Missing required configuration: '([^']+)'"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_message)
        if match:
            return match.group(1)
    
    # Fallback: extract any ALL_CAPS variable names
    caps_match = re.search(r'([A-Z_]+)', error_message)
    if caps_match:
        return caps_match.group(1)
    
    return 'unknown'


def _detect_secrets_config() -> str:
    """
    Detect the secrets configuration from app.yaml.
    """
    # Check for app configuration
    app_config_path = Path.cwd() / 'config' / 'app.yaml'
    if app_config_path.exists():
        try:
            with open(app_config_path, 'r') as f:
                app_config = yaml.safe_load(f) or {}
                secrets_manager = app_config.get('secrets', {}).get('manager', '')
                if secrets_manager:
                    return secrets_manager
        except Exception:
            pass
    
    # Check for .secrets file (indicates local secrets)
    if (Path.cwd() / '.secrets').exists():
        return 'local'
    
    # Default fallback
    return 'unknown'




def _generate_guidance(env_type: str, missing_config: str, secrets_config: str) -> List[str]:
    """
    Generate guidance based on environment type, missing configuration, and secrets configuration.
    """
    guidance = []
    
    # Get suite description from config
    suite_description = _get_suite_description(env_type)
    
    # Generate generic guidance
    guidance.append(f"❌ {suite_description} were skipped due to missing {missing_config}")
    guidance.append("💡 To run these tests:")
    
    # Add specific guidance based on missing configuration type
    if missing_config == 'PROJECT_ID':
        # PROJECT_ID is not a secret - it's configured in environments.yaml
        guidance.extend([
            "   1. Configure PROJECT_ID in environments.yaml:",
            "      - Add PROJECT_ID: \"$.projects.dev\" to an environment, OR",
            "      - Add PROJECT_ID: \"my-project-id\" directly to an environment",
            "   2. Set BASE_ENV_LAYER to that environment (e.g., integration-test, dev)"
        ])
    else:
        # These are actual secrets that need to be configured
        if secrets_config == 'local':
            guidance.extend([
                "   1. Set up .secrets file locally, OR",
                "   2. Set BASE_ENV_LAYER to an environment that includes this secret (e.g., dev)"
            ])
        elif secrets_config == 'google':
            guidance.append(f"   1. Run: invoke secrets set {missing_config.lower().replace('_', '-')} --config-env=dev")
        else:  # unknown
            guidance.append(f"   1. Configure {missing_config} in your environment")
    
    return guidance


def _get_suite_description(env_type: str) -> str:
    """
    Get suite description from test configuration.
    """
    test_config = _load_test_config()
    suites = test_config.get('suites', {})
    
    suite_config = suites.get(env_type, {})
    description = suite_config.get('description', f'{env_type.title()} tests')
    
    return description




def _get_environment_for_test_path(test_path: str) -> Optional[str]:
    """
    Determine which environment layer to load based on the test file path.
    
    Uses tests.yaml to find which suite the test belongs to and loads its environment.
    """
    # Load test suite configuration
    test_config = _load_test_config()
    
    # Get suites from config
    suites = test_config.get('suites', {})
    
    # Find the first suite whose test paths match this test file
    for suite_name, suite_config in suites.items():
        test_paths = suite_config.get('tests', [])
        for test_path_pattern in test_paths:
            if test_path_pattern in test_path:
                return suite_config.get('env')
    
    # No pattern matched
    return None


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


