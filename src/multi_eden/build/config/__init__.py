"""
Configuration management for multi-eden build tasks.
"""

import yaml
from pathlib import Path
from typing import Dict, Any

from .secrets import SecretsConfig, Authorization
from .providers import ProviderConfig
from .host import HostConfig
from .loading import load_env


def get_tasks_config() -> Dict[str, Any]:
    """Load tasks configuration from tasks.yaml."""
    config_path = Path(__file__).parent / 'tasks.yaml'
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


__all__ = [
    'SecretsConfig',
    'Authorization',
    'ProviderConfig', 
    'HostConfig',
    'load_env',
    'get_tasks_config'
]
