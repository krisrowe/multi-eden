"""Test configuration for multi_env_sdk tests."""

import os
from pathlib import Path


class TestConfig:
    """Lazy-loaded test configuration."""
    
    _project_id = None
    
    @classmethod
    def get_test_project_id(cls) -> str:
        """
        Get test project ID from .config-project file.
        
        Returns:
            Project ID string
            
        Raises:
            FileNotFoundError: If .config-project file doesn't exist
            ValueError: If .config-project file is empty or invalid
        """
        if cls._project_id is None:
            config_file = Path(__file__).parent.parent / '.config-project'
            
            if not config_file.exists():
                raise FileNotFoundError(
                    f"Test configuration file not found: {config_file}\n"
                    f"Create it with: echo 'your-test-project-id' > {config_file}"
                )
            
            project_id = config_file.read_text().strip()
            if not project_id:
                raise ValueError(
                    f"Test configuration file is empty: {config_file}\n"
                    f"Add project ID with: echo 'your-test-project-id' > {config_file}"
                )
            
            cls._project_id = project_id
        
        return cls._project_id


# Convenience function for direct import
def get_test_project_id() -> str:
    """Get test project ID. See TestConfig.get_test_project_id() for details."""
    return TestConfig.get_test_project_id()


# Test constants
TEST_APP_ID_BASE = "test-sdk"
LABEL_KEY = "multi-env-sdk"
LABEL_VALUE = "config"

# Bucket limits for test environment monitoring
# This helps detect bucket accumulation issues in test environments.
# The limit is checked whenever find_config_buckets_by_label() is called during tests.
# If bucket count exceeds this limit, a warning is logged (but tests don't fail).
# Adjust this value if your test environment legitimately needs more buckets.
MAX_EXPECTED_BUCKETS = 20  # Maximum number of buckets expected in test project
