"""
Pytest configuration for secrets tests.

Uses our config layering system to avoid environment pollution.
Creates isolated test directories per-test using fixtures.
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
    """Configure pytest for secrets testing."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "critical: mark test as critical - failure stops all testing"
    )


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


@pytest.fixture(scope="function")
def secrets_test_environment():
    """
    Create isolated test environment for each test.
    
    This fixture works with our config layering system:
    1. The pytest plugin calls load_env() which loads the 'unit' environment
    2. This fixture then overrides LOCAL_SECRETS_REPO and LOCAL_SECRETS_CACHE
       with test-specific temporary directories
    3. After the test, the temporary directories are cleaned up
    """
    # Create isolated test directories with our test identifier
    test_secrets_repo_dir = tempfile.mkdtemp(prefix=f'{TEST_BASE_IDENTIFIER}-{SECRETS_REPO_SUBDIR}-')
    test_secrets_cache = tempfile.mkdtemp(prefix=f'{TEST_BASE_IDENTIFIER}-{SECRETS_CACHE_SUBDIR}-')
    
    # Secrets repo should point to a file inside the repo directory
    test_secrets_repo = os.path.join(test_secrets_repo_dir, LocalSecretsManager.DEFAULT_SECRETS_FILENAME)
    
    # Store original environment variables for restoration
    original_secrets_repo = os.environ.get('LOCAL_SECRETS_REPO')
    original_secrets_cache = os.environ.get('LOCAL_SECRETS_CACHE')
    
    # Override environment variables for this test
    os.environ['LOCAL_SECRETS_REPO'] = test_secrets_repo
    os.environ['LOCAL_SECRETS_CACHE'] = test_secrets_cache
    
    # Store cleanup info
    test_setup = {
        'repo_path': test_secrets_repo,
        'repo_dir': test_secrets_repo_dir,
        'cache_path': test_secrets_cache,
        'original_secrets_repo': original_secrets_repo,
        'original_secrets_cache': original_secrets_cache
    }
    
    yield test_setup
    
    # Cleanup: Restore original environment variables
    if original_secrets_repo is not None:
        os.environ['LOCAL_SECRETS_REPO'] = original_secrets_repo
    elif 'LOCAL_SECRETS_REPO' in os.environ:
        del os.environ['LOCAL_SECRETS_REPO']
    
    if original_secrets_cache is not None:
        os.environ['LOCAL_SECRETS_CACHE'] = original_secrets_cache
    elif 'LOCAL_SECRETS_CACHE' in os.environ:
        del os.environ['LOCAL_SECRETS_CACHE']
    
    # Clean up temporary directories
    try:
        shutil.rmtree(test_secrets_repo_dir)
    except Exception as e:
        print(f"⚠️  Failed to clean up {test_secrets_repo_dir}: {e}")
    
    try:
        shutil.rmtree(test_secrets_cache)
    except Exception as e:
        print(f"⚠️  Failed to clean up {test_secrets_cache}: {e}")


def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    print("🔒 Starting secrets tests with config layering...")


def pytest_sessionfinish(session, exitstatus):
    """Called after whole test run finished."""
    if exitstatus == 0:
        print("✅ All secrets tests passed!")
    else:
        print(f"❌ Tests failed with exit status: {exitstatus}")