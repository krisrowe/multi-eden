"""
Test runner tasks for multi-env-sdk.

This module provides tasks for running different types of tests
with appropriate configuration and environment setup.
"""

import subprocess
import sys
from pathlib import Path
from invoke import task
from .config.setup import get_task_default_env
from .config.decorators import requires_config_env


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
    'test_name': 'Filter to specific test method(s) (e.g., "test_long_name_product" or "test_*")'
})
def test(ctx, suite, config_env=None, verbose=False, test_name=None):
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
    from .config.decorators import resolve_config_env
    
    # Create a callback that gets the suite-specific default
    def get_suite_env_callback(ctx, suite, **kwargs):
        return get_suite_default_env(suite)
    
    resolved_env = resolve_config_env(config_env, (suite,), {'verbose': verbose}, 'test', get_suite_env_callback)
    
    print(f"🧪 Running {suite} tests...")
    return run_pytest(suite, resolved_env, verbose, test_name)


def run_pytest(suite, config_env, verbose, test_name=None):
    """
    Run pytest with the specified suite and environment.
    
    Args:
        suite: Test suite name
        config_env: Configuration environment (optional)
        verbose: Whether to enable verbose output
        test_name: Optional test name filter (e.g., "test_long_name_product")
        
    Returns:
        subprocess.CompletedProcess: Result of pytest execution
    """
    # Get test paths from configuration
    test_paths = get_test_paths_from_config(suite)
    if not test_paths:
        print(f"⚠️  No test paths configured for suite '{suite}'")
        return None
    
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
    
    # Add test paths
    for path in test_paths:
        cmd.append(f"tests/{path}")
    
    print(f"🔍 Including pytest {' '.join(cmd[4:])}")
    
    # Run pytest
    print(f"🧪 Running {suite} tests...")
    result = subprocess.run(cmd, cwd=Path.cwd())
    
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
                print(f"📋 Moved providers path to FIRST position")
            else:
                print(f"📋 Providers path already in FIRST position")
        
        print(f"📋 Final test paths: {test_paths}")
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