"""Task definitions for multi-env SDK.

Direct task imports for simplicity and reliability.
"""

from invoke import task

# Use absolute imports consistently
from multi_eden.build.tasks.config.init import init_config
from multi_eden.tests.runner import test_sdk
from multi_eden.build.tasks.test import test, pytest_config
from multi_eden.build.tasks.build import build, status as build_status
from multi_eden.build.tasks.deploy import deploy, deploy_web, status as deploy_status
from multi_eden.build.tasks.docker import (
    docker_build, docker_run, compose_up, compose_down, 
    compose_logs, compose_restart, docker_status, docker_cleanup
)
from multi_eden.build.tasks.local import (
    api_start, api_stop, setup, api_status, api_restart
)
from multi_eden.build.tasks.auth import token
from multi_eden.build.tasks.config.backup import config_env_backup
from multi_eden.build.tasks.config.restore import config_env_restore
from multi_eden.build.tasks.config.env import config_env_create, config_env_list

# All @task decorated functions from the imports above are now available
# No need to manually assign them - invoke will discover them automatically

# Import CLI plugin system to register app-specific tasks
try:
    print("DEBUG: Attempting to import CLI module with absolute import")
    from multi_eden.cli import _register_cli_tasks
    print("DEBUG: CLI module imported successfully with absolute import")
    _register_cli_tasks(globals())
    print("DEBUG: CLI tasks registered successfully with absolute import")
except ImportError as e:
    print(f"DEBUG: CLI import failed: {e}")
    print("CLI plugin system not available")
    pass  # CLI plugin system not available
