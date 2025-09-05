"""
Multi-Environment SDK Task Collection
"""

# Pytest plugin registration
pytest_plugins = ["multi_eden.pytest_plugin"]
from invoke import Collection

# Create namespace and collect tasks from each submodule
namespace = Collection()

# Import task modules and add them to namespace using Collection.from_module()
from .build.tasks import test, build, deploy, docker, local, auth, config, init_app, prompt, python_exec
from .build.tasks import secrets

# Add tasks from each submodule (flattened for most, nested for secrets)
for submodule in [test, build, deploy, docker, local, auth, config, init_app, prompt, python_exec]:
    submodule_collection = Collection.from_module(submodule)
    for task_name, task in submodule_collection.tasks.items():
        namespace.add_task(task)

# Add secrets as a nested namespace
secrets_collection = Collection.from_module(secrets)
namespace.add_collection(secrets_collection, name='secrets')

# CLI tasks removed - use clean task approach instead


