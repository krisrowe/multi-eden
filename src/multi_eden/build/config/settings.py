"""
Unified Settings Configuration System

Provides a simplified, unified approach to configuration that replaces
the complex host.json + providers.json + secrets.json system.
"""

import os
import json
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Settings:
    """Build-time configuration for all app settings."""
    
    # Environment identification
    project_id: Optional[str] = None  # If set, indicates cloud environment
    
    # API configuration  
    api_in_memory: bool = True  # Whether API runs in same process as tests
    
    # Authentication settings
    custom_auth_enabled: bool = True
    
    # Provider stubbing
    stub_ai: bool = True
    stub_db: bool = True
    
    # Security settings
    local: bool = False  # Whether to allow local defaults for secrets
    
    # Network configuration
    port: Optional[int] = None  # API port override
    
    @classmethod
    def from_config_env(cls, config_env: str, app_config_path: str = "config/private/environments.yaml") -> 'Settings':
        """Load unified settings by merging SDK defaults with app-specific overrides."""
        
        # Load SDK default environments
        sdk_environments = cls._load_sdk_environments()
        
        # Load app-specific environment overrides (may not exist)
        app_environments = cls._load_app_environments(app_config_path)
        
        # Merge environments: for each environment, merge SDK defaults with app overrides
        merged_environments = {}
        for env_name in sdk_environments:
            merged_environments[env_name] = sdk_environments[env_name].copy()
            if env_name in app_environments:
                # Merge app-specific overrides into SDK defaults
                merged_environments[env_name].update(app_environments[env_name])
        
        # Add any app-only environments (not in SDK)
        for env_name in app_environments:
            if env_name not in merged_environments:
                merged_environments[env_name] = app_environments[env_name]
        
        if config_env not in merged_environments:
            available_envs = list(merged_environments.keys())
            raise ValueError(f"Unknown config environment '{config_env}'. Available: {available_envs}")
        
        env_config = merged_environments[config_env]
        
        # Create settings from merged config - NO DEFAULTS, EXPLICIT REQUIRED
        if 'api_in_memory' not in env_config:
            raise ValueError(f"Missing required setting 'api_in_memory' in environment '{config_env}'")
        if 'custom_auth_enabled' not in env_config:
            raise ValueError(f"Missing required setting 'custom_auth_enabled' in environment '{config_env}'")
        if 'stub_ai' not in env_config:
            raise ValueError(f"Missing required setting 'stub_ai' in environment '{config_env}'")
        if 'stub_db' not in env_config:
            raise ValueError(f"Missing required setting 'stub_db' in environment '{config_env}'")
            
        settings = cls(
            project_id=env_config.get('project_id'),  # Optional for local environments
            api_in_memory=env_config['api_in_memory'],
            custom_auth_enabled=env_config['custom_auth_enabled'],
            stub_ai=env_config['stub_ai'],
            stub_db=env_config['stub_db'],
            local=env_config.get('local', False),  # Optional, defaults to False for security
            port=env_config.get('port')  # Optional port override
        )
        
        # Log what was loaded
        source = "app override" if config_env in app_environments else "SDK default"
        logger.info(f"Loaded unified settings for '{config_env}' from {source}")
        return settings
    
    @staticmethod
    def _load_sdk_environments() -> Dict[str, Dict[str, Any]]:
        """Load SDK default environment configuration."""
        import yaml
        from pathlib import Path
        
        # SDK environments are in the build config directory
        sdk_config_path = Path(__file__).parent.parent.parent / 'build' / 'config' / 'environments.yaml'
        
        if not sdk_config_path.exists():
            raise FileNotFoundError(f"Required SDK environments file not found: {sdk_config_path}")
            
        try:
            with open(sdk_config_path, 'r') as f:
                config = yaml.safe_load(f)
                if not config or 'environments' not in config:
                    raise ValueError(f"Invalid SDK environments file: missing 'environments' key in {sdk_config_path}")
                return config['environments']
        except Exception as e:
            raise RuntimeError(f"Failed to load required SDK environments from {sdk_config_path}: {e}")
    
    @staticmethod
    def _load_app_environments(config_path: str) -> Dict[str, Dict[str, Any]]:
        """Load app-specific environment configuration from YAML file."""
        import yaml
        from pathlib import Path
        
        config_file = Path(config_path)
        if not config_file.exists():
            logger.info(f"App environment config not found: {config_path} (using SDK defaults only)")
            return {}
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                if config is None:
                    raise ValueError(f"App environment config file is empty: {config_path}")
                return config.get('environments', {})
        except Exception as e:
            raise RuntimeError(f"Failed to load app environment config from {config_path}: {e}")
    
    def derive_api_url(self, task_context: Optional[Dict[str, Any]] = None) -> str:
        """Derive API URL based on settings and task context."""
        
        # 1. Environment variable override (highest priority)
        if env_var := os.getenv('API_TESTING_URL'):
            return env_var
        
        # 2. Cloud environment (project_id present) - get actual Cloud Run URL
        if self.project_id:
            from multi_eden.internal.gcp import get_cloud_run_service_url
            service_name = f"{self.project_id}-api"
            return get_cloud_run_service_url(self.project_id, service_name)
        
        # 3. Local execution (no project_id) - only if local setting is enabled
        if not self.local:
            raise RuntimeError("Cannot derive API URL: no project_id for cloud and local execution not enabled")
        
        # Local execution - use port if configured, otherwise no port specified
        if self.port:
            return f"http://localhost:{self.port}"
        else:
            return "http://localhost"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for environment setup."""
        return {
            'project_id': self.project_id,
            'api_in_memory': self.api_in_memory,
            'custom_auth_enabled': self.custom_auth_enabled,
            'stub_ai': self.stub_ai,
            'stub_db': self.stub_db,
            'local': self.local,
            'port': self.port
        }


def load_settings(config_env: str) -> Settings:
    """Load settings for the given environment."""
    return Settings.from_config_env(config_env)
