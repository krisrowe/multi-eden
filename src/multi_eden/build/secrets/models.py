"""Pydantic models for secrets management.

Defines storage models (SecretsManifest) and response models with meta/data separation.
"""

from typing import List, Optional
from pydantic import BaseModel, computed_field


# Storage Models (what gets encrypted/stored)
class SecretDefinition(BaseModel):
    """Individual secret definition for storage."""
    name: str
    value: str


class SecretsManifest(BaseModel):
    """Container for all secrets in storage format."""
    secrets: List[SecretDefinition] = []


class SecretNameInfo(BaseModel):
    """Secret name information for listing (no values)."""
    name: str


class SecretsListManifest(BaseModel):
    """Container for secret names only (for listing)."""
    secrets: List[SecretNameInfo] = []


# Response Meta Models
class ErrorInfo(BaseModel):
    """Error information in responses."""
    code: str
    message: str


class SecretsManagerMetaResponse(BaseModel):
    """Meta information for all secrets manager responses."""
    success: bool
    provider: Optional[str] = None
    operation: Optional[str] = None  # e.g., "get", "set", "delete", "list", "get-cached-key"
    error: Optional[ErrorInfo] = None


# Response Data Models
class SecretInfo(BaseModel):
    """Secret information in API responses."""
    name: str
    value: Optional[str] = None  # Optional when show=False
    hash: Optional[str] = None
    
    @classmethod
    def create(cls, name: str, secret_value: str, show: bool = False) -> 'SecretInfo':
        """Factory method to create SecretInfo with proper hash calculation."""
        import hashlib
        secret_hash = hashlib.sha256(secret_value.encode()).hexdigest()[:16]
        
        return cls(
            name=name,
            value=secret_value if show else None,
            hash=secret_hash
        )


class CachedKeyInfo(BaseModel):
    """Information about a cached encryption key."""
    hash: str
    cache_file: Optional[str] = None  # Optional for security


# Response Models (meta + data)
class GetSecretResponse(BaseModel):
    """Response from getting a secret."""
    meta: SecretsManagerMetaResponse
    secret: Optional[SecretInfo] = None


class SetSecretResponse(BaseModel):
    """Response from setting a secret."""
    meta: SecretsManagerMetaResponse
    secret: Optional[SecretInfo] = None


class DeleteSecretResponse(BaseModel):
    """Response from deleting a secret."""
    meta: SecretsManagerMetaResponse
    secret: Optional[SecretInfo] = None


class ListSecretsResponse(BaseModel):
    """Response from listing secrets."""
    meta: SecretsManagerMetaResponse
    manifest: Optional[SecretsListManifest] = None


class GetCachedKeyResponse(BaseModel):
    """Response from getting cached key status."""
    meta: SecretsManagerMetaResponse
    key: Optional[CachedKeyInfo] = None


class SetCachedKeyResponse(BaseModel):
    """Response from setting a cached key."""
    meta: SecretsManagerMetaResponse
    key: Optional[CachedKeyInfo] = None
    code: Optional[str] = None  # Response code for cache key operations
        
    @property
    def hash(self) -> Optional[str]:
        """Get key hash for backward compatibility."""
        return self.key.hash if self.key else None


class UpdateKeyResponse(BaseModel):
    """Response from updating encryption key."""
    meta: SecretsManagerMetaResponse
    message: Optional[str] = None
    key: Optional[CachedKeyInfo] = None
    
    @property
    def hash(self) -> Optional[str]:
        """Get key hash for backward compatibility."""
        return self.key.hash if self.key else None


class ClearSecretsResponse(BaseModel):
    """Response from clearing all secrets."""
    meta: SecretsManagerMetaResponse
    cleared_count: Optional[int] = None
    message: Optional[str] = None


class DownloadSecretsResponse(BaseModel):
    """Response from downloading secrets."""
    meta: SecretsManagerMetaResponse
    count: Optional[int] = None
