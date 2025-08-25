"""
Environment and secrets management.

Loads secrets configuration based on --config-env command line argument.
"""
import json
import logging
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml
from .secrets import SecretsConfig

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

# Global secrets instance - initialized as None, loaded on demand (private)
_secrets: Optional[SecretsConfig] = None

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
    
    RATIONALE: This lazy loading approach automatically handles all entry points:
    - API Server (core/api.py) - Started via Docker/Cloud Run
    - CLI Interface (core/cli.py) - Started via invoke tasks or direct execution  
    - Test Suite (pytest) - Started via invoke test or direct pytest execution
    - Custom Entry Points - Any Python script that imports the SDK
    - AI Coding Assistant Entry Points - Dynamic execution by Cursor, Gemini CLI, Windsurf, etc.
    
    This eliminates the need to call set_config_env() in every entry point and ensures
    consistent behavior regardless of how the code is invoked.
    """
    global _config_env
    
    # If config environment is already set, we're done
    if _config_env:
        return
    
    # Quick check if --config-env is present (handle both --config-env=value and --config-env value formats)
    if any(arg.startswith('--config-env') for arg in sys.argv):
        try:
            # Parse just the --config-env argument
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument('--config-env', required=True)
            parsed_args, _ = parser.parse_known_args(sys.argv)
            
            if parsed_args.config_env:
                logger.debug(f"Setting config environment from command line: {parsed_args.config_env}")
                set_config_env(parsed_args.config_env)
                return
        except Exception as e:
            logger.debug(f"Failed to parse --config-env from command line: {e}")
    
    logger.debug("No --config-env found in command line arguments")


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
        secrets = get_secrets()
        logger.debug("Secrets loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load secrets: {e}")
        raise ConfigurationException(f"Configuration environment not set. Use --config-env argument (e.g., --config-env dev)")
    
    # Verify key configuration values
    if not secrets.salt or not secrets.salt.strip():
        logger.error("Salt value is missing or empty")
        raise ConfigurationException("Invalid configuration: salt value is missing or empty")
    
    logger.debug(f"Salt value verified: {secrets.salt[:8]}...")
    
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
        get_secrets()
        return True
    except Exception:
        return False


def set_secrets(secrets_config: Optional[SecretsConfig]) -> None:
    """Set the global secrets configuration.
    
    Args:
        secrets_config: SecretsConfig instance to set as global, or None to clear.
    """
    global _secrets
    _secrets = secrets_config


def set_config_env(env_name: str) -> None:
    """Set the configuration environment name."""
    global _config_env
    _config_env = env_name


def get_secrets() -> SecretsConfig:
    """Get secrets configuration using SECRETS_PATH environment variable.
    
    PRINCIPLES ENFORCED:
    - Never returns None or invalid configurations
    - Never falls back to defaults
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    - Uses lazy loading with caching for performance
    
    Uses lazy loading with caching - loads from disk once, then returns cached instance.
    This function now uses the current environment's secrets directory to locate the secrets.json file.
    
    Returns:
        SecretsConfig instance loaded from environment secrets (never None).
        
    Raises:
        SecretsNotAvailableException: If secrets file missing, invalid, or cannot be parsed
    """
    global _secrets
    
    # Ensure command line arguments have been parsed for --config-env if needed
    _parse_command_line()
    
    # Return cached instance if already loaded
    if _secrets is not None:
        return _secrets
    
    try:
        # Get secrets file path using new helper
        secrets_path = _get_secrets_file_path()
        
        # Load secrets directly
        try:
            with open(secrets_path, 'r') as f:
                config_dict = json.load(f)
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in secrets file {secrets_path}: {e}"
            logger.error(f"Secrets loading failed: {error_msg}")
            raise SecretsNotAvailableException(error_msg)
        except Exception as e:
            error_msg = f"Failed to read secrets file {secrets_path}: {e}"
            logger.error(f"Secrets loading failed: {error_msg}")
            raise SecretsNotAvailableException(error_msg)
        
        logger.debug(f"Loading secrets from: {secrets_path}")
        
        try:
            secrets_config = SecretsConfig.from_dict(config_dict)
        except Exception as e:
            error_msg = f"Failed to create SecretsConfig from {secrets_path}: {e}"
            logger.error(f"Secrets loading failed: {error_msg}")
            raise SecretsNotAvailableException(error_msg)
        
        # Cache the loaded secrets for future calls
        _secrets = secrets_config
        logger.debug(f"Successfully loaded secrets from: {secrets_path}")
        return secrets_config
            
    except SecretsNotAvailableException:
        # Re-raise our custom exception
        raise
    except Exception as e:
        error_msg = f"Unexpected error loading secrets: {e}"
        logger.error(f"Secrets loading failed: {error_msg}")
        raise SecretsNotAvailableException(error_msg)


def get_project_id() -> str:
    """Get the GCP project ID from configuration.
    
    IMPORTANT: Callers must check is_cloud_enabled() before calling this function.
    This function will raise an exception if cloud services are not enabled.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty string
    - Never suppresses exceptions inappropriately
    - Enforces explicit cloud-enabled checking
    - Tries host.json first, falls back to cloud detection if needed
    
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
    
    # Try to get project ID from host.json first
    try:
        host_config = _get_host()
        if host_config and 'project_id' in host_config:
            project_id = host_config['project_id']
            if project_id and project_id.strip():
                logger.debug(f"Got project ID from host.json: {project_id}")
                return project_id.strip()
    except Exception as e:
        logger.debug(f"Could not get project ID from host.json: {e}")
    
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
    - Check if host.json exists in the current environment's settings directory
    - If host.json exists and has project_id → cloud enabled
    - If no host.json or no project_id → cloud disabled
    
    PRINCIPLES ENFORCED:
    - Never suppresses exceptions inappropriately
    - Uses proper error logging
    - Simple logic without complex mode detection
    
    Returns:
        True if cloud services are available, False for unit testing/local-only mode
        
    Raises:
        CloudConfigurationException: If host.json exists but is invalid JSON
    """
    try:
        host_config = _get_host()
        if host_config and 'project_id' in host_config:
            project_id = host_config.get('project_id')
            if project_id and project_id.strip():
                logger.debug("Cloud enabled: project_id found in host.json")
                return True
    except CloudConfigurationException:
        # Re-raise configuration errors
        raise
    except Exception as e:
        logger.debug(f"Cloud disabled: could not load host configuration: {e}")
        return False
    
    logger.debug("Cloud disabled: no project_id in host.json or host.json not found")
    return False


def _get_host() -> Optional[Dict[str, Any]]:
    """Get host configuration from cached config or settings directory.
    
    Returns:
        Host configuration dictionary, or None if not available
        
    Raises:
        CloudConfigurationException: If host.json exists but is invalid JSON, or if cached config has no required fields
    """
    global _host_config
    
    # Return cached instance if already loaded
    if _host_config is not None:
        # Check if cached config has required fields
        if not _host_config.get('project_id') and not _host_config.get('api_url'):
            error_msg = "Cached host configuration has no project_id or api_url - environment is not cloud-enabled"
            logger.error(f"Host configuration error: {error_msg}")
            raise CloudConfigurationException(error_msg)
        return _host_config
    
    # Get settings folder path using new helper
    try:
        settings_path = _get_settings_folder_path()
    except (SecurityException, ConfigurationException) as e:
        logger.debug(f"Could not get settings folder path: {e}")
        return None
    
    host_file = settings_path / 'host.json'
    if not host_file.exists():
        logger.debug(f"No host.json found at {host_file}")
        return None
    
    try:
        with open(host_file, 'r') as f:
            host_config = json.load(f)
        logger.debug(f"Successfully loaded host configuration from {host_file}")
        return host_config
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in {host_file}: {e}"
        logger.error(f"Host configuration error: {error_msg}")
        raise CloudConfigurationException(error_msg)
    except Exception as e:
        error_msg = f"Failed to read {host_file}: {e}"
        logger.error(f"Host configuration error: {error_msg}")
        raise CloudConfigurationException(error_msg)


def get_providers() -> Dict[str, Any]:
    """Get provider configuration from providers.json.
    
    This function loads provider configuration from the current environment's settings directory.
    
    Returns:
        Provider configuration dictionary
        
    Raises:
        FileNotFoundError: If providers.json not found
        json.JSONDecodeError: If providers.json is invalid JSON
    """
    try:
        # Get settings folder path using new helper
        settings_path = _get_settings_folder_path()
        
        providers_file = settings_path / 'providers.json'
        if not providers_file.exists():
            error_msg = f"Providers file not found: {providers_file}"
            logger.error(f"Provider loading failed: {error_msg}")
            raise FileNotFoundError(error_msg)
        
        with open(providers_file, 'r') as f:
            providers_config = json.load(f)
        
        logger.debug(f"Loaded provider configuration from: {providers_file}")
        return providers_config
        
    except (FileNotFoundError, json.JSONDecodeError):
        raise
    except Exception as e:
        error_msg = f"Unexpected error loading provider configuration: {e}"
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
    Get the current configuration environment name with security validation.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty string
    - Always throws strongly-typed exceptions on failure
    - Uses --config-env argument if set, otherwise fails
    - Validates environment name for security (no path traversal, valid characters)
    
    Returns:
        Configuration environment name string (never None/empty)
        
    Raises:
        ValueError: If no config environment specified via --config-env argument
        SecurityException: If environment name contains invalid characters or path traversal attempts
    """
    if not _config_env:
        error_msg = "No config environment specified. Use --config-env argument"
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


def _get_settings_folder_path() -> Path:
    """
    Get the settings folder path for the current environment.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty path
    - Always throws strongly-typed exceptions on failure
    - Uses _get_config_env() for environment name
    - Validates path exists and is a directory
    - No defaults, no fallbacks
    
    Returns:
        Path to settings folder (never None/empty)
        
    Raises:
        SecurityException: If environment name fails security validation
        ConfigurationException: If settings folder doesn't exist or is invalid
    """
    env_name = _get_config_env()
    repo_root = Path.cwd()
    settings_path = repo_root / 'config' / 'settings' / env_name
    
    if not settings_path.exists():
        error_msg = f"Settings folder not found: {settings_path}"
        logger.error(f"Settings folder path resolution failed: {error_msg}")
        raise ConfigurationException(error_msg)
    
    if not settings_path.is_dir():
        error_msg = f"Settings path is not a directory: {settings_path}"
        logger.error(f"Settings folder path resolution failed: {error_msg}")
        raise ConfigurationException(error_msg)
    
    return settings_path


def _get_secrets_file_path() -> Path:
    """
    Get the secrets file path for the current environment.
    
    PRINCIPLES ENFORCED:
    - Never returns None or empty path
    - Always throws strongly-typed exceptions on failure
    - Uses _get_config_env() for environment name
    - Validates file exists and is readable
    - No defaults, no fallbacks
    
    Returns:
        Path to secrets.json file (never None/empty)
        
    Raises:
        SecurityException: If environment name fails security validation
        ConfigurationException: If secrets file doesn't exist or is invalid
    """
    env_name = _get_config_env()
    repo_root = Path.cwd()
    secrets_path = repo_root / 'config' / 'secrets' / env_name / 'secrets.json'
    
    if not secrets_path.exists():
        error_msg = f"Secrets file not found: {secrets_path}"
        logger.error(f"Secrets file path resolution failed: {error_msg}")
        raise ConfigurationException(error_msg)
    
    return secrets_path