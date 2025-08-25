"""
Multi-Environment SDK Task Collection
"""
from invoke import Collection

# Create namespace and collect tasks from each submodule
namespace = Collection()

# Import and collect tasks from each submodule using Collection.from_module()
from .build.tasks import test, build, deploy, docker, local, auth, config

# Add tasks from each submodule (flattened)
for submodule in [build, deploy, docker, local, auth, config]:
    submodule_collection = Collection.from_module(submodule)
    for task_name, task in submodule_collection.tasks.items():
        namespace.add_task(task)

# Manually add test tasks since Collection.from_module isn't working for test module
from .build.tasks.test import test as test_task, pytest_config
namespace.add_task(test_task)
namespace.add_task(pytest_config)

# Manually add build tasks since Collection.from_module isn't working for build module
from .build.tasks.build import build as build_task, status as build_status
namespace.add_task(build_task)
namespace.add_task(build_status)

# Manually add deploy tasks since Collection.from_module isn't working for deploy module
from .build.tasks.deploy import deploy as deploy_task, deploy_web as deploy_web_task, status as deploy_status
namespace.add_task(deploy_task)
namespace.add_task(deploy_web_task)
namespace.add_task(deploy_status)

# Register app-specific CLI tasks
from . import cli
cli.register_cli_tasks(namespace)


