"""
Environment and secrets management.

Loads configuration from environment variables that are set by task runners.
Task runners load configuration files and inject them as environment variables.
"""
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml
from .secrets import Authorization, get_authorization_config, get_secret

# Set up logger
logger = logging.getLogger(__name__)


@dataclass
class SimpleAppConfig:
    """Application configuration loaded from app.yaml."""
    id: str

class AppIdNotAvailableException(Exception):
    """Raised when the application ID cannot be determined."""
    pass


class SecretsNotAvailableException(Exception):
    """Exception raised when secrets cannot be loaded or accessed."""
    pass



class ProjectIdNotAvailableException(Exception):
    """Raised when project ID cannot be determined from any source."""
    pass


class CloudConfigurationException(Exception):
    """Raised when host.json configuration is invalid or missing required fields."""
    pass


class NotConfiguredForFirebaseException(Exception):
    """Raised when Firebase operations are attempted but cloud services are not enabled."""
    pass


class SecurityException(Exception):
    """Raised when security validation fails."""
    pass


class ConfigurationException(Exception):
    """Raised when configuration cannot be loaded."""
    pass


try:
    from google.cloud import storage
    from google.auth import default
except ImportError:
    # Fallback for environments without Google Cloud SDK
    storage = None
    default = None


# Global app config instance - initialized as None, loaded on demand (private)
_app_config: Optional[SimpleAppConfig] = None

# Global authorization instance - initialized as None, loaded on demand (private)
_authorization: Optional[Authorization] = None

# Global host configuration instance - initialized as None, loaded on demand (private)
_host_config: Optional[Dict[str, Any]] = None

# Configuration environment - set by CLI/API entry points or lazy command line parsing
_config_env: Optional[str] = None

def get_app_config() -> SimpleAppConfig:
    """
    Load the application configuration from app.yaml in the project root.
    Falls back to a default app ID based on the package name if config is not available.
    """
    global _app_config
    if _app_config:
        return _app_config

    try:
        repo_root = Path.cwd()
        app_config_path = repo_root / 'config' / 'app.yaml'
        
        if not app_config_path.exists():
            # Generate default app ID from package name
            default_app_id = _generate_default_app_id()
            logger.debug(f"app.yaml not found at {app_config_path.absolute()}, using default app ID: {default_app_id}")
            _app_config = SimpleAppConfig(id=default_app_id)
            return _app_config

        with open(app_config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            if not isinstance(config_data, dict) or 'id' not in config_data:
                # Generate default app ID from package name
                default_app_id = _generate_default_app_id()
                logger.debug(f"'id' not found in app.yaml at {app_config_path.absolute()}, using default app ID: {default_app_id}")
                _app_config = SimpleAppConfig(id=default_app_id)
                return _app_config
            
            app_id = config_data['id']
            if not app_id or not app_id.strip():
                # Generate default app ID from package name
                default_app_id = _generate_default_app_id()
                logger.debug(f"app.yaml 'id' is blank/empty/null at {app_config_path.absolute()}, using default app ID: {default_app_id}")
                _app_config = SimpleAppConfig(id=default_app_id)
                return _app_config
            
            _app_config = SimpleAppConfig(id=app_id)
            return _app_config
            
    except Exception as e:
        # Generate default app ID from package name
        default_app_id = _generate_default_app_id()
        logger.debug(f"Failed to load app.yaml: {e}, using default app ID: {default_app_id}")
        _app_config = SimpleAppConfig(id=default_app_id)
        return _app_config

def _generate_default_app_id() -> str:
    """
    Generate a default app ID based on the package name.
    Converts underscores to hyphens and adds '-default' suffix.
    """
    # Get the package name from the current module path
    package_name = __name__.split('.')[0]  # 'multi_eden' from 'multi_eden.run.config.settings'
    
    # Convert underscores to hyphens and add -default suffix
    default_app_id = package_name.replace('_', '-') + '-default'
    
    return default_app_id


def get_app_id() -> str:
    """Returns the application ID from the app configuration."""
    return get_app_config().id


def _parse_command_line() -> None:
    """
    Parse command line arguments for --config-env if not already set.
    Only runs if _config_env is not already set.
    
    NOTE: This function is now deprecated since configuration is loaded by task runners
    and passed via environment variables. Direct execution requires environment variables
    to be set beforehand.
    """
    global _config_env
    
    # If config environment is already set, we're done
    if _config_env:
        return
    
    # No longer parsing --config-env from command line
    # Configuration must be provided via environment variables by task runners
    logger.debug("No --config-env parsing - configuration must be provided via environment variables")


def ensure_env_config_loaded() -> None:
    """
    Ensure that environment configuration is loaded and verify it's valid.
    
    This method:
    1. Attempts lazy command line parsing if not done yet
    2. Forces loading of secrets and provider settings
    3. Verifies key configuration values are present and valid
    4. Uses debug logging throughout the process
    
    Raises:
        ConfigurationException: If configuration cannot be loaded or verified
    """
    logger.debug("Ensuring environment configuration is loaded...")
    
    # Force load secrets (this will raise if config_env is not set
    # and cannot be set via command line argument)
    try:
        authorization = get_authorization()
        logger.debug("Authorization loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load authorization: {e}")
        raise ConfigurationException("Configuration environment not set. Environment variables must be provided by task runners.")
    
    # Verify key configuration values
    try:
        jwt_key = get_secret('jwt-secret-key')
        logger.debug("JWT key validation successful")
    except RuntimeError as e:
        logger.error(f"JWT key validation failed: {e}")
        raise ConfigurationException(f"Invalid configuration: {e}")
    
    logger.debug(f"JWT key verified: {jwt_key[:8]}...")
    
    # Check if custom auth is enabled (this will load provider settings)
    try:
        from .providers import is_custom_auth_enabled
        custom_auth_enabled = is_custom_auth_enabled()
        logger.debug(f"Custom auth enabled: {custom_auth_enabled}")
    except Exception as e:
        logger.error(f"Failed to check custom auth status: {e}")
        raise ConfigurationException(f"Failed to load provider configuration: {e}")
    
    logger.debug("Environment configuration verified successfully")


def is_secrets_available() -> bool:
    """Check if secrets are available and can be loaded.
    
    Returns:
        True if secrets can be loaded successfully, False otherwise.
    """
    try:
        get_authorization()
        return True
    except Exception:
        return False


def set_authorization(authorization: Optional[Authorization]) -> None:
    """Set the global authorization configuration.
    
    Args:
        authorization: Authorization instance to set as global, or None to clear.
    """
    global _authorization
    _authorization = authorization


def set_config_env(env_name: str) -> None:
    """Set the configuration environment name."""
    global _config_env
    _config_env = env_name


def get_authorization() -> Authorization:
    """Get authorization configuration from environment variables.
    
    Returns:
        Authorization instance loaded from environment variables.
        
    Raises:
        SecretsNotAvailableException: If required environment variables are missing
    """
    global _authorization
    
    # Return cached instance if already loaded
    if _authorization is not None:
        return _authorization
    
    try:
        # Use the new secrets system
        authorization = get_authorization_config()
        
        # Cache the loaded authorization for future calls
        _authorization = authorization
        logger.debug("Successfully loaded authorization from environment variables")
        return authorization
            
    except Exception as e:
        error_msg = f"Unexpected error loading authorization: {e}"
        logger.error(f"Authorization loading failed: {error_msg}")
        raise SecretsNotAvailableException(error_msg)





def get_project_id() -> str:
    """Get the GCP project ID from configuration.
    
    IMPORTANT: Callers must check is_cloud_enabled() before calling this function.
    This function will raise an exception if cloud services are not enabled.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty string
    - Never suppresses exceptions inappropriately
    - Enforces explicit cloud-enabled checking
    - Uses CLOUD_PROJECT_ID environment variable
    
    Returns:
        GCP project ID string (never None/empty)
        
    Raises:
        ProjectIdNotAvailableException: If project ID cannot be determined
        CloudConfigurationException: If cloud services are not enabled
    """
    # First check if cloud is enabled
    if not is_cloud_enabled():
        error_msg = "Cloud services are not enabled. Check is_cloud_enabled() before calling get_project_id()."
        logger.error(f"Project ID access failed: {error_msg}")
        raise CloudConfigurationException(error_msg)
    
    # Try to get project ID from CLOUD_PROJECT_ID environment variable
    project_id = os.environ.get('CLOUD_PROJECT_ID')
    if project_id and project_id.strip():
        logger.debug(f"Got project ID from CLOUD_PROJECT_ID environment variable: {project_id}")
        return project_id.strip()
    
    # Fall back to cloud detection
    try:
        project_id = _get_project_id_from_cloud()
        logger.debug(f"Got project ID from cloud detection: {project_id}")
        return project_id
    except Exception as e:
        error_msg = f"Could not determine project ID from any source: {e}"
        logger.error(f"Project ID detection failed: {error_msg}")
        raise ProjectIdNotAvailableException(error_msg)


def _get_project_id_from_cloud() -> str:
    """Get project ID from Google Cloud environment.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty string  
    - Never falls back to defaults inappropriately
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    
    Detection order:
    1. Google Cloud SDK default credentials
    2. GCE metadata service (if running on Google Cloud)
    
    Returns:
        Project ID string (never None/empty)
        
    Raises:
        ProjectIdNotAvailableException: If project ID cannot be determined
    """
    # Try Google Cloud SDK default credentials
    if default is not None:
        try:
            credentials, project_id = default()
            if project_id and project_id.strip():
                logger.debug(f"Got project ID from GCP default credentials: {project_id}")
                return project_id.strip()
            else:
                logger.debug("GCP default credentials available but no project ID returned")
        except Exception as e:
            logger.debug(f"Failed to get project ID from GCP default credentials: {e}")
    
    # Try GCE metadata service
    try:
        import requests
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(metadata_url, headers=headers, timeout=5)
        if response.status_code == 200:
            project_id = response.text.strip()
            if project_id:
                logger.debug(f"Got project ID from GCE metadata service: {project_id}")
                return project_id
        logger.debug(f"GCE metadata service returned status {response.status_code}")
    except Exception as e:
        logger.debug(f"Failed to get project ID from GCE metadata service: {e}")
    
    # No project ID found
    error_msg = (
        "Could not determine project ID from any cloud source. "
        "Tried: GCP default credentials, metadata service. "
        "Ensure you're running in a Google Cloud environment or have proper credentials configured."
    )
    logger.error(f"Project ID detection failed: {error_msg}")
    raise ProjectIdNotAvailableException(error_msg)


def is_cloud_enabled() -> bool:
    """
    Determine if cloud services (project ID, Firestore, etc.) are enabled.
    
    Logic:
    - Check if CLOUD_PROJECT_ID environment variable is set
    - If CLOUD_PROJECT_ID is set and not empty → cloud enabled
    - If no CLOUD_PROJECT_ID → cloud disabled
    
    PRINCIPLES ENFORCED:
    - Never suppresses exceptions inappropriately
    - Uses proper error logging
    - Simple logic without complex mode detection
    
    Returns:
        True if cloud services are available, False for unit testing/local-only mode
    """
    project_id = os.environ.get('CLOUD_PROJECT_ID')
    if project_id and project_id.strip():
        logger.debug(f"Cloud enabled: CLOUD_PROJECT_ID environment variable set: {project_id}")
        return True
    
    logger.debug("Cloud disabled: CLOUD_PROJECT_ID environment variable not set")
    return False


def get_providers() -> Dict[str, Any]:
    """Get provider configuration from environment variables.
    
    This function gets provider configuration from environment variables using the provider manager.
    
    Returns:
        Provider configuration dictionary
        
    Raises:
        ProviderConfigurationError: If provider configuration cannot be determined
    """
    try:
        from .providers import get_provider_config
        provider_config = get_provider_config()
        
        # Convert to dictionary format for backward compatibility
        providers_config = {
            'auth_provider': provider_config.auth_provider,
            'data_provider': provider_config.data_provider,
            'ai_provider': provider_config.ai_provider
        }
        
        logger.debug("Loaded provider configuration from environment variables")
        return providers_config
        
    except Exception as e:
        error_msg = f"Failed to get provider configuration: {e}"
        logger.error(f"Provider loading failed: {error_msg}")
        raise



def is_cloud_run() -> bool:
    """Check if the current environment is Google Cloud Run.
    
    Returns:
        True if running in Cloud Run, False otherwise
    """
    return os.environ.get('K_SERVICE') is not None


def _get_config_env() -> str:
    """
    Get the configuration environment name with validation.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty string
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    - Validates environment name for security
    
    Returns:
        Environment name string (never None/empty)
        
    Raises:
        ValueError: If no config environment is specified
        SecurityException: If environment name contains invalid characters or path traversal attempts
    """
    if not _config_env:
        error_msg = "No config environment specified. Environment variables must be provided by task runners."
        logger.error(f"Configuration environment detection failed: {error_msg}")
        raise ValueError(error_msg)
    
    env_name = _config_env.strip()
    
    # Basic validation
    if not env_name:
        error_msg = "Environment name cannot be empty or whitespace-only"
        logger.error(f"Configuration environment validation failed: {error_msg}")
        raise SecurityException(error_msg)
    
    # Check for path traversal attempts (this is NOT redundant with regex)
    if '..' in env_name:
        error_msg = f"Environment name contains path traversal attempt: {env_name}"
        logger.error(f"Configuration environment validation failed: {error_msg}")
        raise SecurityException(error_msg)
    
    # Check for valid folder name characters
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', env_name):
        error_msg = f"Environment name contains invalid characters: {env_name}"
        logger.error(f"Configuration environment validation failed: {error_msg}")
        raise SecurityException(error_msg)
    
    # Check reasonable length limit (only upper bound needed)
    if len(env_name) > 50:
        error_msg = f"Environment name too long (max 50 chars): {len(env_name)}"
        logger.error(f"Configuration environment validation failed: {error_msg}")
        raise SecurityException(error_msg)
    
    return env_name