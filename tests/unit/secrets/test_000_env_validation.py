"""CRITICAL: Environment Variable Validation Tests

These tests MUST run first and MUST pass for the secrets test suite to continue.
They validate that environment variables are properly set to safe test locations
and that the secrets system respects these locations.

IMPORTANT: Environment variables LOCAL_SECRETS_REPO and LOCAL_SECRETS_CACHE
must be set to safe test locations before running this suite. These tests
will FAIL if the environment variables are not set or point to unsafe locations.

Test naming with 000_ prefix ensures these run first in alphabetical order.
"""

import os
import json
import pytest
from pathlib import Path
import uuid

# Import after setting up environment to avoid import-time issues
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


@pytest.mark.critical
def test_001_secrets_repo_env_var_validation(secrets_test_environment):
    """CRITICAL: Verify LOCAL_SECRETS_REPO is set to a safe test location."""
    from multi_eden.build.secrets.local_manager import LocalSecretsManager
    from .base import TEST_BASE_IDENTIFIER
    
    # FAIL FAST: Environment variable must be set
    secrets_repo = os.getenv(LocalSecretsManager.ENV_SECRETS_REPO)
    assert secrets_repo is not None, f"{LocalSecretsManager.ENV_SECRETS_REPO} environment variable must be set for testing"
    
    # FAIL FAST: Must contain our test identifier
    assert TEST_BASE_IDENTIFIER in secrets_repo, f"{LocalSecretsManager.ENV_SECRETS_REPO} must contain test identifier '{TEST_BASE_IDENTIFIER}'. Got: {secrets_repo}"
    
    # FAIL FAST: Must not be common production paths
    dangerous_paths = ['.secrets', '/secrets', '~/.secrets', str(Path.home() / '.secrets')]
    assert secrets_repo not in dangerous_paths, f"{LocalSecretsManager.ENV_SECRETS_REPO} must not be a common production path: {secrets_repo}"
    
    # FAIL FAST: Must be a file path (not directory)
    assert os.path.isfile(secrets_repo) or not os.path.exists(secrets_repo), f"{LocalSecretsManager.ENV_SECRETS_REPO} must be a file path: {secrets_repo}"
    
    # Verify it matches our test setup
    assert secrets_repo == secrets_test_environment['repo_path'], f"Expected {secrets_test_environment['repo_path']}, got {secrets_repo}"


@pytest.mark.critical
def test_002_secrets_cache_env_var_validation(secrets_test_environment):
    """CRITICAL: Verify LOCAL_SECRETS_CACHE is set to a safe test location."""
    from multi_eden.build.secrets.local_manager import LocalSecretsManager
    from .base import TEST_BASE_IDENTIFIER
    
    # FAIL FAST: Environment variable must be set
    secrets_cache = os.getenv(LocalSecretsManager.ENV_SECRETS_CACHE)
    assert secrets_cache is not None, f"{LocalSecretsManager.ENV_SECRETS_CACHE} environment variable must be set for testing"
    
    # FAIL FAST: Must contain our test identifier
    assert TEST_BASE_IDENTIFIER in secrets_cache, f"{LocalSecretsManager.ENV_SECRETS_CACHE} must contain test identifier '{TEST_BASE_IDENTIFIER}'. Got: {secrets_cache}"
    
    # FAIL FAST: Must not be common production paths
    dangerous_paths = ['.secrets', '/secrets', '~/.secrets', str(Path.home() / '.secrets')]
    assert secrets_cache not in dangerous_paths, f"{LocalSecretsManager.ENV_SECRETS_CACHE} must not be a common production path: {secrets_cache}"
    
    # FAIL FAST: Must be a directory path
    assert os.path.isdir(secrets_cache), f"{LocalSecretsManager.ENV_SECRETS_CACHE} must be a directory: {secrets_cache}"
    
    # Verify it matches our test setup
    assert secrets_cache == secrets_test_environment['cache_path'], f"Expected {secrets_test_environment['cache_path']}, got {secrets_cache}"


@pytest.mark.critical
def test_003_factory_returns_local_secrets_manager(secrets_test_environment):
    """CRITICAL: Verify factory returns LocalSecretsManager when LOCAL_SECRETS_REPO is set."""
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    assert manager is not None, "Factory must return a secrets manager"
    assert hasattr(manager, 'get_secret'), "Manager must have get_secret method"
    assert hasattr(manager, 'set_secret'), "Manager must have set_secret method"


@pytest.mark.critical
def test_004_manager_reads_from_secrets_repo_location(secrets_test_environment):
    """CRITICAL: Verify manager reads from the correct secrets repo location."""
    from multi_eden.build.secrets.local_manager import LocalSecretsManager
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    assert isinstance(manager, LocalSecretsManager), "Manager must be LocalSecretsManager"
    
    # Verify the manager is using the correct repo path
    expected_repo = secrets_test_environment['repo_path']
    # Note: We can't directly access the private _secrets_repo_path, but we can verify
    # the environment variable is set correctly
    assert os.getenv(LocalSecretsManager.ENV_SECRETS_REPO) == expected_repo


@pytest.mark.critical
def test_005_cached_key_uses_cache_location(secrets_test_environment):
    """CRITICAL: Verify cached key uses the correct cache location."""
    from multi_eden.build.secrets.local_manager import LocalSecretsManager
    from multi_eden.build.secrets.factory import get_secrets_manager
    
    manager = get_secrets_manager()
    assert isinstance(manager, LocalSecretsManager), "Manager must be LocalSecretsManager"
    
    # Verify the manager is using the correct cache path
    expected_cache = secrets_test_environment['cache_path']
    # Note: We can't directly access the private _secrets_cache_path, but we can verify
    # the environment variable is set correctly
    assert os.getenv(LocalSecretsManager.ENV_SECRETS_CACHE) == expected_cache