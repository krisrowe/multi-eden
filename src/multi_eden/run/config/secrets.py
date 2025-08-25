"""
Secrets configuration representation.

Represents secrets loaded from JSON files with proper dataclass structure.
"""
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List


@dataclass
class Authorization:
    """Authorization configuration."""
    all_authenticated_users: bool
    allowed_user_emails: List[str]


@dataclass
class SecretsConfig:
    """Secrets configuration representation.
    
    Contains all secrets loaded from the secrets JSON file.
    Can be serialized back to the JSON format we store.
    """
    salt: str
    google_api_key: str
    authorization: Authorization
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'SecretsConfig':
        """Create SecretsConfig from dictionary.
        
        Args:
            config: Dictionary containing configuration loaded from secrets file
            
        Returns:
            SecretsConfig instance
        """
        cls._validate_config(config)
        
        # Parse authorization
        auth_data = config['authorization']
        authorization = Authorization(
            all_authenticated_users=auth_data['all_authenticated_users'],
            allowed_user_emails=auth_data['allowed_user_emails']
        )
        
        return cls(
            salt=config['salt'],
            google_api_key=config['google_api_key'],
            authorization=authorization
        )
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]):
        """Validate that required configuration fields are present."""
        required_fields = ['salt', 'google_api_key', 'authorization']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        # Validate authorization object structure
        auth_config = config.get('authorization', {})
        if 'all_authenticated_users' not in auth_config:
            raise ValueError("Missing 'all_authenticated_users' in authorization config")
        if 'allowed_user_emails' not in auth_config:
            raise ValueError("Missing 'allowed_user_emails' in authorization config")
