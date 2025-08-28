"""
Configuration models for build-time configuration loading.
These models represent the structure of JSON configuration files.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class Authorization:
    """Authorization configuration from secrets.json."""
    all_authenticated_users: bool = False
    allowed_user_emails: List[str] = None
    
    def __post_init__(self):
        if self.allowed_user_emails is None:
            self.allowed_user_emails = []


@dataclass
class SecretsConfig:
    """Complete secrets configuration from secrets.json."""
    salt: str = ""
    google_api_key: str = ""
    authorization: Authorization = None
    
    def __post_init__(self):
        if self.authorization is None:
            self.authorization = Authorization()
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'SecretsConfig':
        """Create SecretsConfig from dictionary."""
        # Parse authorization
        auth_data = config.get('authorization', {})
        authorization = Authorization(
            all_authenticated_users=auth_data.get('all_authenticated_users', False),
            allowed_user_emails=auth_data.get('allowed_user_emails', [])
        )
        
        return cls(
            salt=config.get('salt', ''),
            google_api_key=config.get('google_api_key', ''),
            authorization=authorization
        )


@dataclass
class ProviderConfig:
    """Provider configuration from providers.json."""
    auth_provider: List[str] = None
    data_provider: str = "tinydb"
    ai_provider: str = "mocked"
    
    def __post_init__(self):
        if self.auth_provider is None:
            self.auth_provider = ["custom"]
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'ProviderConfig':
        """Create ProviderConfig from dictionary."""
        return cls(
            auth_provider=config.get('auth_provider', ["custom"]),
            data_provider=config.get('data_provider', "tinydb"),
            ai_provider=config.get('ai_provider', "mocked")
        )


@dataclass
class HostConfig:
    """Host configuration from host.json."""
    project_id: Optional[str] = None
    api_url: Optional[str] = None
    custom_domain: Optional[str] = None
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'HostConfig':
        """Create HostConfig from dictionary."""
        return cls(
            project_id=config.get('project_id'),
            api_url=config.get('api_url'),
            custom_domain=config.get('custom_domain')
        )
