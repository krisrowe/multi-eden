"""
Decorators for multi-env-sdk tasks.

This module provides decorators that add common behaviors to tasks,
such as automatic configuration environment setup.
"""

import functools
from typing import Optional, Callable, Any, Tuple
from .setup import get_task_default_env
from pathlib import Path


def resolve_config_env(config_env: Optional[str], args: Tuple, kwargs: dict, 
                      task_name: str, default_env_callback: Optional[Callable] = None, 
                      quiet: bool = False) -> str:
    """
    Helper method to resolve configuration environment from various sources.
    
    Args:
        config_env: Explicitly provided config_env
        args: Positional arguments from the task call
        kwargs: Keyword arguments from the task call
        task_name: Name of the task being executed
        default_env_callback: Optional callback to determine default environment based on task arguments
        
    Returns:
        str: Resolved configuration environment name
        
    Raises:
        ConfigEnvironmentRequiredError: If no environment can be determined
        ConfigEnvironmentNotFoundError: If the environment doesn't exist
        ConfigEnvironmentLoadError: If the environment cannot be loaded
    """
    
    # Determine the environment and selection method
    env_name = None
    selection_method = None
    
    if config_env:
        env_name = config_env
        selection_method = "command line argument"
    elif default_env_callback:
        try:
            # Create a mock context object for the callback
            mock_ctx = type('MockContext', (), {})()
            env_name = default_env_callback(mock_ctx, *args, **kwargs)
            if env_name:
                # Extract suite name from args if available
                suite = args[0] if args else 'unknown'
                selection_method = f"\033[1;33m{suite}\033[0m test suite default"
        except Exception as e:
            # If callback fails, fall through to standard lookup
            print(f"⚠️  Custom environment callback failed: {e}")
    
    # Fall back to standard lookup if no custom callback or callback failed
    if not env_name:
        env_name = get_task_default_env(task_name)
        if not env_name:
            raise ConfigEnvironmentRequiredError(
                f"Task '{task_name}' requires a configuration environment. "
                f"Please specify --config-env=<environment> or configure a default "
                f"environment for this task."
            )
        selection_method = f"\033[1;33m{task_name}\033[0m task default"
    
    # Display the configuration section (only if not quiet)
    if not quiet:
        import sys
        print("\n" + "="*50, file=sys.stderr)
        print("🔧 CONFIGURATION", file=sys.stderr)
        print("="*50, file=sys.stderr)
        print(f"Using: \033[1;36m{env_name}\033[0m", file=sys.stderr)  # Bright cyan color
        print(f"Selection method: {selection_method}", file=sys.stderr)
        
        # Add test paths if available (for test tasks)
        if args and len(args) > 0:
            suite = args[0]  # First argument is typically the suite for test tasks
            try:
                from multi_eden.build.tasks.test import get_test_paths_from_config
                test_paths = get_test_paths_from_config(suite)
                if test_paths:
                    colored_paths = [f"\033[1;36m{path}\033[0m" for path in test_paths]
                    print(f"Final test paths: {', '.join(colored_paths)}", file=sys.stderr)
            except Exception:
                pass  # Not a test task or paths not available
        
        if selection_method != "command line argument":
            print(f"💡 Override with: --config-env=<environment>", file=sys.stderr)
        print("="*50, file=sys.stderr)
    
    # Load the configuration environment (sets up secrets and environment variables)
    try:
        from multi_eden.build.config.loading import load_env
        
        load_env(env_name, quiet=quiet)  # Load the environment (sets up secrets)
        
        # Configuration environment loaded successfully (moved to debug logging)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Configuration environment '{env_name}' loaded successfully")
    except Exception as e:
        error_msg = f"Failed to load configuration environment '{env_name}': {e}"
        print(f"❌ {error_msg}")
        raise ConfigEnvironmentLoadError(error_msg)
    
    return env_name


def requires_config_env(func: Callable) -> Callable:
    """
    Decorator that requires a configuration environment to be set up.
    
    This decorator will:
    1. Check if --config-env is provided as an override
    2. If not, look up the default environment for the task from the centralized config system
    3. Set up the configuration environment before running the task
    4. Set up debug logging if --debug flag is provided
    5. Fail early with a strong-typed exception if the environment cannot be loaded
    
    Usage:
        @task
        @requires_config_env
        def my_task(ctx, config_env=None, debug=False):
            # config_env is automatically set if not provided
            # debug logging is automatically set up if debug=True
            pass
    """
    
    @functools.wraps(func)
    def wrapper(ctx, *args, **kwargs):
        # Get the task name from the function
        task_name = func.__name__
        
        # Check if config_env is explicitly provided
        config_env = kwargs.get('config_env')
        
        # Check if task has quiet parameter
        quiet = kwargs.get('quiet', False)
        
        # Check if task has debug parameter and set LOG_LEVEL
        debug = kwargs.get('debug', False)
        if debug:
            import os
            import sys
            os.environ['LOG_LEVEL'] = 'DEBUG'
            print("🐛 Debug logging enabled (LOG_LEVEL=DEBUG)", file=sys.stderr)
        
        # Use the helper method to resolve the environment (no callback)
        resolved_env = resolve_config_env(config_env, args, kwargs, task_name, None, quiet)
        kwargs['config_env'] = resolved_env
        
        # Now run the original task
        return func(ctx, *args, **kwargs)
    
    return wrapper


class ConfigEnvironmentRequiredError(Exception):
    """Raised when a task requires a configuration environment but none is specified."""
    pass


class ConfigEnvironmentNotFoundError(Exception):
    """Raised when a required configuration environment is not found."""
    pass


class ConfigEnvironmentLoadError(Exception):
    """Raised when a configuration environment cannot be loaded."""
    pass



