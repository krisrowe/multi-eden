"""
Pytest configuration for secrets tests.

Ensures critical environment variable validation tests run first and fail fast.
Implements strict sandboxing with resilient cleanup of temporary test environments.
"""

import os
import sys
import tempfile
import pytest
import shutil
from pathlib import Path
from .base import TEST_BASE_IDENTIFIER, SECRETS_REPO_SUBDIR, SECRETS_CACHE_SUBDIR
from multi_eden.build.secrets.local_manager import LocalSecretsManager


def pytest_configure(config):
    """Configure pytest for secrets testing with strict sandboxing."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "critical: mark test as critical - failure stops all testing"
    )
    
    # STRICT SANDBOXING: Fail if environment variables are already set
    # This ensures we don't accidentally contaminate real secrets during testing
    if os.getenv('LOCAL_SECRETS_REPO'):
        pytest.exit(
            f"LOCAL_SECRETS_REPO is already set to '{os.getenv('LOCAL_SECRETS_REPO')}'. "
            "Secrets tests require a clean environment for safety. "
            "Please unset this variable before running secrets tests.",
            returncode=1
        )
    
    if os.getenv('LOCAL_SECRETS_CACHE'):
        pytest.exit(
            f"LOCAL_SECRETS_CACHE is already set to '{os.getenv('LOCAL_SECRETS_CACHE')}'. "
            "Secrets tests require a clean environment for safety. "
            "Please unset this variable before running secrets tests.",
            returncode=1
        )
    
    # Create isolated test directories with our test identifier
    test_secrets_repo_dir = tempfile.mkdtemp(prefix=f'{TEST_BASE_IDENTIFIER}-{SECRETS_REPO_SUBDIR}-')
    test_secrets_cache = tempfile.mkdtemp(prefix=f'{TEST_BASE_IDENTIFIER}-{SECRETS_CACHE_SUBDIR}-')
    
    # Secrets repo should point to a file inside the repo directory
    test_secrets_repo = os.path.join(test_secrets_repo_dir, LocalSecretsManager.DEFAULT_SECRETS_FILENAME)
    
    # Set environment variables for this test session
    os.environ['LOCAL_SECRETS_REPO'] = test_secrets_repo
    os.environ['LOCAL_SECRETS_CACHE'] = test_secrets_cache
    
    # Store original state for cleanup
    config._secrets_test_setup = {
        'repo_path': test_secrets_repo,
        'repo_dir': test_secrets_repo_dir,  # Store dir for cleanup
        'cache_path': test_secrets_cache
    }
    
    print(f"🔒 STRICT SANDBOXING: Created isolated test environment")
    print(f"  LOCAL_SECRETS_REPO: {test_secrets_repo}")
    print(f"  LOCAL_SECRETS_CACHE: {test_secrets_cache}")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to ensure critical tests run first."""
    # Sort items so that critical tests run first
    critical_tests = []
    other_tests = []
    
    for item in items:
        # Check if test has the 'critical' marker
        if item.get_closest_marker('critical'):
            critical_tests.append(item)
        else:
            other_tests.append(item)
    
    # Critical tests first, then others
    items[:] = critical_tests + other_tests


def pytest_runtest_makereport(item, call):
    """Make test reports and fail fast on critical test failures."""
    # Check for critical test failures in any phase (setup, call, teardown)
    if call.excinfo is not None:
        # Check if this test has the 'critical' marker
        if item.get_closest_marker('critical'):
            # Critical test failed - exit immediately
            print(f"\n❌ CRITICAL TEST FAILED: {item.name}")
            print("Critical test failure - stopping all tests for safety")
            print(f"Failure in phase: {call.when}")
            print(f"Exception: {call.excinfo.value}")
            pytest.exit("Critical test failed", returncode=1)


def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    print("🔒 Starting secrets tests with strict sandboxing...")


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    # RESILIENT CLEANUP: Always clean up, regardless of test outcome
    if hasattr(session.config, '_secrets_test_setup'):
        secrets_test_setup = session.config._secrets_test_setup
        
        # Clean up temporary directories
        if secrets_test_setup['repo_dir']:
            try:
                shutil.rmtree(secrets_test_setup['repo_dir'])
                print(f"🧹 Cleaned up test secrets repo dir: {secrets_test_setup['repo_dir']}")
            except Exception as e:
                print(f"⚠️  Failed to clean up {secrets_test_setup['repo_dir']}: {e}")
        
        if secrets_test_setup['cache_path']:
            try:
                shutil.rmtree(secrets_test_setup['cache_path'])
                print(f"🧹 Cleaned up test secrets cache: {secrets_test_setup['cache_path']}")
            except Exception as e:
                print(f"⚠️  Failed to clean up {secrets_test_setup['cache_path']}: {e}")
        
        # Clean up environment variables (restore original state)
        try:
            if 'LOCAL_SECRETS_REPO' in os.environ:
                del os.environ['LOCAL_SECRETS_REPO']
                print("🧹 Unset LOCAL_SECRETS_REPO")
        except Exception as e:
            print(f"⚠️  Failed to unset LOCAL_SECRETS_REPO: {e}")
        
        try:
            if 'LOCAL_SECRETS_CACHE' in os.environ:
                del os.environ['LOCAL_SECRETS_CACHE']
                print("🧹 Unset LOCAL_SECRETS_CACHE")
        except Exception as e:
            print(f"⚠️  Failed to unset LOCAL_SECRETS_CACHE: {e}")
    
    if exitstatus == 0:
        print("✅ All secrets tests passed!")
    else:
        print(f"❌ Tests failed with exit status: {exitstatus}")
