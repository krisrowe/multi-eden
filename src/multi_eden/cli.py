"""
CLI Plugin System for Multi-env SDK.

This module automatically loads app-specific CLI tasks from the SDK configuration
and registers them as invoke tasks that call the specified modules.
"""

import logging
import logging
import os
import sys
import yaml
import subprocess
from pathlib import Path
from invoke import task
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)



def _load_cli_config() -> Dict[str, Any]:
    """Load CLI configuration from cli.yaml if it exists."""
    # Look for cli.yaml in the current working directory (project root)
    # For pip-installed library, use current working directory
    repo_root = Path.cwd()
    cli_config_path = repo_root / "cli.yaml"
    
    logger.debug(f"Looking for cli.yaml at: {cli_config_path}")
    logger.debug(f"cli.yaml exists: {cli_config_path.exists()}")
    
    if not cli_config_path.exists():
        return {}
    
    try:
        with open(cli_config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.debug(f"Successfully loaded config: {config}")
        return config.get('tasks', {})
    except Exception as e:
        logger.warning(f"Could not load cli.yaml: {e}")
        return {}


def _create_task_runner(module: str, args: List[str], user_args: Dict[str, Any]):
    """
    Create a task function that runs the specified module with args,
    dynamically adding user-provided arguments.
    """
    
    # Dynamically create the function signature
    # Note: This is advanced metaprogramming to create a function signature
    # that invoke can introspect correctly.
    arg_defs = []
    for name, config in user_args.items():
        # We assume all args are optional strings for simplicity here
        arg_defs.append(f"{name}=None")
        
    func_sig = f"def task_runner(ctx, {', '.join(arg_defs)}):"
    
    # Create the function body
    func_body = f"""
        import sys
        import subprocess
        from pathlib import Path
        
        repo_root = Path.cwd()
        additional_args = []
        
        # Collect the arguments that were actually passed
        local_vars = locals()
        for name in {list(user_args.keys())}:
            value = local_vars.get(name)
            if value is not None:
                additional_args.extend([f"--{{name.replace('_', '-')}}", str(value)])

        # Check if we're in a virtual environment, if not, try to activate one
        venv_python = repo_root / "venv" / "bin" / "python"
        if venv_python.exists():
            # Use the venv python directly
            python_executable = str(venv_python)
        else:
            # Fallback to current python
            python_executable = sys.executable
        
        cmd = [python_executable, "-m", "{module}"] + {args} + additional_args
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=repo_root
            )
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            if result.returncode != 0:
                sys.exit(result.returncode)
        except Exception as e:
            print(f"Error running '{module}': {{e}}", file=sys.stderr)
            sys.exit(1)
    """
    
    # Combine signature and body
    func_code = f"{func_sig}\n    {func_body}"
    
    # Execute the code to define the function
    temp_globals = {}
    exec(func_code, globals(), temp_globals)
    
    # Return the dynamically created function, wrapped in @task
    return task(temp_globals['task_runner'])

def register_cli_tasks(namespace):
    """Register CLI tasks from cli.yaml configuration."""
    logger.debug("register_cli_tasks called")
    config = _load_cli_config()
    logger.debug(f"Loaded config: {config}")
    
    for task_name, task_config in config.items():
        logger.debug(f"Processing task {task_name}: {task_config}")
        if isinstance(task_config, dict) and 'module' in task_config:
            module = task_config['module']
            args = task_config.get('args', [])
            user_args = task_config.get('user_args', {})
            
            logger.debug(f"Creating task {task_name} for module {module} with args {args} and user_args {user_args}")
            
            task_func = _create_task_runner(module, args, user_args)
            task_func.__name__ = task_name
            
            namespace.add_task(task_func, name=task_name)
            logger.debug(f"Task {task_name} registered in namespace")
        else:
            logger.debug(f"Skipping {task_name} - invalid config")



# Auto-register tasks when this module is imported
# _register_cli_tasks()
