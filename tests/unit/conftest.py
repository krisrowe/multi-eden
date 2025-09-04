"""
Unit test conftest.py for multi-eden.

This module provides unit test configuration and environment setup.
"""

import os
from multi_eden.build.config.loading import load_env


def pytest_configure(config):
    """Configure unit test environment."""
    # Bootstrap logging
    from multi_eden.run.config.logging import auto_bootstrap_logging
    auto_bootstrap_logging()(None)
    
    # Load unit test environment variables
    load_env(test_mode='unit', quiet=True)
    
    # No cleanup needed - process isolation handles it automatically
