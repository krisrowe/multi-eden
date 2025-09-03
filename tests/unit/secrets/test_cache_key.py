import unittest
from pathlib import Path

from multi_eden.build.secrets.local_manager import LocalSecretsManager
from .base import BaseSecretsTest

# Make sure all these are tested:
# - CACHE_KEY_VALID_SET: Sets /tmp-cached key via passphrase valid for existing .secrets file when no /tmp-cached key present
# - CACHE_KEY_VALID_CHANGE: Sets cached key to valid one while existing /tmp-cached key doesn't match .secrets file
# - CACHE_KEY_INVALID: New key is wrong for .secrets file (doesn't matter if existing /tmp-cached key is valid)
# - CACHE_KEY_NEW: No .secrets file exists locally
# - CACHE_KEY_NO_CHANGE: Passphrase converts to key matching existing in /tmp (no validation against .secrets needed)
# These have test methods:
# - CACHE_KEY_VALID_SET: test_cached_key_expired_recovery
# - CACHE_KEY_VALID_CHANGE: test_cached_key_invalid_recovery
# - CACHE_KEY_INVALID: test_cache_key_rejected
# - CACHE_KEY_NEW: test_cache_key_new
# - CACHE_KEY_NO_CHANGE: test_cache_key_no_change
class TestCacheKey(BaseSecretsTest):
    """Test the set-cached-key command with detailed response codes."""
    
    def test_cache_key_new(self):
        """Test comprehensive CACHE_KEY_NEW behavior and transitions.
        
        This test verifies the complete lifecycle of CACHE_KEY_NEW scenarios
        and transitions to other response codes based on file states.
        """
        # Step 1: Verify neither secrets file nor key file exists
        self._cleanup_test_files()
        self.assertFalse(self.manager.get_secrets_file_path().exists())
        self.assertFalse(self.manager.get_cached_key_file_path().exists())
        
        # Step 2: Set cached key and verify CACHE_KEY_NEW + key file exists but not secrets file
        result = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(result.meta.success)
        self.assertEqual(result.code, "CACHE_KEY_NEW")
        self.assertIsNotNone(result.key.hash)
        
        self.assertTrue(self.manager.get_cached_key_file_path().exists())  # Key file exists
        self.assertFalse(self.manager.get_secrets_file_path().exists())  # Secrets file does not exist
        
        # Step 3: Set a secret, verify both key and secrets file exist
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        self.assertTrue(self.manager.get_cached_key_file_path().exists())  # Key file still exists
        self.assertTrue(self.manager.get_secrets_file_path().exists())  # Secrets file now exists
        
        # Step 4: Set cache key again with same passphrase and see NO_CHANGE
        no_change_result = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(no_change_result.meta.success)
        self.assertEqual(no_change_result.code, "CACHE_KEY_NO_CHANGE")
        
        # Step 5: Run cleanup and verify neither key file nor secrets file exists
        self._cleanup_test_files()
        self.assertFalse(self.manager.get_cached_key_file_path().exists())  # No key file
        self.assertFalse(self.manager.get_secrets_file_path().exists())  # No secrets file
        
        # Step 6: Set cached key again to same and assert CACHE_KEY_NEW + key exists but not secrets
        new_result = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(new_result.meta.success)
        self.assertEqual(new_result.code, "CACHE_KEY_NEW")
        
        self.assertTrue(self.manager.get_cached_key_file_path().exists())  # Key file exists
        self.assertFalse(self.manager.get_secrets_file_path().exists())  # Secrets file does not exist
        
        # Step 7: Set cached key again with same passphrase while no secrets file present
        # Should be NO_CHANGE since key already cached and no secrets file to validate against
        no_change_result2 = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(no_change_result2.meta.success)
        self.assertEqual(no_change_result2.code, "CACHE_KEY_NO_CHANGE")
        
        self.assertTrue(self.manager.get_cached_key_file_path().exists())  # Key file exists
        self.assertFalse(self.manager.get_secrets_file_path().exists())  # Secrets file still does not exist
    
    def test_cached_key_expired_recovery(self):
        """Test setting cached key via passphrase valid for existing .secrets file
        when no /tmp-cached key is present.
        
        This test simulates OS cleanup scenarios where the cached key file gets
        removed but the secrets file remains. It verifies that set_cached_key
        can recover by validating against the existing secrets file.
        """
        # Step 1: Create a secrets file by setting up key and storing a secret
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        original_key_hash = key_response.key.hash  # Store original key hash for comparison
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Step 2: Establish baseline - same passphrase should return NO_CHANGE
        no_change_result = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(no_change_result.meta.success)
        self.assertEqual(no_change_result.code, "CACHE_KEY_NO_CHANGE")
        self.assertEqual(no_change_result.key.hash, original_key_hash)  # Same key hash
        
        # Step 3: Simulate OS cleanup - remove cached key file
        # This can happen during system reboots, /tmp cleanup, or container restarts
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())  # Verify we have a cache file
        key_file.unlink()
        
        # Step 4: Set cached key with same passphrase after OS cleanup
        result = self.manager.set_cached_key("original-passphrase")
        
        # Should succeed with CACHE_KEY_VALID_SET code (not NO_CHANGE)
        # because the cached key is missing but passphrase validates against secrets file
        self.assertTrue(result.meta.success)
        self.assertEqual(result.code, "CACHE_KEY_VALID_SET")
        self.assertIsNotNone(result.key.hash)
        
        # Verify the recovered key hash matches the original
        # Same passphrase should always derive the same key hash
        self.assertEqual(result.key.hash, original_key_hash)
        
        # Step 5: Verify cached key can be read and has correct hash
        cached_key_result = self.manager.get_cached_key()
        self.assertTrue(cached_key_result.meta.success)
        self.assertEqual(cached_key_result.key.hash, original_key_hash)
        
        # Verify we can still access the secret
        secret_result = self.manager.get_secret("test-secret", show=True)
        self.assertTrue(secret_result.meta.success)
        self.assertEqual(secret_result.secret.value, "test-value")
    
    def test_cached_key_invalid_recovery(self):
        """Test recovery from corrupted cached key file.
        
        This test manually corrupts the cached key file and verifies that
        set_cached_key can recover with CACHE_KEY_VALID_CHANGE response.
        """
        # Step 1: Set cached key and save first secret
        key_response = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Step 2: Get secret to verify it works
        get_result1 = self.manager.get_secret("test-secret", show=True)
        self.assertTrue(get_result1.meta.success)
        self.assertEqual(get_result1.secret.value, "test-value")
        
        # Step 3: Manually corrupt the cached key file
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())
        
        # Write corrupted key data
        with open(key_file, 'wb') as f:
            f.write(b'corrupted_key_data_that_is_wrong')
        
        # Step 4: Try to get secret again, expect key mismatch error
        get_result2 = self.manager.get_secret("test-secret")
        self.assertFalse(get_result2.meta.success)
        self.assertEqual(get_result2.meta.error.code, "KEY_INVALID")
        
        # Step 5: Call set_cached_key with correct passphrase, expect CACHE_KEY_VALID_CHANGE
        recovery_result = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(recovery_result.meta.success)
        self.assertEqual(recovery_result.code, "CACHE_KEY_VALID_CHANGE")
        
        # Conclude by successfully reading secret again
        get_result3 = self.manager.get_secret("test-secret", show=True)
        self.assertTrue(get_result3.meta.success)
        self.assertEqual(get_result3.secret.value, "test-value")
    
    def test_cache_key_rejected(self):
        """Test setting cached key with passphrase that's wrong for .secrets file.
        
        This test verifies that when a different passphrase is provided that
        cannot decrypt the existing .secrets file, it returns CACHE_KEY_INVALID error.
        Note: It doesn't matter if existing /tmp-cached key is valid or not,
        as we don't check that during this operation.
        """
        # Step 1: Create secrets file with known passphrase
        key_response = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Step 2: Try to set cached key with wrong passphrase
        result = self.manager.set_cached_key("wrong-passphrase")
        
        # Should fail with CACHE_KEY_INVALID error code
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_INVALID")
        self.assertIn("cannot decrypt", result.meta.error.message)
    
    def test_cache_key_no_change(self):
        """Test setting cached key where passphrase converts to key matching existing in /tmp.
        
        This test verifies that when the same passphrase is provided that results
        in the same key already cached in /tmp, it returns CACHE_KEY_VALID_NO_CHANGE.
        This does not attempt to validate the key against the .secrets file since
        no change to /tmp is needed.
        """
        # Step 1: Set initial cached key
        result1 = self.manager.set_cached_key("same-passphrase")
        self.assertTrue(result1.meta.success)
        initial_hash = result1.key.hash
        
        # Step 2: Set cached key again with same passphrase
        result2 = self.manager.set_cached_key("same-passphrase")
        
        # Should succeed with CACHE_KEY_NO_CHANGE code
        self.assertTrue(result2.meta.success)
        self.assertEqual(result2.code, "CACHE_KEY_NO_CHANGE")
        self.assertEqual(result2.key.hash, initial_hash)  # Hash should be identical
        
        # Step 3: Verify this works even with secrets file present
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Step 4: Set cached key again with same passphrase
        result3 = self.manager.set_cached_key("same-passphrase")
        
        # Should still return NO_CHANGE without validating against secrets file
        self.assertTrue(result3.meta.success)
        self.assertEqual(result3.code, "CACHE_KEY_NO_CHANGE")
        self.assertEqual(result3.key.hash, initial_hash)
    
    def test_cache_key_response_structure(self):
        """Test that all cache key responses follow expected JSON structure."""
        
        # Test successful response structure
        result = self.manager.set_cached_key("test-passphrase")
        
        # Should have success, code, and hash
        self.assertIsNotNone(result.meta)
        self.assertIsNotNone(result.code)
        self.assertIsNotNone(result.key.hash)
        self.assertIsInstance(result.key.hash, str)
        self.assertEqual(len(result.key.hash), 16)  # SHA256 hash truncated to 16 chars
        
        # Test error response structure
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        error_result = self.manager.set_cached_key("wrong-passphrase")
        
        # Should have success=false and error with code and message
        self.assertFalse(error_result.meta.success)
        self.assertIsNotNone(error_result.meta.error)
        self.assertIsNotNone(error_result.meta.error.code)
        self.assertIsNotNone(error_result.meta.error.message)


if __name__ == "__main__":
    unittest.main()
