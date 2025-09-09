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
from multi_eden.build.config.models import LoadParams


def config(profile: str = None):
    """Decorator that loads environment configuration.
    
    Args:
        profile: Default profile to load. If None, requires profile parameter.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(ctx, *args, **kwargs):
            # If no profile specified, try to get it from profile parameter
            profile_to_load = profile
            if not profile_to_load:
                profile_to_load = kwargs.get('profile')
                if not profile_to_load:
                    print("❌ No profile specified and no profile parameter provided", file=sys.stderr)
                    sys.exit(1)
            
            try:
                params = LoadParams(top_layer=profile_to_load)
                load_env(params)
            except ConfigException as e:
                print(e.guidance, file=sys.stderr)
                sys.exit(1)
            # Let other exceptions bubble up
            
            return func(ctx, *args, **kwargs)
        return wrapper
    return decorator

