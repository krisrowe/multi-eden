"""
Multi-Environment SDK Task Collection
"""
from invoke import Collection

# Create namespace and collect tasks from each submodule
namespace = Collection()

# Import task modules and add them to namespace using Collection.from_module()
from .build.tasks import test, build, deploy, docker, local, auth, config, init_app, prompt

# Add tasks from each submodule (flattened)
for submodule in [test, build, deploy, docker, local, auth, config, init_app, prompt]:
    submodule_collection = Collection.from_module(submodule)
    for task_name, task in submodule_collection.tasks.items():
        namespace.add_task(task)

# Register app-specific CLI tasks
from . import cli
cli.register_cli_tasks(namespace)


