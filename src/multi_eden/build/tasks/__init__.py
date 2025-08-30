"""
Multi-env SDK tasks package.

This package contains all the task modules for the multi-env SDK.
Modules are imported directly by the main __init__.py using Collection.from_module().
"""

import logging
from invoke import Collection, Config

# Global task configuration
def setup_global_config():
    """Set up global configuration for all tasks."""
    config = Config()
    
    # Add global --debug flag
    config.tasks.debug = False
    
    return config

def setup_logging(debug=False):
    """Set up logging configuration based on debug flag."""
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        # Set specific loggers to DEBUG
        logging.getLogger('multi_eden').setLevel(logging.DEBUG)
        print("🐛 Debug logging enabled")
    else:
        # Default logging level
        logging.basicConfig(level=logging.WARNING)

# Import CLI plugin system to register app-specific tasks
try:
    from ..cli import _register_cli_tasks
    _register_cli_tasks(globals())
except ImportError:
    try:
        from multi_eden.cli import _register_cli_tasks
        _register_cli_tasks(globals())
    except ImportError:
        pass  # CLI plugin system not available
