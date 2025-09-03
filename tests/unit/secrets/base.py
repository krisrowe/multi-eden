"""Base test class for secrets unit tests."""

import unittest
import hashlib
from multi_eden.build.secrets.factory import get_secrets_manager


# Base path identifier for all test directories
TEST_BASE_IDENTIFIER = "multi-eden-unit-testing"

# Subdirectory names for different test components
SECRETS_REPO_SUBDIR = "secrets-repo"
SECRETS_CACHE_SUBDIR = "secrets-cache"


class BaseSecretsTest(unittest.TestCase):
    """Base test class for secrets tests with centralized cleanup."""
    
    def setUp(self):
        """Set up test environment."""
        self.manager = get_secrets_manager()
        
        # Clean up any existing test state
        self._cleanup_test_files()
    
    def tearDown(self):
        """Clean up test environment."""
        self._cleanup_test_files()
    
    def _cleanup_test_files(self):
        """Remove test secrets and temp key files."""
        # Remove cached key file
        key_file = self.manager.get_cached_key_file_path()
        if key_file.exists():
            key_file.unlink()
        
        # Remove secrets file
        secrets_file = self.manager.get_secrets_file_path()
        if secrets_file.exists():
            secrets_file.unlink()
        
        # Clear all secrets via manager
        self.manager.clear_all_secrets()
        
        # Remove cached key file again after clear_all_secrets
        key_file = self.manager.get_cached_key_file_path()
        if key_file.exists():
            key_file.unlink()
    
    def get_expected_secret_hash(self, secret_value: str) -> str:
        """Generate the expected hash for a secret value using the same method as LocalSecretsManager."""
        return hashlib.sha256(secret_value.encode()).hexdigest()[:16]
