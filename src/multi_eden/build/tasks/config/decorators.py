"""
Task decorators for environment loading.
"""
import functools
import sys
from typing import Optional

from multi_eden.build.config.exceptions import (
    SecretUnavailableException,
    EnvironmentLoadError
)
from multi_eden.build.config.loading import load_env


def requires_config_env(environment: str):
    """Decorator that requires a specific environment to be loaded."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(ctx, *args, **kwargs):
            try:
                load_env(top_layer=environment)
            except SecretUnavailableException as e:
                print(f"❌ Secret unavailable: {e}", file=sys.stderr)
                sys.exit(1)
            except EnvironmentLoadError as e:
                print(f"❌ Environment load failed: {e}", file=sys.stderr)
                sys.exit(1)
            # Let other exceptions bubble up
            
            return func(ctx, *args, **kwargs)
        return wrapper
    return decorator