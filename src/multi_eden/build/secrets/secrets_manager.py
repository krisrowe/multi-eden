"""
Google Secret Manager integration for build tasks.

Provides functions for accessing secrets from Google Cloud Secret Manager.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_secret_manager_value(project_id: str, secret_name: str) -> Optional[str]:
    """Get secret value from Google Secret Manager.
    
    Args:
        project_id: Google Cloud project ID
        secret_name: Name of the secret
        
    Returns:
        Secret value if found, None otherwise
        
    Raises:
        RuntimeError: If Secret Manager access fails
    """
    try:
        logger.debug(f"Attempting to import google.cloud.secretmanager...")
        from google.cloud import secretmanager
        logger.debug(f"Import successful")
        
        logger.debug(f"Creating SecretManagerServiceClient...")
        client = secretmanager.SecretManagerServiceClient()
        logger.debug(f"Client created successfully")
        
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        logger.debug(f"Accessing secret path: {secret_path}")
        
        response = client.access_secret_version(request={"name": secret_path})
        logger.debug(f"Secret access successful")
        
        secret_value = response.payload.data.decode("UTF-8")
        logger.debug(f"Secret decoded successfully (length: {len(secret_value)})")
        return secret_value
        
    except ImportError as e:
        logger.warning(f"Google Cloud Secret Manager library not available: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve secret '{secret_name}' from Secret Manager: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        raise RuntimeError(f"Secret Manager access failed: {e}")
