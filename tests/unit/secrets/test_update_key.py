import unittest
from pathlib import Path

from multi_eden.build.secrets.local_manager import LocalSecretsManager
from .base import BaseSecretsTest


class TestUpdateKey(BaseSecretsTest):
    """Test the update-key command functionality."""
    
    def test_update_key_no_cached_key(self):
        """Test update-key command when no cached key is present.
        
        This test verifies that update-key fails with NO_CACHED_KEY error
        when there's no cached key in /tmp to use for decryption.
        Expected: success: false
        """
        # Ensure no cached key exists
        self._cleanup_test_files()
        
        # Try to update key without any cached key
        result = self.manager.update_encryption_key("new-passphrase")
        
        # Should fail with NO_CACHED_KEY error
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_NOT_SET")
        self.assertIn("No cached key found", result.meta.error.message)
        self.assertIn("set-cached-key", result.meta.error.message)
    
    def test_update_key_cached_key_valid(self):
        """Test update-key command with valid cached key.
        
        This test sets up a valid cached key with secrets, then updates
        the key to a new passphrase. All secrets should remain accessible
        with the new passphrase.
        Expected: success: true
        """
        # Step 1: Set up initial key and secrets
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response1 = self.manager.set_secret("secret1", "value1")
        self.assertTrue(set_response1.meta.success)
        
        set_response2 = self.manager.set_secret("secret2", "value2")
        self.assertTrue(set_response2.meta.success)
        
        # Verify initial setup works
        result = self.manager.get_secret("secret1", show=True)
        self.assertEqual(result.secret.value, "value1")
        
        # Step 2: Update key to new passphrase
        update_result = self.manager.update_encryption_key("new-passphrase")
        
        # Verify response structure
        self.assertTrue(update_result.meta.success)
        self.assertIsNotNone(update_result.key.hash)
        
        # Step 3: Verify secrets are still accessible with new key
        result1 = self.manager.get_secret("secret1", show=True)
        self.assertTrue(result1.meta.success)
        self.assertEqual(result1.secret.value, "value1")
        
        result2 = self.manager.get_secret("secret2", show=True)
        self.assertTrue(result2.meta.success)
        self.assertEqual(result2.secret.value, "value2")
        
        # Step 4: Verify old passphrase no longer works
        # Remove cached key and try to set with old passphrase
        key_file = self.manager.get_cached_key_file_path()
        if key_file.exists():
            key_file.unlink()
        
        old_result = self.manager.set_cached_key("original-passphrase")
        self.assertFalse(old_result.meta.success)
        self.assertEqual(old_result.meta.error.code, "KEY_INVALID")
        
        # Step 5: Verify new passphrase works
        new_result = self.manager.set_cached_key("new-passphrase")
        self.assertTrue(new_result.meta.success)
    
    def test_update_key_cached_key_invalid(self):
        """Test update-key command when cached key is invalid for existing secrets.
        
        This test creates a scenario where the cached key cannot decrypt
        the existing .secrets file (corrupted state).
        Expected: success: false
        """
        # Step 1: Set up initial key and secrets
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        
        set_response = self.manager.set_secret("test-secret", "test-value")
        self.assertTrue(set_response.meta.success)
        
        # Step 2: Manually corrupt the cached key by overwriting it with wrong key
        # First, get the temp key path
        key_file = self.manager.get_cached_key_file_path()
        self.assertTrue(key_file.exists())
        temp_key_path = str(key_file)
        
        # Overwrite with a different key (from different passphrase)
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.fernet import Fernet
        import base64
        
        # Generate wrong key
        salt = b"multi_eden_secrets_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        wrong_key = base64.urlsafe_b64encode(kdf.derive(b"wrong-passphrase"))
        
        # Write wrong key to temp file
        with open(temp_key_path, 'wb') as f:
            f.write(wrong_key)
        
        # Step 3: Try to update key - should fail because cached key is invalid
        result = self.manager.update_encryption_key("new-passphrase")
        
        # Should fail with CACHED_KEY_INVALID error
        self.assertFalse(result.meta.success)
        self.assertEqual(result.meta.error.code, "KEY_INVALID")
        self.assertIn("invalid", result.meta.error.message.lower())
    
    def test_update_key_no_secrets_file(self):
        """Test update-key command when no .secrets file exists.
        
        This test verifies that update-key works even when there's no
        existing .secrets file - it should just update the cached key.
        """
        # Step 1: Set cached key but don't create any secrets
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        
        # Verify no secrets file exists
        secrets_file = self.manager.get_secrets_file_path()
        self.assertFalse(secrets_file.exists())
        
        # Step 2: Update key
        result = self.manager.update_encryption_key("new-passphrase")
        
        # Should succeed
        self.assertTrue(result.meta.success)
        self.assertIsNotNone(result.hash)
        
        new_result = self.manager.set_cached_key("new-passphrase")
        self.assertTrue(new_result.meta.success)
        self.assertEqual(new_result.code, "CACHE_KEY_NO_CHANGE")
    
    def test_update_key_response_structure(self):
        """Test that update-key responses follow expected JSON structure."""
        
        # Test successful response structure
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        
        result = self.manager.update_encryption_key("new-passphrase")
        
        # Should have success and hash
        self.assertTrue(result.meta.success)
        self.assertIsNotNone(result.hash)
        self.assertIsInstance(result.hash, str)
        self.assertEqual(len(result.hash), 16)  # SHA256 hash truncated to 16 chars
        
        # Test error response structure (no cached key)
        self._cleanup_test_files()
        error_result = self.manager.update_encryption_key("new-passphrase")
        
        # Should have success=false and error with code and message
        self.assertFalse(error_result.meta.success)
        self.assertIsNotNone(error_result.meta.error)
        self.assertIsNotNone(error_result.meta.error.code)
        self.assertIsNotNone(error_result.meta.error.message)
    
    def test_update_key_preserves_all_secrets(self):
        """Test that update-key preserves all secrets during re-encryption.
        
        This test creates multiple secrets and verifies they all remain
        intact after key update.
        """
        # Step 1: Set up multiple secrets
        key_response = self.manager.set_cached_key("original-passphrase")
        self.assertTrue(key_response.meta.success)
        
        secrets_data = {
            "api-key": "sk-1234567890abcdef",
            "database-url": "postgresql://user:pass@localhost/db",
            "jwt-secret": "super-secret-jwt-key",
            "redis-password": "redis-pass-123",
            "smtp-password": "email-pass-456"
        }
        
        for name, value in secrets_data.items():
            set_response = self.manager.set_secret(name, value)
            self.assertTrue(set_response.meta.success)
        
        # Step 2: Verify all secrets are accessible
        for name, expected_value in secrets_data.items():
            result = self.manager.get_secret(name, show=True)
            self.assertTrue(result.meta.success)
            self.assertEqual(result.secret.value, expected_value)
        
        # Step 3: Update key
        update_result = self.manager.update_encryption_key("new-passphrase")
        self.assertTrue(update_result.meta.success)
        
        # Step 4: Verify all secrets are still accessible with new key
        for name, expected_value in secrets_data.items():
            result = self.manager.get_secret(name, show=True)
            self.assertTrue(result.meta.success, f"Failed to get secret {name}")
            self.assertEqual(result.secret.value, expected_value, f"Secret {name} value changed")
        
        # Step 5: Verify list shows all secrets
        list_result = self.manager.list_secrets()
        self.assertTrue(list_result.meta.success)
        self.assertEqual(len(list_result.manifest.secrets), len(secrets_data))
        
        secret_names = [s.name for s in list_result.manifest.secrets]
        for name in secrets_data.keys():
            self.assertIn(name, secret_names)


if __name__ == "__main__":
    unittest.main()
