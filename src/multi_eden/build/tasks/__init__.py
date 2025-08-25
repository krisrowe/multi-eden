"""
Multi-env SDK tasks package.

This package contains all the task modules for the multi-env SDK.
"""

# Import task functions so they're available at the package level
from .test import test, pytest_config
from .build import build, status as build_status
from .deploy import deploy, deploy_web, status as deploy_status
from .docker import (
    docker_build, docker_run, compose_up, compose_down,
    compose_logs, compose_restart, docker_status, docker_cleanup
)
from .local import (
    api_start, api_stop, setup, api_status, api_restart
)
from .auth import token
from .config.backup import config_env_backup
from .config.restore import config_env_restore
from .config.init import init_config
from .config.setup import set_env_config, get_env_config, list_env_configs

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
