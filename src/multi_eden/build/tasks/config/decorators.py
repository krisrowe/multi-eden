"""
Task decorators for environment loading.
"""
import functools
import sys
from typing import Optional

from multi_eden.build.config.exceptions import (
    ConfigException,
    ProjectIdRequiredException,
    NoProjectIdForGoogleSecretsException,
    NoKeyCachedForLocalSecretsException,
    LocalSecretNotFoundException,
    GoogleSecretNotFoundException
)
from multi_eden.build.config.loading import load_env


def requires_env_stack(environment: str = None):
    """Decorator that requires a specific environment stack to be loaded.
    
    Args:
        environment: Default environment to load. If None, requires config_env parameter.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(ctx, *args, **kwargs):
            # If no environment specified, try to get it from profile parameter
            env_to_load = environment
            if not env_to_load:
                env_to_load = kwargs.get('profile')
                if not env_to_load:
                    print("❌ No environment specified and no profile parameter provided", file=sys.stderr)
                    sys.exit(1)
            
            try:
                load_env(top_layer=env_to_load, fail_on_secret_error=True)
            except ConfigException as e:
                print(e.guidance, file=sys.stderr)
                sys.exit(1)
            # Let other exceptions bubble up
            
            return func(ctx, *args, **kwargs)
        return wrapper
    return decorator


# Legacy decorator for backward compatibility
def requires_config_env(environment: str = None):
    """Legacy decorator: Use requires_env_stack instead."""
    return requires_env_stack(environment)