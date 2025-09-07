"""
Local encrypted secrets manager implementation.

Provides secrets management using local encrypted file storage with passphrase protection.
"""

import json
import logging
import os
import tempfile
import hashlib
import getpass
import base64
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from functools import wraps
from .interface import SecretsManager, PassphraseRequiredException, InvalidPassphraseException
from .models import SecretsManifest, SecretDefinition, GetSecretResponse, SetSecretResponse, DeleteSecretResponse, ListSecretsResponse, SecretsManagerMetaResponse, ErrorInfo, SecretInfo, GetCachedKeyResponse, SetCachedKeyResponse, CachedKeyInfo, UpdateKeyResponse, ClearSecretsResponse

logger = logging.getLogger(__name__)

def loads_secrets(response_class, requires_file=True, requires_key=True, allow_empty_list=False):
    """Decorator that handles secrets loading and all exception cases.
    
    Calls self._load_secrets(passphrase) and passes the manifest as first arg to decorated method.
    Handles all exceptions and returns proper error responses.
    
    Args:
        response_class: The Pydantic response class to return on error
        requires_file: If True, throw exception when no secrets file exists
        requires_key: If True, throw exception when no cached key available
        allow_empty_list: If True, return empty list when no file exists (for list operations)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Extract passphrase from kwargs or use None
            passphrase = kwargs.get('passphrase', None)
            
            # Extract throw_not_found from kwargs
            throw_not_found = kwargs.get('throw_not_found', False)
            
            try:
                # Check if secrets file exists
                secrets_file_path = self.get_secrets_file_path()
                if not secrets_file_path.exists():
                    if requires_file:
                        # Operation requires file to exist
                        if throw_not_found:
                            from multi_eden.build.config.exceptions import LocalSecretNotFoundException
                            # Extract secret_name from args (it's the second argument, first is secrets_manifest)
                            secret_name = args[1] if len(args) > 1 else 'unknown'
                            raise LocalSecretNotFoundException("No local secrets file found. Use 'invoke secrets.set' to create secrets.", secret_name=secret_name)
                        from .models import SecretsManagerMetaResponse, ErrorInfo
                        error_meta = SecretsManagerMetaResponse(
                            success=False,
                            provider="local",
                            error=ErrorInfo(code="SECRET_NOT_FOUND", message="No local secrets file found. Use 'invoke secrets.set' to create secrets.")
                        )
                        return _create_error_response(response_class, error_meta)
                    elif allow_empty_list:
                        # For list operations, return empty list when no file exists
                        secrets_manifest = SecretsManifest()
                        return func(self, secrets_manifest, *args, **kwargs)
                    else:
                        # For set operations, no file means we need a cached key to create new encrypted file
                        self._validate_cached_key_exists(passphrase)
                        secrets_manifest = SecretsManifest()
                        return func(self, secrets_manifest, *args, **kwargs)
                
                # File exists, so we need cached key to decrypt it
                if requires_key:
                    self._validate_cached_key_exists(passphrase)
                    # Load secrets manifest
                    secrets_manifest = self._load_secrets(passphrase)
                    # Call the original method with manifest as first argument
                    return func(self, secrets_manifest, *args, **kwargs)
                else:
                    # For operations that don't require key (shouldn't happen with current design)
                    secrets_manifest = SecretsManifest()
                    return func(self, secrets_manifest, *args, **kwargs)
                
            except PassphraseRequiredException as e:
                if throw_not_found:
                    from multi_eden.build.config.exceptions import NoKeyCachedForLocalSecretsException
                    # Extract secret_name from args (it's the first argument after secrets_manifest)
                    secret_name = args[0] if len(args) > 0 else 'unknown'
                    raise NoKeyCachedForLocalSecretsException(f"Local secrets require a cached decryption key but none is available", secret_name=secret_name)
                
                from .models import SecretsManagerMetaResponse, ErrorInfo
                error_meta = SecretsManagerMetaResponse(
                    success=False,
                    provider="local",
                    error=ErrorInfo(code="KEY_NOT_SET", message=str(e))
                )
                return _create_error_response(response_class, error_meta)
                
            except LocalSecretNotFoundException as e:
                if throw_not_found:
                    raise e  # Re-raise the LocalSecretNotFoundException
                
                from .models import SecretsManagerMetaResponse, ErrorInfo
                error_meta = SecretsManagerMetaResponse(
                    success=False,
                    provider="local",
                    error=ErrorInfo(code="SECRET_NOT_FOUND", message=str(e))
                )
                return _create_error_response(response_class, error_meta)
                
            except InvalidPassphraseException as e:
                from .models import SecretsManagerMetaResponse, ErrorInfo
                error_meta = SecretsManagerMetaResponse(
                    success=False,
                    provider="local",
                    error=ErrorInfo(code="KEY_INVALID", message=str(e))
                )
                return _create_error_response(response_class, error_meta)
                
            except Exception as e:
                from .models import SecretsManagerMetaResponse, ErrorInfo
                error_meta = SecretsManagerMetaResponse(
                    success=False,
                    provider="local",
                    error=ErrorInfo(code="UNKNOWN_ERROR", message=str(e))
                )
                return _create_error_response(response_class, error_meta)
        return wrapper
    return decorator

def _create_error_response(response_class, error_meta):
    """Helper to create error response based on response class structure."""
    # Handle different response types based on their structure
    if hasattr(response_class, 'secret'):
        return response_class(meta=error_meta, secret=None)
    elif hasattr(response_class, 'secrets'):
        return response_class(meta=error_meta, secrets=[])
    else:
        # Fallback - try to create with just meta
        return response_class(meta=error_meta)

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

# Module-level constants for default paths - these will be used as fallbacks
_DEFAULT_SECRETS_FILE = ".secrets"
_DEFAULT_CACHE_DIR = "/tmp"


class LocalSecretsManager(SecretsManager):
    """Local encrypted secrets manager using file-based storage."""
    
    # Public constants that tests and other code can reference - NO MORE HARDCODED VALUES ANYWHERE
    DEFAULT_SECRETS_FILENAME = ".secrets"
    CACHE_FILE_PREFIX = "multi_eden_key_"
    DEFAULT_CACHE_DIR = "/tmp"
    
    # Environment variable names
    ENV_SECRETS_REPO = "LOCAL_SECRETS_REPO"
    ENV_SECRETS_CACHE = "LOCAL_SECRETS_CACHE"
    
    # Cryptographic constants
    SALT_VALUE = b'multi_eden_secrets_salt_v1'
    PBKDF2_ITERATIONS = 100000
    HASH_ALGORITHM = 'sha256'
    
    def __init__(self):
        """Initialize local secrets manager."""
        self._repo_folder_override: Optional[Path] = None
        
    def set_repo_folder(self, folder_path: str) -> None:
        """Set a custom repository folder path override.
        
        Args:
            folder_path: Path to the folder where secrets should be stored
        """
        self._repo_folder_override = Path(folder_path)
    
    def get_secrets_file_path(self) -> Path:
        """Get the secrets file path from override, environment, or default."""
        if self._repo_folder_override:
            return self._repo_folder_override / self.DEFAULT_SECRETS_FILENAME
        
        secrets_file_path = os.getenv(self.ENV_SECRETS_REPO, self.DEFAULT_SECRETS_FILENAME)
        return Path(secrets_file_path)
    
    
    @property
    def manager_type(self) -> str:
        """Return the manager type."""
        return "local"
    
    def get_cached_key_file_path(self) -> Path:
        """Get the path for the cached key file."""
        # Use cache directory from environment (check at runtime)
        cache_dir_path = os.getenv(self.ENV_SECRETS_CACHE, self.DEFAULT_CACHE_DIR)
        cache_dir = Path(cache_dir_path)
        
        # Create unique temp key filename based on secrets file path
        secrets_path_str = str(self.get_secrets_file_path().absolute())
        path_hash = hashlib.sha256(secrets_path_str.encode()).hexdigest()[:8]
        temp_key_filename = f"{self.CACHE_FILE_PREFIX}{path_hash}"
        
        return cache_dir / temp_key_filename
    
    def is_key_cached(self) -> bool:
        """Check if a cached key exists.
        
        Returns:
            True if cached key exists, False otherwise
        """
        temp_key_path = self.get_cached_key_file_path()
        return temp_key_path.exists()
    
    def _validate_cached_key_exists(self, passphrase: Optional[str] = None) -> None:
        """Validate that a cached key exists before attempting any secret operations.
        
        Args:
            passphrase: Optional passphrase if provided by caller
            
        Raises:
            PassphraseRequiredException: If no cached key exists and no passphrase provided
        """
        if not self.is_key_cached() and passphrase is None:
            raise PassphraseRequiredException("No encryption key found. Set cached key first.")
    
    def set_cached_key_with_code(self, passphrase: str) -> Tuple[str, bytes]:
        """Set cached key from passphrase and return detailed response code.
        
        Returns:
            tuple: (response_code, key_bytes)
            
        Response codes:
            - CACHE_KEY_VALID_SET: Sets /tmp-cached key via passphrase valid for existing .secrets file when no /tmp-cached key present
            - CACHE_KEY_VALID_CHANGE: Sets cached key to valid one while existing /tmp-cached key doesn't match .secrets file
            - CACHE_KEY_INVALID: New key is wrong for .secrets file (doesn't matter if existing /tmp-cached key is valid)
            - CACHE_KEY_NEW: No .secrets file exists locally
            - CACHE_KEY_NO_CHANGE: Passphrase converts to key matching existing in /tmp (no validation against .secrets needed)
        """
        if not passphrase:
            raise ValueError("Passphrase cannot be empty")
        
        # Derive key from passphrase
        salt = self.SALT_VALUE
        new_key = self._derive_key_from_passphrase(passphrase, salt)
        
        temp_key_path = self.get_cached_key_file_path()
        existing_cached_key = None
        
        # Check if there's an existing cached key
        if temp_key_path.exists():
            try:
                with open(temp_key_path, 'rb') as f:
                    existing_cached_key = f.read()
            except (OSError, IOError):
                existing_cached_key = None
        
        # Check if new key matches existing cached key
        if existing_cached_key and existing_cached_key == new_key:
            # No change needed, return existing key
            self._key = new_key
            return "CACHE_KEY_NO_CHANGE", new_key
        
        # Check if secrets file exists
        secrets_file_path = self.get_secrets_file_path()
        if not secrets_file_path.exists() or secrets_file_path.stat().st_size == 0:
            # No secrets file, this is a new setup
            self._cache_key(new_key, temp_key_path)
            return "CACHE_KEY_NEW", new_key
        
        # Secrets file exists, validate new key against it
        try:
            with open(self.get_secrets_file_path(), 'rb') as f:
                encrypted_data = f.read()
            
            if encrypted_data:
                fernet = Fernet(new_key)
                fernet.decrypt(encrypted_data)  # This will raise InvalidToken if key is wrong
            
            # Key is valid for secrets file
            self._cache_key(new_key, temp_key_path)
            
            if existing_cached_key is None:
                return "CACHE_KEY_VALID_SET", new_key
            else:
                return "CACHE_KEY_VALID_CHANGE", new_key
                
        except InvalidToken:
            # New key cannot decrypt existing secrets
            raise InvalidPassphraseException("Passphrase cannot decrypt existing secrets")
    
    def _cache_key(self, key: bytes, temp_key_path: Path) -> None:
        """Cache the key to temp file with proper permissions."""
        temp_key_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_key_path, 'wb') as f:
            f.write(key)
        temp_key_path.chmod(0o600)
        
        if not temp_key_path.exists():
            raise RuntimeError(f"Failed to create temp key file: {temp_key_path}")
        
        self._key = key
        logger.debug(f"Cached encryption key: {temp_key_path}")
    
    def update_key(self, new_passphrase: str) -> None:
        """Update encryption key by re-encrypting all secrets with new passphrase.
        
        Requires existing valid cached key in /tmp. Decrypts entire .secrets file
        with cached key, re-encrypts with new passphrase-derived key, and updates
        cached key in /tmp.
        
        Args:
            new_passphrase: New passphrase to use for encryption
            
        Raises:
            PassphraseRequiredException: If no cached key available
            InvalidPassphraseException: If cached key is invalid for existing secrets
        """
        self._validate_cached_key_exists()
        
        if not new_passphrase:
            raise ValueError("New passphrase cannot be empty")
        
        # Get current cached key (this will raise exceptions if no key or invalid key)
        try:
            current_key = self._get_encryption_key()
        except PassphraseRequiredException:
            raise PassphraseRequiredException("No cached key found. Run 'invoke secrets.set-cached-key <passphrase>' first.")
        
        # If no secrets file exists, just update the cached key
        secrets_file_path = self.get_secrets_file_path()
        if not secrets_file_path.exists() or secrets_file_path.stat().st_size == 0:
            salt = self.SALT_VALUE
            new_key = self._derive_key_from_passphrase(new_passphrase, salt)
            temp_key_path = self.get_cached_key_file_path()
            self._cache_key(new_key, temp_key_path)
            return
        
        # Decrypt all secrets with current key
        try:
            with open(self.get_secrets_file_path(), 'rb') as f:
                encrypted_data = f.read()
            
            if encrypted_data:
                current_fernet = Fernet(current_key)
                decrypted_data = current_fernet.decrypt(encrypted_data)
                
                # Re-encrypt with new key
                salt = self.SALT_VALUE
                new_key = self._derive_key_from_passphrase(new_passphrase, salt)
                new_fernet = Fernet(new_key)
                new_encrypted_data = new_fernet.encrypt(decrypted_data)
                
                # Write re-encrypted data back to file
                with open(self.get_secrets_file_path(), 'wb') as f:
                    f.write(new_encrypted_data)
                
                # Update cached key
                temp_key_path = self.get_cached_key_file_path()
                self._cache_key(new_key, temp_key_path)
                
                
        except InvalidToken:
            raise InvalidPassphraseException("Cached key is invalid for existing secrets")
    
    def _cleanup_temp_key(self):
        """Clean up temporary key file."""
        temp_key_path = self.get_cached_key_file_path()
        if temp_key_path.exists():
            try:
                temp_key_path.unlink()
                logger.debug(f"Cleaned up temporary key file: {temp_key_path}")
            except (OSError, IOError) as e:
                logger.warning(f"Failed to clean up temporary key file: {e}")
    
    def _derive_key_from_passphrase(self, passphrase: str, salt: bytes) -> bytes:
        """Derive encryption key from passphrase using PBKDF2."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return key
    
    def _get_encryption_key(self, passphrase: Optional[str] = None) -> bytes:
        """Get or create the encryption key.
        
        Args:
            passphrase: Optional passphrase to use. If not provided, will try cached key first
        
        Raises:
            PassphraseRequiredException: If passphrase is required but not provided
            InvalidPassphraseException: If provided passphrase is invalid
        """
        # First, always try to load from temp storage (cached derived key)
        temp_key_path = self.get_cached_key_file_path()
        if temp_key_path.exists():
            try:
                with open(temp_key_path, 'rb') as f:
                    cached_key = f.read()
                
                # Validate cached key against existing secrets file (if it exists)
                secrets_file_path = self.get_secrets_file_path()
                if secrets_file_path.exists():
                    with open(secrets_file_path, 'rb') as f:
                        encrypted_data = f.read()
                    if encrypted_data:  # Only validate if file has content
                        fernet = Fernet(cached_key)
                        fernet.decrypt(encrypted_data)  # This will raise exception if key is wrong
                
                logger.debug("Loaded and validated encryption key from temporary storage")
                return cached_key
                
            except Exception as e:
                logger.warning(f"Cached key validation failed: {e}")
                # Raise InvalidPassphraseException to indicate cached key is wrong
                raise InvalidPassphraseException("Cached encryption key is invalid for existing secrets")
        
        # No cached key available, need passphrase to derive new key
        if passphrase is None:
            raise PassphraseRequiredException("No encryption key found. Set cached key first.")
        
        # Derive key from passphrase
        key = self._derive_key_from_passphrase(passphrase, self.SALT_VALUE)
        logger.debug("Derived encryption key from passphrase")
        return key
    
    def _load_secrets(self, passphrase: Optional[str] = None) -> SecretsManifest:
        """Load and decrypt secrets from file.
        
        Args:
            passphrase: Optional passphrase for key derivation
            
        Returns:
            SecretsManifest object
        """
        self._validate_cached_key_exists(passphrase)
        
        secrets_file_path = self.get_secrets_file_path()
        
        # Encrypted mode
        try:
            with open(self.get_secrets_file_path(), 'rb') as f:
                encrypted_data = f.read()
            
            if not encrypted_data:
                logger.debug("Secrets file is empty")
                return SecretsManifest()
            
            # Get encryption key (may prompt for passphrase)
            key = self._get_encryption_key(passphrase)
            
            # Decrypt the data
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data)
            
            # Parse JSON
            data = json.loads(decrypted_data.decode())
            # Handle both old dict format and new manifest format
            if isinstance(data, dict) and 'secrets' not in data:
                # Old format: convert dict to manifest
                secrets = [SecretDefinition(name=k, value=v) for k, v in data.items()]
                manifest = SecretsManifest(secrets=secrets)
            else:
                # New format: parse as manifest
                manifest = SecretsManifest.model_validate(data)
            
            logger.debug(f"Loaded {len(manifest.secrets)} secrets from {secrets_file_path}")
            return manifest
            
        except FileNotFoundError:
            logger.debug(f"Secrets file {secrets_file_path} not found")
            return SecretsManifest()
        except InvalidToken as e:
            logger.error(f"Failed to decrypt secrets file: {e}")
            raise InvalidPassphraseException("Invalid passphrase or corrupted secrets file")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse decrypted secrets: {e}")
            raise ValueError(f"Corrupted secrets file format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading secrets: {e}")
            raise
    
    def _save_secrets(self, secrets_manifest: SecretsManifest, passphrase: Optional[str] = None) -> bool:
        """Encrypt and save secrets to file."""
        self._validate_cached_key_exists(passphrase)
        
        try:
            # Convert to JSON
            json_data = secrets_manifest.model_dump_json(indent=2)
            
            # Encrypt the data
            key = self._get_encryption_key(passphrase)
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(json_data.encode())
            
            # Write to file
            secrets_file_path = self.get_secrets_file_path()
            secrets_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(secrets_file_path, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions (owner read/write only)
            secrets_file_path.chmod(0o600)
            
            logger.debug(f"Saved {len(secrets_manifest.secrets)} secrets to {secrets_file_path}")
            return True
            
        except (PassphraseRequiredException, InvalidPassphraseException):
            # Let these bubble up to the caller
            raise
        except Exception as e:
            logger.error(f"Failed to save secrets to {self.get_secrets_file_path()}: {e}")
            raise
    
    @loads_secrets(GetSecretResponse, requires_file=True, requires_key=True, allow_empty_list=False)
    def get_secret(self, secrets_manifest: SecretsManifest, secret_name: str, passphrase: Optional[str] = None, show: bool = False, throw_not_found: bool = False) -> GetSecretResponse:
        """Get a secret value from local storage.
        
        Args:
            secrets_manifest: Loaded secrets manifest (provided by decorator)
            secret_name: Name of the secret to retrieve
            passphrase: Optional passphrase for encrypted storage
            show: If True, include secret value; if False, only include hash
            
        Returns:
            GetSecretResponse
        """
        # Find the secret
        secret_def = None
        for secret in secrets_manifest.secrets:
            if secret.name == secret_name:
                secret_def = secret
                break
        
        if secret_def is None:
            if throw_not_found:
                from multi_eden.build.config.exceptions import LocalSecretNotFoundException
                raise LocalSecretNotFoundException(f"Secret '{secret_name}' not found in local secrets file", secret_name=secret_name)
            
            return GetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    error=ErrorInfo(code="SECRET_NOT_FOUND", message=f"Secret '{secret_name}' not found")
                ),
                secret=None
            )
        
        return GetSecretResponse(
            meta=SecretsManagerMetaResponse(
                success=True,
                provider=self.manager_type,
                error=None
            ),
            secret=SecretInfo.create(
                name=secret_name,
                secret_value=secret_def.value,
                show=show
            )
        )
    
    @loads_secrets(SetSecretResponse, requires_file=False, requires_key=True, allow_empty_list=False)
    def set_secret(self, secrets_manifest: SecretsManifest, secret_name: str, secret_value: str, passphrase: Optional[str] = None) -> SetSecretResponse:
        """Set a secret value in local storage.
        
        Args:
            secrets_manifest: Loaded secrets manifest (provided by decorator)
            secret_name: Name of the secret
            secret_value: Value to store
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            SetSecretResponse
        """
        # Remove existing secret with same name
        secrets_manifest.secrets = [s for s in secrets_manifest.secrets if s.name != secret_name]
        # Add new secret
        secrets_manifest.secrets.append(SecretDefinition(name=secret_name, value=secret_value))
        
        success = self._save_secrets(secrets_manifest, passphrase)
        
        if success:
            return SetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="set"
                ),
                secret=SecretInfo.create(
                    name=secret_name,
                    secret_value=secret_value,
                    show=False
                )
            )
        else:
            return SetSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    error=ErrorInfo(code="SAVE_FAILED", message="Failed to save secret")
                ),
                secret=SecretInfo(name=secret_name, value=None)
            )
    
    @loads_secrets(ListSecretsResponse, requires_file=False, requires_key=True, allow_empty_list=True)
    def list_secrets(self, secrets_manifest: SecretsManifest, passphrase: Optional[str] = None) -> ListSecretsResponse:
        """List all secret names in local storage.
        
        Args:
            secrets_manifest: Loaded secrets manifest (provided by decorator)
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            ListSecretsResponse
        """
        from .models import SecretsListManifest, SecretNameInfo
        
        # Convert full manifest to names-only manifest
        names_only_manifest = SecretsListManifest(
            secrets=[SecretNameInfo(name=secret.name) for secret in secrets_manifest.secrets]
        )
        
        return ListSecretsResponse(
            meta=SecretsManagerMetaResponse(success=True, provider=self.manager_type),
            manifest=names_only_manifest
        )
    
    @loads_secrets(DeleteSecretResponse, requires_file=True, requires_key=True, allow_empty_list=False)
    def delete_secret(self, secrets_manifest: SecretsManifest, secret_name: str, passphrase: Optional[str] = None) -> 'DeleteSecretResponse':
        """Delete a secret from local storage.
        
        Args:
            secrets_manifest: Loaded secrets manifest (provided by decorator)
            secret_name: Name of the secret to delete
            passphrase: Optional passphrase for encrypted storage
            
        Returns:
            DeleteSecretResponse
        """
        from .models import DeleteSecretResponse, SecretsManagerMetaResponse, ErrorInfo
        
        # Check if secret exists
        if secret_name not in [s.name for s in secrets_manifest.secrets]:
            return DeleteSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="delete",
                    error=ErrorInfo(code="SECRET_NOT_FOUND", message=f"Secret '{secret_name}' not found")
                ),
                secret_name=secret_name
            )
        
        # Remove the secret
        secrets_manifest.secrets = [s for s in secrets_manifest.secrets if s.name != secret_name]
        success = self._save_secrets(secrets_manifest, passphrase)
        
        if success:
            return DeleteSecretResponse(
                meta=SecretsManagerMetaResponse(success=True, provider=self.manager_type, operation="delete"),
                secret_name=secret_name
            )
        else:
            return DeleteSecretResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="delete",
                    error=ErrorInfo(code="DELETE_FAILED", message="Failed to save secrets after deletion")
                ),
                secret_name=secret_name
            )
    
    def exists(self, secret_name: str, passphrase: Optional[str] = None) -> bool:
        """Check if a secret exists in local storage.
        
        Args:
            secret_name: Name of the secret to check
            
        Returns:
            True if secret exists, False otherwise
        """
        self._validate_cached_key_exists(passphrase)
        
        secrets_manifest = self._load_secrets(passphrase)
        return secret_name in [s.name for s in secrets_manifest.secrets]
    
    def get_cached_key(self) -> 'GetCachedKeyResponse':
        """Get cached encryption key status and hash.
        
        Returns:
            GetCachedKeyResponse with key info if available, error if not
        """
        from .models import GetCachedKeyResponse, SecretsManagerMetaResponse, ErrorInfo, CachedKeyInfo
        import hashlib
        
        try:
            # Try to get current key without passphrase (will use cached key if available)
            current_key = self._get_encryption_key()
            key_hash = hashlib.sha256(current_key).hexdigest()[:16]  # First 16 chars of hash
            
            return GetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(success=True, provider=self.manager_type),
                key=CachedKeyInfo(hash=key_hash)
            )
            
        except PassphraseRequiredException:
            return GetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    error=ErrorInfo(
                        code="KEY_NOT_SET",
                        message="No encryption key found"
                    )
                )
            )
        except Exception as e:
            return GetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    error=ErrorInfo(
                        code="UNKNOWN_ERROR",
                        message=str(e)
                    )
                )
            )

    def set_cached_key(self, passphrase: str) -> SetCachedKeyResponse:
        """Set cached key from passphrase and return Pydantic response."""
        import hashlib
        try:
            response_code, key_bytes = self.set_cached_key_with_code(passphrase)
            key_hash = hashlib.sha256(key_bytes).hexdigest()[:16]
            
            return SetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=True, 
                    provider=self.manager_type,
                    operation="set_cached_key"
                ),
                key=CachedKeyInfo(hash=key_hash),
                code=response_code
            )
            
        except InvalidPassphraseException:
            return SetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="set_cached_key",
                    error=ErrorInfo(
                        code="KEY_INVALID",
                        message="Passphrase cannot decrypt existing secrets. Use 'invoke secrets.clear --force' to reset."
                    )
                )
            )
        except Exception as e:
            return SetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="set_cached_key",
                    error=ErrorInfo(code="UNKNOWN_ERROR", message=str(e))
                )
            )

    def update_encryption_key(self, new_passphrase: str) -> UpdateKeyResponse:
        """Update encryption key by re-encrypting all secrets with new passphrase."""
        import hashlib
        try:
            self.update_key(new_passphrase)  # Call existing method
            # Generate hash for the new key
            key_bytes = self._derive_key_from_passphrase(new_passphrase, b'salt')
            key_hash = hashlib.sha256(key_bytes).hexdigest()[:16]
            
            return UpdateKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="update_key"
                ),
                key=CachedKeyInfo(hash=key_hash)
            )
            
        except PassphraseRequiredException:
            return UpdateKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="update_key",
                    error=ErrorInfo(
                        code="KEY_NOT_SET",
                        message="No cached key found. Run 'invoke secrets.set-cached-key <passphrase>' first."
                    )
                )
            )
        except InvalidPassphraseException:
            return UpdateKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="update_key",
                    error=ErrorInfo(
                        code="KEY_INVALID",
                        message="Cached key is invalid for existing secrets"
                    )
                )
            )
        except Exception as e:
            return UpdateKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="update_key",
                    error=ErrorInfo(code="UNKNOWN_ERROR", message=str(e))
                )
            )

    def clear_all_secrets(self) -> ClearSecretsResponse:
        """Clear all secrets from the store."""
        try:
            # Get count before clearing
            list_response = self.list_secrets()
            if list_response.meta.success and list_response.manifest:
                cleared_count = len(list_response.manifest.secrets)
            else:
                cleared_count = 0
            
            # For local provider, delete the .secrets file
            secrets_file_path = self.get_secrets_file_path()
            if secrets_file_path.exists():
                secrets_file_path.unlink()
                logger.info(f"Cleared {cleared_count} secrets from local storage")
            
            return ClearSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=True,
                    provider=self.manager_type,
                    operation="clear"
                ),
                cleared_count=cleared_count,
                message=f"Successfully cleared {cleared_count} secrets"
            )
            
        except Exception as e:
            return ClearSecretsResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="clear",
                    error=ErrorInfo(code="UNKNOWN_ERROR", message=str(e))
                ),
                cleared_count=0
            )

    def clear_cached_key(self) -> 'GetCachedKeyResponse':
        """Clear the cached encryption key.
        
        Returns:
            GetCachedKeyResponse with meta indicating success/failure
        """
        try:
            cached_key_path = self.get_cached_key_file_path()
            if cached_key_path.exists():
                cached_key_path.unlink()
                logger.debug(f"Cleared cached key file: {cached_key_path}")
                
                # Also clear in-memory key
                self._key = None
                
                return GetCachedKeyResponse(
                    meta=SecretsManagerMetaResponse(
                        success=True,
                        provider=self.manager_type,
                        operation="clear_cached_key"
                    ),
                    key=None
                )
            else:
                return GetCachedKeyResponse(
                    meta=SecretsManagerMetaResponse(
                        success=True,
                        provider=self.manager_type,
                        operation="clear_cached_key"
                    ),
                    key=None
                )
            
        except Exception as e:
            logger.error(f"Failed to clear cached key: {e}")
            return GetCachedKeyResponse(
                meta=SecretsManagerMetaResponse(
                    success=False,
                    provider=self.manager_type,
                    operation="clear_cached_key",
                    error=ErrorInfo(code="CLEAR_FAILED", message=str(e))
                ),
                key=None
            )

    def cleanup(self):
        """Clean up in-memory cached keys only. Temp key files persist across processes."""
        self._key = None
        logger.debug("Local secrets manager cleanup completed")
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            self.cleanup()
        except (OSError, IOError):
            pass  # Ignore cleanup errors during destruction
