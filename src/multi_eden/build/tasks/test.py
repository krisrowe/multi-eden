"""
Test runner tasks for multi-env-sdk.

This module provides tasks for running different types of tests
with appropriate configuration and environment setup.
"""

import sys
from pathlib import Path
from typing import Optional

from invoke import task
from multi_eden.build.tasks.config.setup import get_task_default_env
import os
import logging

from multi_eden.run.config.logging import bootstrap_logging

# Bootstrap logging to respect LOG_LEVEL environment variable
bootstrap_logging()
logger = logging.getLogger(__name__)


def get_test_api_url():
    """Get the test API URL based on current environment configuration.
    
    Delegates to the shared testing utility.
    
    Returns:
        list: List of (var_name, var_value, var_source) tuples
    """
    from multi_eden.build.config.testing import get_test_api_url as shared_get_test_api_url
    return shared_get_test_api_url()


def _get_test_paths(suite: str) -> list:
    """Get test paths for a suite without loading full test config."""
    import yaml
    from pathlib import Path
    
    tests_yaml = Path(__file__).parent.parent / "config" / "tests.yaml"
    try:
        with open(tests_yaml, 'r') as f:
            config = yaml.safe_load(f)
        
        suite_config = config.get('suites', {}).get(suite, {})
        test_paths = suite_config.get('tests', [])
        
        # If providers is in the list, ensure it runs FIRST
        if 'tests/providers' in test_paths and test_paths.index('tests/providers') != 0:
            test_paths = test_paths.copy()
            test_paths.remove('tests/providers')
            test_paths.insert(0, 'tests/providers')
            
        return test_paths
    except Exception as e:
        print(f"⚠️  Failed to load test paths for '{suite}': {e}", file=sys.stderr)
        return []


@task(help={
    'suite': 'Test suite to run (unit, ai, firestore, api)',
    'target': 'Target profile for side-loading (e.g., local, dev, prod)',
    'verbose': 'Enable verbose output',
    'test_name': 'Filter to specific test method(s) (e.g., "test_long_name_product" or "test_*")',
    'show_config': 'Show detailed configuration including partial secret values',
    'quiet': 'Suppress configuration display (show only test results)'
})
def test(ctx, suite, target=None, config_env=None, verbose=False, test_name=None, show_config=False, quiet=False):
    """
    Run tests for a specific suite.
    
    Examples:
        inv test unit                    # Run unit tests with suite default env
        inv test api --config-env=local-server # Run API tests with specific env
        inv test ai --verbose           # Run AI tests with verbose output
        inv test ai --test-name=test_long_name_product  # Run specific AI test
        inv test unit --test-name="test_*auth*"        # Run auth-related unit tests
    """
    if suite is None:
        print("❌ Error: Test suite is required")
        print("   Usage: inv test <suite>")
        print("   Available suites: unit, ai, firestore, api")
        sys.exit(1)
    
    # Load test suite config once
    test_config = None
    # Environment loading is handled by the pytest plugin
    # Just get test paths for pytest - no need to reload full test config
    test_paths = _get_test_paths(suite) if suite else None
    
    return run_pytest(suite, target, config_env, verbose, test_name, show_config, test_paths, quiet)


def run_pytest(suite, target, config_env, verbose, test_name=None, show_config=False, test_paths=None, quiet=False):
    """
    Run pytest with the specified suite and environment.
    
    Args:
        suite: Test suite name
        target: Target profile for side-loading (e.g., local, dev, prod)
        config_env: Configuration environment (legacy parameter)
        verbose: Whether to enable verbose output
        test_name: Optional test name filter (e.g., "test_long_name_product")
        show_config: Whether to show detailed configuration including secrets
        test_paths: Pre-loaded test paths (optional)
        quiet: Whether to suppress runtime configuration display
        
    Returns:
        subprocess.CompletedProcess: Result of pytest execution
    """
    # Test paths are passed in (already processed by _get_test_paths)
    
    if not test_paths:
        print(f"⚠️  No test paths configured for suite '{suite}'")
        return None
    
    # Test paths and override message are now shown in configuration environment table
    
    # Environment configuration already loaded by decorator
    if config_env:
        try:
            # Show all configuration tables (both normal and --show-config)
            _show_all_configuration_tables(config_env)
            
            # Show runtime configuration for --show-config
            if show_config:
                from ...run.config import print_runtime_configuration
                print_runtime_configuration()
                print("📊 Configuration display complete. Exiting without running tests.")
                return None
                
        except Exception as e:
            print(f"⚠️  Could not load configuration for environment '{config_env}': {e}")
            if show_config:
                return None
    
    # Use current environment variables (set by load_env)
    # Environment variables are already set by load_env() in the current process
    
    # Use the virtual environment's pytest directly (same as Makefile)
    venv_pytest = Path.cwd() / "venv" / "bin" / "pytest"
    if venv_pytest.exists():
        pytest_executable = str(venv_pytest)
        logger.debug(f"🐍 Using virtual environment pytest: {pytest_executable}")
    else:
        pytest_executable = "python"
        logger.debug(f"🐍 Using system pytest: {pytest_executable}")
    
    # Build pytest command
    if pytest_executable != "python":
        cmd = [pytest_executable]
    else:
        cmd = [pytest_executable, "-m", "pytest"]
    
    cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--capture=no"
    ])
    
    # Filter out integration tests if omit-integration is true
    if os.environ.get('TEST_OMIT_INTEGRATION', '').lower() == 'true':
        cmd.extend(["-m", "not integration"])
        logger.debug(f"🔒 Filtering out integration tests for {suite} test suite (omit-integration: true)")
    
    if config_env:
        cmd.extend(["--config-env", config_env])
    
    if target:
        cmd.extend(["--target", target])
    
    if verbose:
        cmd.append("-v")
    
    # Add test name filter if specified
    if test_name:
        cmd.extend(["-k", test_name])
        print(f"🎯 Filtering tests by name: {test_name}")
    
    # Add test paths (filter out non-existent ones)
    valid_test_paths = []
    for path in test_paths:
        test_path = Path.cwd() / path
        if test_path.exists():
            valid_test_paths.append(path)
        else:
            logger.debug(f"Test path not found, skipping: {path}")
    
    if not valid_test_paths:
        print(f"❌ No valid test paths found for suite '{suite}'")
        return None
    
    cmd.extend(valid_test_paths)
    
    logger.debug(f"🔍 Including pytest {' '.join(cmd[4:])}")
    
    # Show runtime configuration that tests will use (unless quiet)
    if not quiet:
        from ...run.config import print_runtime_configuration
        print_runtime_configuration()
    
    # Run pytest as a subprocess to ensure proper plugin loading
    # This ensures the pytest plugin hooks work correctly
    logger.debug(f"🧪 Running {suite} tests...")
    
    import subprocess
    import sys
    
    try:
        # Run pytest as subprocess to ensure proper plugin loading
        result = subprocess.run(cmd, cwd=Path.cwd())
        
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print(f"❌ Tests failed with exit code {result.returncode}")
        
        return result.returncode
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return 1




@task(help={
    'suite': 'Test suite to configure',
    'env': 'Configuration environment to use'
})
def pytest_config(ctx, suite, env=None):
    """
    Show pytest configuration for a specific suite.
    
    This is useful for debugging test configuration issues.
    """
    if suite is None:
        print("❌ Error: Test suite is required")
        print("   Usage: inv pytest-config <suite>")
        sys.exit(1)
    
    print(f"🔧 Pytest configuration for suite: {suite}")
    print(f"📁 Working directory: {Path.cwd()}")
    
    # Get test paths
    test_paths = get_test_paths_from_config(suite)
    if test_paths:
        print(f"📋 Test paths: {test_paths}")
    else:
        print("⚠️  No test paths configured")
    
    # Check integration filtering
    if should_omit_integration_tests(suite):
        print("🔒 Integration tests will be filtered out")
    else:
        print("🔓 Integration tests will be included")
    
    # Show environment
    if env:
        print(f"🌍 Using environment: {env}")
    else:
        print("⚠️  No environment specified - test mode must provide complete config")
    
    # Show pytest command that would be run
    cmd = ["python", "-m", "pytest"]
    if should_omit_integration_tests(suite):
        cmd.extend(["-m", "not integration"])
    if test_paths:
        for path in test_paths:
            cmd.append(f"tests/{path}")
    
    print(f"🚀 Pytest command: {' '.join(cmd)}")


def _show_secrets_configuration(config_env):
    """
    Display secrets configuration with partial values for debugging.
    
    Args:
    """
    print("\n" + "=" * 74)
    print("🔐 SECRETS CONFIGURATION")
    print("=" * 74)
    
    try:
        # Load secrets manifest from YAML
        from multi_eden.build.secrets.manifest import load_secrets_manifest
        import os
        
        secrets_found = []
        secrets_missing = []
        
        # Load the secrets definitions
        secret_definitions = load_secrets_manifest()
        
        for secret_def in secret_definitions:
            secret_name = secret_def.name
            env_var_name = secret_def.env_var  # This is a property that converts name to ENV_VAR format
            secret_value = os.environ.get(env_var_name)
            
            if secret_value:
                # Show partial value (20-25% of characters)
                partial_length = max(3, len(secret_value) // 4)  # 25% but at least 3 chars
                if len(secret_value) <= 8:
                    # For very short secrets, show first 3 chars
                    partial_value = secret_value[:3] + "..."
                else:
                    # For longer secrets, show first portion + "..."
                    partial_value = secret_value[:partial_length] + "..."
                
                secrets_found.append((secret_name, env_var_name, partial_value))
            else:
                secrets_missing.append((secret_name, env_var_name))
        
        # Combine all secrets into one table
        all_secrets = []
        
        # Add configured secrets
        for secret_name, env_var, partial_value in secrets_found:
            all_secrets.append((secret_name, env_var, f"✅ {partial_value}"))
        
        # Add missing secrets
        for secret_name, env_var in secrets_missing:
            all_secrets.append((secret_name, env_var, "⚠️  Not set"))
        
        # Display unified secrets table
        if all_secrets:
            print(f"{'SECRET NAME':<20} {'ENV VARIABLE':<25} {'VALUE':<25}")
            print("-" * 74)
            for secret_name, env_var, status_value in all_secrets:
                print(f"{secret_name:<20} {env_var:<25} {status_value:<25}")
        
        print("=" * 74)
        print(f"📊 Environment: {config_env}")
        print(f"📊 Total secrets: {len(secrets_found)} configured, {len(secrets_missing)} missing")
        print("=" * 74 + "\n")
        
    except ImportError as e:
        print(f"⚠️  Could not load secrets manifest: {e}")
        print("=" * 74 + "\n")
    except Exception as e:
        print(f"⚠️  Error displaying secrets configuration: {e}")
        print("=" * 74 + "\n")





def _show_all_configuration_tables(config_env):
    """Show all 4 configuration tables consistently for both normal and --show-config runs."""
    # Table 1: TESTING CONFIGURATION is already shown by the decorator
    
    # Table 2: ENVIRONMENT VARIABLES (from loading.py)
    # This is already displayed by load_env() in loading.py
    
    # Table 3: SECRETS CONFIGURATION
    _show_secrets_configuration(config_env)