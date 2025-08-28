"""
Build package secrets utilities.

Provides manifest metadata and environment loading for build tasks.
"""

from .manifest import secrets_manifest
from ..config.loading import load_env

__all__ = ['secrets_manifest', 'load_env']
