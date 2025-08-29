"""
Multi-env SDK tasks package.

This package contains all the task modules for the multi-env SDK.
Modules are imported directly by the main __init__.py using Collection.from_module().
"""

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
