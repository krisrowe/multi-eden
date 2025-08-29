"""
Multi-Environment SDK Configuration Package

This package provides configuration management functionality including:
- Initialization of config buckets
- Backup and restore operations
- Utility functions for config management
- Environment creation and management
"""

from .util import (
    find_config_bucket,
    get_project_id_from_config,
    get_repo_root,
    get_config_dir
)

from .init import (
    init_config,
    BucketNameConflictError,
    AppYamlMismatchError,
    InvalidProjectIdError,
    InvalidAppIdError
)

from .backup import config_env_backup
from .restore import config_env_restore
from .env import (
    config_env_create,
    config_env_update_secrets,
    config_env_list,
    CreateConfigEnvError,
    EnvironmentExistsError,
    InvalidEnvironmentNameError
)

__all__ = [
    # Utility functions
    'find_config_bucket',
    'get_project_id_from_config', 
    'get_repo_root',
    'get_config_dir',
    
    # Deployment functions
    'init_config',
    'BucketNameConflictError',
    'AppYamlMismatchError',
    'InvalidProjectIdError',
    'InvalidAppIdError',
    
    # Backup/restore functions
    'config_env_backup',
    'config_env_restore',
    
    # Environment management functions
    'config_env_create',
    'config_env_update_secrets',
    'config_env_list',
    'CreateConfigEnvError',
    'EnvironmentExistsError',
    'InvalidEnvironmentNameError'
]
