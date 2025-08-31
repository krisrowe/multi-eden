"""
Test runner tasks for multi-env-sdk.

This module provides tasks for running different types of tests
with appropriate configuration and environment setup.
"""

import subprocess
import sys
from pathlib import Path
from invoke import task
from multi_eden.build.tasks.config.setup import get_task_default_env
from multi_eden.build.tasks.config.decorators import requires_config_env
import os
import logging

logger = logging.getLogger(__name__)


def get_suite_default_env(suite):
    """
    Get the default environment for a specific test suite.
    
    Args:
        suite: Test suite name (unit, ai, firestore, api)
        
    Returns:
        str: Environment name for the suite, or None if not found
    """
    # Use SDK's config system to get suite default environment
    from multi_eden.run.config.testing import get_mode
    try:
        mode_config = get_mode(suite)
        return mode_config.default_env
    except Exception:
        return None


def should_omit_integration_tests(suite):
    """
    Check if integration tests should be omitted for the given suite.
    
    Args:
        suite: Test suite name (unit, integration, firestore, api)
        
    Returns:
        bool: True if integration tests should be omitted
    """
    # Use SDK's config system to check omit-integration setting
    from multi_eden.run.config.testing import get_mode
    try:
        mode_config = get_mode(suite)
        return getattr(mode_config, 'omit_integration', False)
    except Exception:
        return False


@task(help={
    'suite': 'Test suite to run (unit, ai, firestore, api)',
    'config_env': 'Configuration environment to use (overrides suite default)',
    'verbose': 'Enable verbose output',
    'test_name': 'Filter to specific test method(s) (e.g., "test_long_name_product" or "test_*")',
    'show_config': 'Show detailed configuration including partial secret values',
    'quiet': 'Suppress configuration display (show only test results)'
})
def test(ctx, suite, config_env=None, verbose=False, test_name=None, show_config=False, quiet=False):
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
    
    # Use the helper method to resolve the environment
    from multi_eden.build.tasks.config.decorators import resolve_config_env
    
    # Create a callback that gets the suite-specific default
    def get_suite_env_callback(ctx, suite, **kwargs):
        return get_suite_default_env(suite)
    
    resolved_env = resolve_config_env(config_env, (suite,), {'verbose': verbose, 'quiet': quiet}, 'test', get_suite_env_callback, quiet)
    
    return run_pytest(suite, resolved_env, verbose, test_name, show_config)


def run_pytest(suite, config_env, verbose, test_name=None, show_config=False):
    """
    Run pytest with the specified suite and environment.
    
    Args:
        suite: Test suite name
        config_env: Configuration environment (optional)
        verbose: Whether to enable verbose output
        test_name: Optional test name filter (e.g., "test_long_name_product")
        show_config: Whether to show detailed configuration including secrets
        
    Returns:
        subprocess.CompletedProcess: Result of pytest execution
    """
    # Get test paths from configuration
    test_paths = get_test_paths_from_config(suite)
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
                from ...run.config import print_runtime_config
                print_runtime_config()
                print("📊 Configuration display complete. Exiting without running tests.")
                return None
                
        except Exception as e:
            print(f"⚠️  Could not load configuration for environment '{config_env}': {e}")
            if show_config:
                return None
    
    # Use current environment variables (set by load_env)
    env_vars = os.environ.copy()
    
    # Use the virtual environment's pytest directly (same as Makefile)
    venv_pytest = Path.cwd() / "venv" / "bin" / "pytest"
    if venv_pytest.exists():
        pytest_executable = str(venv_pytest)
        print(f"🐍 Using virtual environment pytest: {pytest_executable}")
    else:
        pytest_executable = "python"
        print(f"🐍 Using system pytest: {pytest_executable}")
    
    # Build pytest command
    if pytest_executable != "python":
        cmd = [pytest_executable]
    else:
        cmd = [pytest_executable, "-m", "pytest"]
    
    cmd.extend([
        "--tb=short",
        "--strict-markers",
        "--suite", suite
    ])
    
    # Filter out integration tests if omit-integration is true
    if should_omit_integration_tests(suite):
        cmd.extend(["-m", "not integration"])
        print(f"🔒 Filtering out integration tests for {suite} test suite (omit-integration: true)")
    
    if config_env:
        cmd.extend(["--config-env", config_env])
    
    if verbose:
        cmd.append("-v")
    
    # Add test name filter if specified
    if test_name:
        cmd.extend(["-k", test_name])
        print(f"🎯 Filtering tests by name: {test_name}")
    
    # Add test paths (filter out non-existent ones)
    logger = logging.getLogger(__name__)
    valid_test_paths = []
    for path in test_paths:
        test_path = Path.cwd() / "tests" / path
        if test_path.exists():
            valid_test_paths.append(f"tests/{path}")
        else:
            logger.debug(f"Test path not found, skipping: tests/{path}")
    
    if not valid_test_paths:
        print(f"❌ No valid test paths found for suite '{suite}'")
        return None
    
    cmd.extend(valid_test_paths)
    
    print(f"🔍 Including pytest {' '.join(cmd[4:])}")    
    
    # Show runtime configuration that tests will use
    from ...run.config import print_runtime_config
    print_runtime_config()
    
    # Run pytest with environment variables
    print(f"🧪 Running {suite} tests...")
    
    result = subprocess.run(cmd, cwd=Path.cwd(), env=env_vars)
    
    if result.returncode == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ Tests failed with exit code {result.returncode}")
    
    return result

def get_test_paths_from_config(suite):
    """
    Get test paths for a specific suite from configuration.
    
    Args:
        suite: Test suite name
        
    Returns:
        list: List of test path strings, or None if not found
    """
    # Use SDK's config system to get test paths
    from multi_eden.run.config.testing import get_mode
    try:
        mode_config = get_mode(suite)
        test_paths = mode_config.get_test_paths().copy()  # Make a copy to modify
        
        # If providers is already in the list, ensure it runs FIRST by putting it at the beginning
        if 'providers' in test_paths:
            if test_paths.index('providers') != 0:
                # If providers is already in the list but not first, move it to first
                test_paths.remove('providers')
                test_paths.insert(0, 'providers')
                pass  # Providers moved to first position
            else:
                pass  # Providers already in first position
        return test_paths
    except Exception as e:
        print(f"⚠️  Could not load test configuration for suite '{suite}': {e}")
        return None


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
        suite_env = get_suite_default_env(suite)
        if suite_env:
            print(f"🌍 Suite default environment: {suite_env}")
        else:
            print("⚠️  No default environment configured for this suite")
    
    # Show pytest command that would be run
    cmd = ["python", "-m", "pytest", "--suite", suite]
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
        config_env: Configuration environment name
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
    try:
        # Table 1: TESTING CONFIGURATION is already shown by the decorator
        
        # Table 2: ENVIRONMENT VARIABLES (from loading.py)
        # This is already displayed by load_env() in loading.py
        
        # Table 3: SECRETS CONFIGURATION
        _show_secrets_configuration(config_env)
        
    except Exception as e:
        print(f"⚠️  Could not display configuration tables: {e}")
        print()