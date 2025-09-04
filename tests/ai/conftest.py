"""
AI test conftest.py for multi-eden.

This module provides AI test configuration and environment setup.
"""

import os
import pytest
from multi_eden.build.config.loading import load_env


def pytest_configure(config):
    """Configure AI test environment."""
    # Bootstrap logging
    from multi_eden.run.config.logging import auto_bootstrap_logging
    auto_bootstrap_logging()(None)
    
    # Load AI test environment variables (includes GEMINI_API_KEY)
    load_env(test_mode='ai', quiet=True)
    
    # No cleanup needed - process isolation handles it automatically


