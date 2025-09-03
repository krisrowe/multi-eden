import unittest
import uuid
from multi_eden.build.secrets.local_manager import LocalSecretsManager
from .base import BaseSecretsTest


class TestSecretAccess(BaseSecretsTest):
    """Test secret operations (get, list, set, clear) with various key states."""
    
    def test_secrets_set_success(self):
        """Test successful secret setting with valid cached key."""
        # Set up cached key
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success, f"Failed to set cached key: {key_response.meta.error}")
        
        # Set a secret
        result = self.manager.set_secret("test-secret", "test-value")
        
        # Verify response structure
        self.assertTrue(result.meta.success)
        self.assertEqual(result.secret.name, "test-secret")
    
    def test_secrets_get_success_hash_only(self):
        """Test successful secret retrieval with hash only (show=False by default)."""
        # Generate unique test data
        secret_name = f"test-secret-{uuid.uuid4().hex[:8]}"
        secret_value = f"test-value-{uuid.uuid4().hex[:8]}"
        
        # Set up cached key and secret
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret(secret_name, secret_value)
        self.assertTrue(set_response.meta.success)
        
        # Get secret (hash by default)
        result = self.manager.get_secret(secret_name)
        
        # Should succeed with hash only
        self.assertTrue(result.meta.success, f"Failed to get secret: {result.meta.error}")
        self.assertEqual(result.meta.provider, "local")
        self.assertEqual(result.secret.name, secret_name)
        expected_hash = self.get_expected_secret_hash(secret_value)
        self.assertEqual(result.secret.hash, expected_hash)
        self.assertIsNone(result.secret.value)  # Value not shown by default
    
    def test_secrets_get_success_with_value(self):
        """Test successful secret retrieval with actual value (show=True)."""
        # Generate unique test data
        secret_name = f"test-secret-{uuid.uuid4().hex[:8]}"
        secret_value = f"test-value-{uuid.uuid4().hex[:8]}"
        
        # Set up cached key and secret
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret(secret_name, secret_value)
        self.assertTrue(set_response.meta.success)
        
        # Get secret with show=True
        result = self.manager.get_secret(secret_name, show=True)
        
        # Should succeed with actual value
        self.assertTrue(result.meta.success, f"Failed to get secret with show: {result.meta.error}")
        self.assertEqual(result.meta.provider, "local")
        self.assertEqual(result.secret.name, secret_name)
        self.assertEqual(result.secret.value, secret_value)
        expected_hash = self.get_expected_secret_hash(secret_value)
        self.assertEqual(result.secret.hash, expected_hash)
    
    def test_secrets_list_success(self):
        """Test successful secrets listing with valid cached key."""
        # Set up cached key and multiple secrets
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        self.manager.set_secret("secret1", "value1")
        self.manager.set_secret("secret2", "value2")
        self.manager.set_secret("secret3", "value3")
        
        # List secrets
        result = self.manager.list_secrets()
        
        # Should succeed with all secrets listed
        self.assertTrue(result.meta.success, f"Failed to list secrets: {result.meta.error}")
        self.assertEqual(result.meta.provider, "local")
        self.assertEqual(len(result.manifest.secrets), 3)
        
        # Verify secret names (should be sorted)
        secret_names = [s.name for s in result.manifest.secrets]
        self.assertEqual(secret_names, ["secret1", "secret2", "secret3"])
    
    def test_secrets_get_not_found(self):
        """Test getting a non-existent secret when secrets exist but specific secret not found."""
        # Clear files first
        self._cleanup_test_files()
        
        # Set up cached key
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        # Set secret X
        set_response = self.manager.set_secret("secret-x", "value-x")
        self.assertTrue(set_response.meta.success)
        
        # Get secret X and assert success
        get_x_result = self.manager.get_secret("secret-x")
        self.assertTrue(get_x_result.meta.success)
        
        # Try to get secret Y (non-existent)
        get_y_result = self.manager.get_secret("secret-y")
        
        # Should fail with SECRET_NOT_FOUND
        self.assertFalse(get_y_result.meta.success)
        self.assertEqual(get_y_result.meta.error.code, "SECRET_NOT_FOUND")
    
    def test_secrets_list_empty(self):
        """Test listing secrets when no secrets exist, then confirm with one secret."""
        # Set up cached key but no secrets
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        # List secrets - should be empty
        result = self.manager.list_secrets()
        
        # Should succeed with empty list
        self.assertTrue(result.meta.success, f"Failed to list empty secrets: {result.meta.error}")
        self.assertEqual(result.meta.provider, "local")
        self.assertEqual(len(result.manifest.secrets), 0)  # Confirm empty state
        
        # Add one secret to confirm the empty result was accurate, not coincidental
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # List again - should now have exactly one secret
        result2 = self.manager.list_secrets()
        self.assertTrue(result2.meta.success)
        self.assertEqual(len(result2.manifest.secrets), 1)  # Confirm list functionality works
    
    def test_secrets_get_invalid_cached_key(self):
        """Test getting secret when cached key is invalid for existing secrets."""
        # Set up valid key and secret
        key_response = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Corrupt the cached key by direct file write (manager would block corruption)
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())
        
        # Write corrupted key data directly to file
        with open(key_file, 'wb') as f:
            f.write(b'corrupted_key_data_that_is_wrong')
        
        # Try to get secret with corrupted key
        result = self.manager.get_secret("test-secret")
        
        # Should fail with KEY_INVALID
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_INVALID")
        self.assertIn("invalid", result.meta.error.message.lower())
    
    def test_secrets_set_invalid_cached_key(self):
        """Test setting secret when cached key is invalid for existing secrets."""
        # Set up valid key and secret
        key_response = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("existing-secret", "existing-value")
        self.assertTrue(set_response.meta.success)
        
        # Corrupt the cached key by direct file write (manager would block corruption)
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())
        
        # Write corrupted key data directly to file
        with open(key_file, 'wb') as f:
            f.write(b'corrupted_key_data_that_is_wrong')
        
        # Try to set new secret with corrupted key
        result = self.manager.set_secret("new-secret", "new-value")
        
        # Should fail with KEY_INVALID
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_INVALID")
        self.assertIn("invalid", result.meta.error.message.lower())
    
    def test_secrets_list_invalid_cached_key(self):
        """Test listing secrets when cached key is invalid for existing secrets."""
        # Set up valid key and secret
        key_response = self.manager.set_cached_key("correct-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Corrupt the cached key by direct file write (manager would block corruption)
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())
        
        # Write corrupted key data directly to file
        with open(key_file, 'wb') as f:
            f.write(b'corrupted_key_data_that_is_wrong')
        
        # Try to list secrets with corrupted key
        result = self.manager.list_secrets()
        
        # Should fail with KEY_INVALID
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_INVALID")
        self.assertIn("invalid", result.meta.error.message.lower())
    
    def test_secrets_clear(self):
        """Test clearing secrets and verify impact via get/list operations before and after."""
        # Step 1: Set up secrets
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        self.manager.set_secret("secret1", "value1")
        self.manager.set_secret("secret2", "value2")
        
        # Step 2: Verify secrets exist before clear
        list_before = self.manager.list_secrets()
        self.assertTrue(list_before.meta.success)
        self.assertEqual(len(list_before.manifest.secrets), 2)
        
        get_before = self.manager.get_secret("secret1", show=True)
        self.assertTrue(get_before.meta.success)
        self.assertEqual(get_before.secret.value, "value1")
        
        # Step 3: Clear secrets
        clear_result = self.manager.clear_all_secrets()
        self.assertTrue(clear_result.meta.success)
        self.assertIn("cleared", clear_result.message.lower())
        
        # Step 4: Verify secrets are gone after clear
        list_after = self.manager.list_secrets()
        self.assertTrue(list_after.meta.success)
        self.assertEqual(len(list_after.manifest.secrets), 0)
        
        get_after = self.manager.get_secret("secret1")
        self.assertFalse(get_after.meta.success)
        self.assertEqual(get_after.meta.error.code, "SECRET_NOT_FOUND")
        
        # Step 5: Verify cached key still works for new secrets
        new_set = self.manager.set_secret("new-secret", "new-value")
        self.assertTrue(new_set.meta.success)
        
        new_get = self.manager.get_secret("new-secret", show=True)
        self.assertTrue(new_get.meta.success)
        self.assertEqual(new_get.secret.value, "new-value")
    
    def test_no_secrets_no_key(self):
        """Test KEY_NOT_SET error when no secrets file exists and no cached key."""
        # Step 1: Run cleanup and verify both files are gone
        self._cleanup_test_files()
        self.assertFalse(self.manager.get_secrets_file_path().exists())
        self.assertFalse(self.manager.get_cached_key_file_path().exists())
        
        # Step 2: Try to access a secret without a key - should get KEY_NOT_SET
        get_result = self.manager.get_secret("nonexistent-secret")
        self.assertFalse(get_result.meta.success)
        self.assertEqual(get_result.meta.error.code, "KEY_NOT_SET")
    
    def test_operations_without_cached_key(self):
        """Test KEY_NOT_SET vs SECRET_NOT_FOUND scenarios with proper setup."""
        # Step 1: Start clean, try to get secret without key - should get KEY_NOT_SET
        self._cleanup_test_files()
        get_result1 = self.manager.get_secret("test-secret")
        self.assertFalse(get_result1.meta.success)
        self.assertEqual(get_result1.meta.error.code, "KEY_NOT_SET")
        
        # Step 2: Set key and secret, validate get works
        key_response = self.manager.set_cached_key("test-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        get_result2 = self.manager.get_secret("test-secret")
        self.assertTrue(get_result2.meta.success)
        
        # Step 3: Delete just the key file (not secrets file)
        key_file = self.manager.get_cached_key_file_path()
        if key_file.exists():
            key_file.unlink()
        
        # Step 4: Try to get same secret again - should get KEY_NOT_SET (secret exists but no key)
        get_result3 = self.manager.get_secret("test-secret")
        self.assertFalse(get_result3.meta.success)
        self.assertEqual(get_result3.meta.error.code, "KEY_NOT_SET")
        
        # Test list without cached key
        list_result = self.manager.list_secrets()
        self.assertFalse(list_result.meta.success)
        self.assertEqual(list_result.meta.error.code, "KEY_NOT_SET")
        
        # Test set without cached key
        set_result = self.manager.set_secret("another-secret", "another-value")
        self.assertFalse(set_result.meta.success)
        self.assertEqual(set_result.meta.error.code, "KEY_NOT_SET")
    
if __name__ == "__main__":
    unittest.main()
