"""
Pydantic models for environment loading system.
"""
import os
import hashlib
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class StagedVariable(BaseModel):
    """A single staged environment variable with metadata."""
    name: str
    value: str
    source: str
    is_override: bool = False
    layer_name: str


class StagingResult(BaseModel):
    """Result of staging environment variables with validators."""
    staged_vars: Dict[str, StagedVariable]
    validators: List[Any]  # List of validator class instances


class LoadParams(BaseModel):
    """Parameters for environment loading with hash-based comparison."""
    top_layer: str
    files: Optional[List[str]] = None
    force_reload: bool = False
    base_layer: Optional[str] = None
    
    def get_cache_key(self) -> str:
        """Generate a hash key for caching based on relevant parameters."""
        # Only include parameters that affect the actual environment loading
        key_data = {
            "top_layer": self.top_layer,
            "files": self.files or [],
            "base_layer": self.base_layer or os.environ.get("BASE_ENV_LAYER")
        }
        
        # Create a stable string representation for hashing
        key_string = f"{key_data['top_layer']}|{sorted(key_data['files'])}|{key_data['base_layer']}"
        return hashlib.md5(key_string.encode()).hexdigest()


class ProviderConfig(BaseModel):
    """Configuration for providers."""
    providers: Dict[str, Any] = {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProviderConfig':
        """Create ProviderConfig from dictionary."""
        return cls(providers=data)


class HostConfig(BaseModel):
    """Configuration for host settings."""
    host: str = "localhost"
    port: int = 8000
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HostConfig':
        """Create HostConfig from dictionary."""
        return cls(**data)