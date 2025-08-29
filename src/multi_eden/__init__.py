"""
Multi-Environment SDK Task Collection
"""
from invoke import Collection

# Create namespace and collect tasks from each submodule
namespace = Collection()

# Manually add all tasks from each module
# Test tasks
from .build.tasks.test import test as test_task, pytest_config
namespace.add_task(test_task)
namespace.add_task(pytest_config)

# Build tasks
from .build.tasks.build import build as build_task, status as build_status
namespace.add_task(build_task)
namespace.add_task(build_status)

# Deploy tasks
from .build.tasks.deploy import deploy as deploy_task, deploy_web, status as deploy_status
namespace.add_task(deploy_task)
namespace.add_task(deploy_web)
namespace.add_task(deploy_status)

# Docker tasks
from .build.tasks.docker import (
    docker_build, docker_run, compose_up, compose_down,
    compose_logs, compose_restart, docker_status, docker_cleanup
)
namespace.add_task(docker_build)
namespace.add_task(docker_run)
namespace.add_task(compose_up)
namespace.add_task(compose_down)
namespace.add_task(compose_logs)
namespace.add_task(compose_restart)
namespace.add_task(docker_status)
namespace.add_task(docker_cleanup)

# Local tasks
from .build.tasks.local import (
    api_start, api_stop, setup, api_status, api_restart
)
namespace.add_task(api_start)
namespace.add_task(api_stop)
namespace.add_task(setup)
namespace.add_task(api_status)
namespace.add_task(api_restart)

# Auth tasks
from .build.tasks.auth import token
namespace.add_task(token)

# Config tasks
from .build.tasks.config import (
    config_env_backup, config_env_restore, init_config,
    config_env_create, config_env_update_secrets, config_env_list
)
namespace.add_task(config_env_backup)
namespace.add_task(config_env_restore)
namespace.add_task(init_config)
namespace.add_task(config_env_create)
namespace.add_task(config_env_update_secrets)
namespace.add_task(config_env_list)

# Init app tasks
from .build.tasks.init_app import init_app
namespace.add_task(init_app)

# Register app-specific CLI tasks
from . import cli
cli.register_cli_tasks(namespace)


