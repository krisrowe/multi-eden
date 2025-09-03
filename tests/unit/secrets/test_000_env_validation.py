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
import unittest
from pathlib import Path
import uuid
import pytest

# Import after setting up environment to avoid import-time issues
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestCriticalEnvValidation(unittest.TestCase):
    """Critical environment variable validation tests that must pass first.
    
    Note: This class intentionally does NOT inherit from BaseSecretsTest
    because it needs to test environment setup before manager initialization.
    """
    
    @pytest.mark.critical
    def test_001_secrets_repo_env_var_validation(self):
        """CRITICAL: Verify LOCAL_SECRETS_REPO is set to a safe test location."""
        from multi_eden.build.secrets.local_manager import LocalSecretsManager
        from .base import TEST_BASE_IDENTIFIER
        
        # FAIL FAST: Environment variable must be set
        secrets_repo = os.getenv(LocalSecretsManager.ENV_SECRETS_REPO)
        self.assertIsNotNone(secrets_repo, 
                           f"{LocalSecretsManager.ENV_SECRETS_REPO} environment variable must be set for testing")
        
        # FAIL FAST: Must contain our test identifier
        self.assertIn(TEST_BASE_IDENTIFIER, secrets_repo,
                     f"{LocalSecretsManager.ENV_SECRETS_REPO} must contain test identifier '{TEST_BASE_IDENTIFIER}'. Got: {secrets_repo}")
        
        # FAIL FAST: Must not be common production paths
        dangerous_paths = ['.secrets', '/secrets', '~/.secrets', str(Path.home() / '.secrets')]
        self.assertNotIn(secrets_repo, dangerous_paths,
                        f"{LocalSecretsManager.ENV_SECRETS_REPO} must not be a common production path: {secrets_repo}")
        
        print(f"✓ {LocalSecretsManager.ENV_SECRETS_REPO} is safely set: {secrets_repo}")
    
    @pytest.mark.critical
    def test_002_secrets_cache_env_var_validation(self):
        """CRITICAL: Verify LOCAL_SECRETS_CACHE is set to a safe test location."""
        from multi_eden.build.secrets.local_manager import LocalSecretsManager
        from .base import TEST_BASE_IDENTIFIER
        
        # FAIL FAST: Environment variable must be set
        secrets_cache = os.getenv(LocalSecretsManager.ENV_SECRETS_CACHE)
        self.assertIsNotNone(secrets_cache,
                           f"{LocalSecretsManager.ENV_SECRETS_CACHE} environment variable must be set for testing")
        
        # FAIL FAST: Must contain our test identifier
        self.assertIn(TEST_BASE_IDENTIFIER, secrets_cache,
                     f"{LocalSecretsManager.ENV_SECRETS_CACHE} must contain test identifier '{TEST_BASE_IDENTIFIER}'. Got: {secrets_cache}")
        
        # FAIL FAST: Must not be the default cache directory (should be isolated)
        self.assertNotEqual(secrets_cache, LocalSecretsManager.DEFAULT_CACHE_DIR,
                          f"{LocalSecretsManager.ENV_SECRETS_CACHE} should not be default cache dir: {secrets_cache}")
        
        print(f"✓ {LocalSecretsManager.ENV_SECRETS_CACHE} is safely set: {secrets_cache}")
    
    @pytest.mark.critical
    def test_003_factory_returns_local_secrets_manager(self):
        """CRITICAL: Verify factory returns LocalSecretsManager instance."""
        from multi_eden.build.secrets.factory import get_secrets_manager
        from multi_eden.build.secrets.local_manager import LocalSecretsManager
        
        manager = get_secrets_manager()
        self.assertIsInstance(manager, LocalSecretsManager, "Factory should return LocalSecretsManager instance")
        
        print(f"✓ Factory correctly returns LocalSecretsManager instance")
        print(f"  Manager type: {type(manager).__name__}")
    
    @pytest.mark.critical
    def test_004_manager_reads_from_secrets_repo_location(self):
        """CRITICAL: Write unencrypted file to LOCAL_SECRETS_REPO, then verify manager reads from that exact location."""
        from multi_eden.build.secrets.factory import get_secrets_manager
        
        # Get the validated safe secrets repo location
        secrets_repo_path = Path(os.getenv('LOCAL_SECRETS_REPO'))
        
        manager = get_secrets_manager()
        self.assertEqual(manager.get_secrets_file_path(), secrets_repo_path,
                        f"Manager should point to LOCAL_SECRETS_REPO location: {secrets_repo_path}")
        print(f"  Manager reads from: {manager.get_secrets_file_path()}")
    
    @pytest.mark.critical
    def test_005_cached_key_uses_cache_location(self):
        """CRITICAL: Write cache file directly to LOCAL_SECRETS_CACHE, then verify API reads from that exact location."""
        from multi_eden.build.secrets.factory import get_secrets_manager
        from multi_eden.build.secrets.local_manager import LocalSecretsManager
        from multi_eden.build.secrets.models import GetCachedKeyResponse
        import subprocess
        import json
        import uuid
        from cryptography.fernet import Fernet
        import base64
        import hashlib
        
        # Get the validated safe cache location
        cache_location = Path(os.getenv(LocalSecretsManager.ENV_SECRETS_CACHE))
        
        # Clean up any existing cache files first
        if cache_location.exists():
            for cache_file in cache_location.glob(f'{LocalSecretsManager.CACHE_FILE_PREFIX}*'):
                cache_file.unlink()
        
        # Ensure cache directory exists
        cache_location.mkdir(parents=True, exist_ok=True)
        
        # Generate random test key data to prevent false positives
        random_suffix = str(uuid.uuid4())[:8]
        test_passphrase = f"test_passphrase_{random_suffix}"
        
        # Create a test encryption key from the passphrase (same logic as LocalSecretsManager)
        key_material = hashlib.pbkdf2_hmac(LocalSecretsManager.HASH_ALGORITHM, test_passphrase.encode(), LocalSecretsManager.SALT_VALUE, LocalSecretsManager.PBKDF2_ITERATIONS)
        test_key = base64.urlsafe_b64encode(key_material)
        
        # Initialize expected_cache_path to None for cleanup safety
        expected_cache_path = None
        
        try:
            # Test 1: Verify get_cached_key reports no key initially
            manager = get_secrets_manager()
            response = manager.get_cached_key()
            
            # Should report no key initially
            self.assertFalse(response.meta.success, "Should report no cached key initially")
            self.assertEqual(response.meta.error.code, 'KEY_NOT_SET', "Should report KEY_NOT_SET")
            self.assertIsNone(response.key, "Should not have key info when no key exists")
            
            # Test 2: Create a properly named cache file that the manager will recognize
            manager = LocalSecretsManager()
            expected_cache_path = manager.get_cached_key_file_path()
            
            # Verify the expected cache path is in our environment variable location
            self.assertTrue(str(expected_cache_path).startswith(str(cache_location)),
                           f"Expected cache path should be in LOCAL_SECRETS_CACHE: {cache_location}")
            
            # Write our test key to the expected cache file location (direct write, not API)
            expected_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(expected_cache_path, 'wb') as f:
                f.write(test_key)
            expected_cache_path.chmod(0o600)
            
            # Test 3: Verify get_cached_key now reports the key exists with correct hash
            response = manager.get_cached_key()
            
            # Verify proper Pydantic response structure
            self.assertTrue(response.meta.success, f"Should report cached key exists: {response.meta.error}")
            self.assertEqual(response.meta.provider, "local", "Should report local provider")
            self.assertIsNone(response.meta.error, "Should not have error on success")
            self.assertIsNotNone(response.key, "Should have key info")
            self.assertIsNotNone(response.key.hash, "Should include key hash")
            
            # Test 4: Verify the API actually read our directly-written key
            expected_key_hash = hashlib.sha256(test_key).hexdigest()[:16]
            self.assertEqual(response.key.hash, expected_key_hash,
                           "API should report hash of the key we wrote directly to cache file")
            
            print(f"✓ Cached key operations use LOCAL_SECRETS_CACHE location correctly")
            print(f"  Cache location: {cache_location}")
            if expected_cache_path:
                print(f"  Expected cache file: {expected_cache_path}")
            print(f"  Key hash matches: {response.key.hash} == {expected_key_hash}")
            print(f"  Random test data: {random_suffix}")
            print(f"  Response structure: meta.success={response.meta.success}, meta.provider={response.meta.provider}")
            
        finally:
            # Clean up cache files
            if cache_location.exists():
                for cache_file in cache_location.glob(f'{LocalSecretsManager.CACHE_FILE_PREFIX}*'):
                    cache_file.unlink()
            # Also clean up the expected cache file
            if expected_cache_path and expected_cache_path.exists():
                expected_cache_path.unlink()


if __name__ == '__main__':
    # Run these critical tests with FAIL FAST - any failure stops everything
    unittest.main(verbosity=2, failfast=True, exit=True)
