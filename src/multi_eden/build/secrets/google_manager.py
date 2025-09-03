"""
Google Cloud Secret Manager implementation.

Provides secrets management using Google Cloud Secret Manager."""

import logging
import os
from typing import Optional, List
from .interface import SecretsManager

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
            self._client = secretmanager.SecretManagerServiceClient()
            logger.debug(f"Google Secret Manager client initialized for project: {self.project_id}")
        return self._client
    
    def get_secret(self, secret_name: str, passphrase: Optional[str] = None) -> Optional[str]:
        """Get a secret value from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to retrieve
            
        Returns:
            Secret value if found, None otherwise
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            logger.debug(f"Accessing secret path: {secret_path}")
            
            response = self.client.access_secret_version(request={"name": secret_path})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.debug(f"Secret '{secret_name}' retrieved successfully (length: {len(secret_value)})")
            return secret_value
            
        except Exception as e:
            logger.warning(f"Failed to retrieve secret '{secret_name}' from Google Secret Manager: {e}")
            return None
    
    def set_secret(self, secret_name: str, secret_value: str, passphrase: Optional[str] = None) -> bool:
        """Set a secret value in Google Secret Manager.
        
        Args:
            secret_name: Name of the secret
            secret_value: Value to store
            
        Returns:
            True if successful, False otherwise
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
            return True
            
        except Exception as e:
            logger.error(f"Failed to set secret '{secret_name}' in Google Secret Manager: {e}")
            return False
    
    def delete_secret(self, secret_name: str, passphrase: Optional[str] = None) -> bool:
        """Delete a secret from Google Secret Manager.
        
        Args:
            secret_name: Name of the secret to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            secret_path = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": secret_path})
            
            logger.debug(f"Secret '{secret_name}' deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete secret '{secret_name}' from Google Secret Manager: {e}")
            return False
    
    def list_secrets(self, passphrase: Optional[str] = None) -> List[str]:
        """List all secrets in Google Secret Manager.
        
        Returns:
            List of secret names
        """
        try:
            parent = f"projects/{self.project_id}"
            secrets = self.client.list_secrets(request={"parent": parent})
            
            secret_names = []
            for secret in secrets:
                # Extract secret name from full path
                secret_name = secret.name.split("/")[-1]
                secret_names.append(secret_name)
            
            logger.debug(f"Listed {len(secret_names)} secrets from Google Secret Manager")
            return secret_names
            
        except Exception as e:
            logger.error(f"Failed to list secrets from Google Secret Manager: {e}")
            return []
    
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

