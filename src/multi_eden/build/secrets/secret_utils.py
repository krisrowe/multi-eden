"""
Secret management utilities.

Provides utility functions for secrets management operations that integrate
with the existing environment loading system.
"""

import logging
import os
from pathlib import Path
from typing import Optional, List
from .factory import get_secrets_manager, cleanup_secrets_manager
from .models import DownloadSecretsResponse, SecretsManagerMetaResponse, ErrorInfo, GetSecretResponse, SetSecretResponse, DeleteSecretResponse, ListSecretsResponse, GetCachedKeyResponse, SetCachedKeyResponse, UpdateKeyResponse, ClearSecretsResponse

logger = logging.getLogger(__name__)


def create_unsupported_provider_response(operation: str, current_provider: str, supported_provider: str = "local"):
    """Create a standardized unsupported provider response for any operation.
    
    Args:
        operation: The operation name (e.g., 'get-cached-key', 'set-cached-key', 'update-key')
        current_provider: The current provider type
        supported_provider: The supported provider (default: 'local')
        
    Returns:
        Appropriate response model with unsupported provider error
    """
    from typing import Union
    
    error_info = ErrorInfo(
        code="UNSUPPORTED_PROVIDER",
        message=f"{operation} command is not supported by {current_provider} provider"
    )
    
    meta = SecretsManagerMetaResponse(
        success=False,
        provider=current_provider,
        operation=operation.replace('-', '_'),
        error=error_info
    )
    
    # Return the appropriate response type based on operation
    operation_responses = {
        'get': GetSecretResponse(meta=meta),
        'set': SetSecretResponse(meta=meta),
        'delete': DeleteSecretResponse(meta=meta),
        'list': ListSecretsResponse(meta=meta),
        'get-cached-key': GetCachedKeyResponse(meta=meta),
        'get_cached_key': GetCachedKeyResponse(meta=meta),
        'set-cached-key': SetCachedKeyResponse(meta=meta),
        'set_cached_key': SetCachedKeyResponse(meta=meta),
        'update-key': UpdateKeyResponse(meta=meta),
        'update_key': UpdateKeyResponse(meta=meta),
        'clear': ClearSecretsResponse(meta=meta),
        'download': DownloadSecretsResponse(meta=meta, count=0)
    }
    
    return operation_responses.get(operation, GetSecretResponse(meta=meta))


def get_project_id_from_env() -> Optional[str]:
    """Get project_id from loaded environment variables.
    
    This follows the same pattern as the existing secrets loading in loading.py
    where project_id comes from the loaded environment configuration.
    
    Returns:
        Project ID if found in environment, None otherwise
    """
    # Check for project_id in environment (set by load_env_dynamic)
    project_id = os.getenv('PROJECT_ID')
    if project_id:
        logger.debug(f"Found project_id in environment: {project_id}")
        return project_id
    
    logger.debug("No project_id found in environment")
    return None


def list_secrets_operation() -> bool:
    """List all secrets in the configured store.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        project_id = get_project_id_from_env()
        manager = get_secrets_manager(project_id)
        secrets = manager.list_secrets()
        
        if not secrets:
            print("📭 No secrets found in the configured store")
            return True
        
        print(f"🔐 Found {len(secrets)} secrets in {manager.manager_type} store:")
        for secret_name in sorted(secrets):
            print(f"  • {secret_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to list secrets: {e}")
        logger.error(f"List secrets failed: {e}")
        return False


def get_secret_operation(secret_name: str, show_value: bool = False) -> bool:
    """Get a specific secret value.
    
    Args:
        secret_name: Name of the secret to retrieve
        show_value: Whether to display the actual secret value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        project_id = get_project_id_from_env()
        manager = get_secrets_manager(project_id)
        value = manager.get_secret(secret_name)
        
        if value is None:
            print(f"❌ Secret '{secret_name}' not found in {manager.manager_type} store")
            return False
        
        if show_value:
            print(f"🔐 Secret '{secret_name}': {value}")
        else:
            print(f"✅ Secret '{secret_name}' exists (length: {len(value)} characters)")
            print("💡 Use --show-value to display the actual value")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to get secret '{secret_name}': {e}")
        logger.error(f"Get secret failed: {e}")
        return False


def set_secret_operation(secret_name: str, secret_value: str) -> bool:
    """Set a secret value.
    
    Args:
        secret_name: Name of the secret
        secret_value: Value to store
        
    Returns:
        True if successful, False otherwise
    """
    try:
        project_id = get_project_id_from_env()
        manager = get_secrets_manager(project_id)
        success = manager.set_secret(secret_name, secret_value)
        
        if success:
            print(f"✅ Secret '{secret_name}' set successfully in {manager.manager_type} store")
            return True
        else:
            print(f"❌ Failed to set secret '{secret_name}' in {manager.manager_type} store")
            return False
        
    except Exception as e:
        print(f"❌ Failed to set secret '{secret_name}': {e}")
        logger.error(f"Set secret failed: {e}")
        return False


def delete_secret_operation(secret_name: str, confirm: bool = False) -> bool:
    """Delete a secret.
    
    Args:
        secret_name: Name of the secret to delete
        confirm: Whether deletion is confirmed
        
    Returns:
        True if successful, False otherwise
    """
    try:
        project_id = get_project_id_from_env()
        manager = get_secrets_manager(project_id)
        
        # Check if secret exists
        if not manager.exists(secret_name):
            print(f"❌ Secret '{secret_name}' not found in {manager.manager_type} store")
            return False
        
        # Confirm deletion if not already confirmed
        if not confirm:
            response = input(f"⚠️  Are you sure you want to delete secret '{secret_name}'? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("🚫 Deletion cancelled")
                return True
        
        success = manager.delete_secret(secret_name)
        
        if success:
            print(f"✅ Secret '{secret_name}' deleted successfully from {manager.manager_type} store")
            return True
        else:
            print(f"❌ Failed to delete secret '{secret_name}' from {manager.manager_type} store")
            return False
        
    except Exception as e:
        print(f"❌ Failed to delete secret '{secret_name}': {e}")
        logger.error(f"Delete secret failed: {e}")
        return False


def download_secrets_operation(output_dir: str, config_env: str, passphrase: Optional[str] = None) -> DownloadSecretsResponse:
    """Download secrets to local storage.
    
    Args:
        output_dir: Output directory path where secrets will be saved
        config_env: Configuration environment name (unused)
        passphrase: Required passphrase for encrypted operations
        
    Returns:
        DownloadSecretsResponse with meta and count
    """
    try:
        from .factory import get_secrets_manager
        manager = get_secrets_manager()
        
        # Don't allow downloading from local manager (circular)
        if manager.manager_type == 'local':
            return DownloadSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=manager.manager_type,
                    operation="download",
                    error=ErrorInfo(code="INVALID_OPERATION", message="Cannot download from local manager")
                ),
                count=0
            )
        

        
        # Get secrets using the manager's list method (returns Pydantic response)
        list_response = manager.list_secrets(passphrase)
        if not list_response.meta.success:
            return DownloadSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=manager.manager_type,
                    operation="download",
                    error=list_response.meta.error
                ),
                count=0
            )
        
        secrets_count = len(list_response.manifest.secrets) if list_response.manifest else 0
        if secrets_count == 0:
            return DownloadSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=manager.manager_type,
                    operation="download"
                ),
                count=0
            )
        
        # Create a new local secrets manager with custom output path
        from .local_manager import LocalSecretsManager
        output_manager = LocalSecretsManager()
        output_manager.set_repo_folder(output_dir)
        
        # Set all secrets in the output manager
        success_count = 0
        for secret in list_response.manifest.secrets:
            # Get the actual secret value
            get_response = manager.get_secret(secret.name, passphrase, show=True)
            if get_response.meta.success and get_response.secret:
                set_response = output_manager.set_secret(secret.name, get_response.secret.value, passphrase=passphrase)
                if not set_response.meta.success:
                    # Return the actual error from the first failed secret operation
                    return DownloadSecretsResponse(
                        meta=SecretsManagerMetaResponse(
                            success=False,
                            provider=manager.manager_type,
                            operation="download",
                            error=set_response.meta.error
                        ),
                        count=success_count
                    )
                success_count += 1
        
        if success_count != secrets_count:
            return DownloadSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=manager.manager_type,
                    operation="download",
                    error=ErrorInfo(
                        code="PARTIAL_DOWNLOAD", 
                        message=f"Only {success_count}/{secrets_count} secrets downloaded successfully"
                    )
                ),
                count=success_count
            )
        
        return DownloadSecretsResponse(
            meta=SecretsManagerMetaResponse(
                success=True,
                provider=manager.manager_type,
                operation="download"
            ),
            count=secrets_count
        )
        
    except Exception as e:
        logger.error(f"Download secrets failed: {e}")
        return DownloadSecretsResponse(
            meta=SecretsManagerMetaResponse(
                success=False,
                provider="unknown",
                operation="download",
                error=ErrorInfo(code="UNKNOWN_ERROR", message=str(e))
            ),
            count=0
        )
    finally:
        # Clean up any temporary resources
        cleanup_secrets_manager()
