"""
Root pytest configuration for multi-eden SDK.

Automatically configures test collection based on --suite command line argument.
"""

import pytest
from pathlib import Path

# Auto-bootstrap logging for all tests
from multi_eden.run.config.logging import auto_bootstrap_logging
auto_bootstrap_logging()(None)


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--config-env",
        action="store",
        help="Configuration environment (e.g., unit-testing, dev, prod)"
    )
    parser.addoption(
        "--suite",
        action="store",
        help="Test suite (e.g., unit, api, firestore)"
    )


def pytest_configure(config):
    """Configure pytest and show what tests are actually queued for execution."""
    try:
        # Get test mode configuration (environment should already be set by test.py)
        from multi_eden.run.config.testing import get_mode
        test_mode_config = get_mode()
        
        # Configuration info is already shown in CONFIGURATION ENVIRONMENT table
        # No need to duplicate it here
        
    except Exception as e:
        pytest.exit(f"❌ Failed to load mode configuration: {e}")
