"""
Google Cloud Secret Manager implementation.

Provides secrets management using Google Cloud Secret Manager."""

import logging
import os
from typing import Optional, List
from .interface import SecretsManager
from .models import (
    GetSecretResponse, SetSecretResponse, DeleteSecretResponse, ListSecretsResponse,
    SecretsManagerMetaResponse, SecretInfo, SecretsListManifest, SecretNameInfo, ErrorInfo
)

logger = logging.getLogger(__name__)


class GoogleSecretsManager(SecretsManager):
    """Google Cloud Secret Manager implementation."""
    
    def __init__(self):
        """Initialize Google Secrets Manager.
        
        Gets project_id from environment variable PROJECT_ID.
        """
        self._client = None
        self._project_id = None
    
    @property
    def manager_type(self) -> str:
        """Return the manager type."""
        return "google"
    
    @property
    def project_id(self) -> str:
        """Get project ID from environment."""
        if self._project_id is None:
            self._project_id = os.getenv('PROJECT_ID')
            if not self._project_id:
                raise RuntimeError("PROJECT_ID environment variable is required for Google Secrets Manager.")
        return self._project_id
    
    @property
    def client(self):
        """Lazy-load the Secret Manager client."""
        if self._client is None:
            from google.cloud import secretmanager
            # Set quota project to avoid warning
            self._client = secretmanager.SecretManagerServiceClient(
                client_options={"quota_project_id": self.project_id}
            )
            logger.debug(f"Google Secret Manager client initialized for project: {self.project_id}")
        return self._client
    
    def get_secret(self, secret_name: str, passphrase: Optional[str] = None, show: bool = False) -> GetSecretResponse:
        """Get a secret value from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to retrieve
            passphrase: Not used for Google Secret Manager (kept for interface compatibility)
            show: If True, include secret value; if False, only include hash
            
        Returns:
            GetSecretResponse
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            logger.debug(f"Accessing secret path: {secret_path}")
            
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.debug(f"Secret '{secret_name}' retrieved successfully (length: {len(secret_value)})")
            
            return GetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="get"
                ),
                secret=SecretInfo.create(
                    name=secret_name,
                    secret_value=secret_value,
                    show=show
                )
            )
            
        except Exception as e:
            logger.warning(f"Failed to retrieve secret '{secret_name}' from Google Secret Manager: {e}")
            return GetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="get",
                    error=ErrorInfo(code="SECRET_NOT_FOUND", message=str(e))
                ),
                secret=None
            )
    
    def set_secret(self, secret_name: str, secret_value: str, passphrase: Optional[str] = None) -> SetSecretResponse:
        """Set a secret value in Google Secret Manager.
        
        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            passphrase: Not used for Google Secret Manager (kept for interface compatibility)
            
        Returns:
            SetSecretResponse
        """
        try:
            # First, try to create the secret (if it doesn't exist)
            try:
                parent = f"projects/{self.project_id}"
                secret = {"replication": {"automatic": {}}}
                self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": secret
                    }
                )
                logger.debug(f"Created new secret '{secret_name}'")
            except Exception:
                # Secret already exists, that's fine
                logger.debug(f"Secret '{secret_name}' already exists")
            
            # Add the secret version
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            payload = {"data": secret_value.encode("UTF-8")}
            
            self.client.add_secret_version(
                request={"parent": parent, "payload": payload}
            )
            
            logger.debug(f"Secret '{secret_name}' set successfully")
            
            return SetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="set"
                ),
                secret=SecretInfo.create(
                    name=secret_name,
                    secret_value=secret_value,
                    show=False  # Don't return the value for security
                )
            )
            
        except Exception as e:
            logger.error(f"Failed to set secret '{secret_name}' in Google Secret Manager: {e}")
            return SetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="set",
                    error=ErrorInfo(code="SET_FAILED", message=str(e))
                ),
                secret=None
            )
    
    def delete_secret(self, secret_name: str, passphrase: Optional[str] = None) -> DeleteSecretResponse:
        """Delete a secret from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to delete
            passphrase: Not used for Google Secret Manager (kept for interface compatibility)
            
        Returns:
            DeleteSecretResponse
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": secret_path})
            
            logger.debug(f"Secret '{secret_name}' deleted successfully")
            
            return DeleteSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="delete"
                ),
                secret=SecretInfo(
                    name=secret_name,
                    value=None,
                    hash=None
                )
            )
            
        except Exception as e:
            logger.error(f"Failed to delete secret '{secret_name}' from Google Secret Manager: {e}")
            return DeleteSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="delete",
                    error=ErrorInfo(code="DELETE_FAILED", message=str(e))
                ),
                secret=None
            )
    
    def list_secrets(self, passphrase: Optional[str] = None) -> ListSecretsResponse:
        """List all secrets in Google Secret Manager.
        
        Args:
            passphrase: Not used for Google Secret Manager (kept for interface compatibility)
            
        Returns:
            ListSecretsResponse
        """
        try:
            parent = f"projects/{self.project_id}"
            secrets = self.client.list_secrets(request={"parent": parent})
            
            secret_infos = []
            for secret in secrets:
                # Extract secret name from full path
                secret_name = secret.name.split("/")[-1]
                secret_infos.append(SecretNameInfo(name=secret_name))
            
            logger.debug(f"Listed {len(secret_infos)} secrets from Google Secret Manager")
            
            return ListSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="list"
                ),
                manifest=SecretsListManifest(
                    secrets=secret_infos,
                    count=len(secret_infos)
                )
            )
            
        except Exception as e:
            logger.error(f"Failed to list secrets from Google Secret Manager: {e}")
            return ListSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="list",
                    error=ErrorInfo(code="LIST_FAILED", message=str(e))
                ),
                manifest=None
            )
    
    def exists(self, secret_name: str, passphrase: Optional[str] = None) -> bool:
        """Check if a secret exists in Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to check
            
        Returns:
            True if secret exists, False otherwise
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.get_secret(request={"name": secret_path})
            return True
        except Exception:
            return False

