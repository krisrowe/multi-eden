#!/usr/bin/env python3
"""
Test mode configuration management.

Loads test configuration tests.yaml with proper validation,
lazy loading, caching, and no fallbacks or defaults - only exceptions thrown.
"""
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TestModeNotDetectedException(Exception):
    """Raised when test mode cannot be definitively identified."""
    pass


class TestModeConfigurationNotAvailable(Exception):
    """Raised when test configuration cannot be loaded."""
    pass


class TestModeValidationException(Exception):
    """Raised when test mode configuration is invalid or missing required fields."""
    pass


class APIConfigurationException(Exception):
    """Raised when API configuration cannot be determined."""
    pass


@dataclass
class TestModeConfig:
    """Test mode configuration"""
    mode: str
    description: Optional[str]
    in_memory_api: bool
    default_env: str
    tests: Optional[Dict[str, Any]] = None
    
    def get_test_paths(self) -> Optional[List[str]]:
        """Get test paths for this mode."""
        if self.tests:
            # Support both old 'path' and new 'paths' for backward compatibility
            if 'paths' in self.tests:
                return self.tests['paths']
            elif 'path' in self.tests:
                return [self.tests['path']]
        return None
    
    def get_test_path(self) -> Optional[str]:
        """Get test path for this mode (backward compatibility)."""
        paths = self.get_test_paths()
        if paths and len(paths) > 0:
            return paths[0]
        return None


# Global test mode instance - initialized as None, loaded on demand (private)
_test_mode: Optional[TestModeConfig] = None


def get_mode(mode_name: Optional[str] = None) -> TestModeConfig:
    """Get test mode configuration with automatic detection.
    
    PRINCIPLES ENFORCED:
    - Never returns None or invalid configurations
    - Never falls back to defaults
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    - Uses lazy loading with caching for performance
    
    Uses lazy loading with caching - loads from disk only once, then returns cached instance.
    
    Returns:
        TestModeConfig instance for the detected mode (never None).
        
    Raises:
        TestModeNotDetectedException: If test mode cannot be definitively identified
        TestModeValidationException: If test mode configuration is invalid or missing required fields
        TestModeConfigurationNotAvailable: If test configuration file cannot be loaded
    """
    global _test_mode
    
    # Return cached instance if already loaded
    if _test_mode is not None:
        return _test_mode
    
    try:
        # Get mode name using strict detection logic
        if not mode_name:
            mode_name = get_mode_name()
        
        # Load configuration data
        # Load configuration data, preferring the app config override
        app_config_path = Path.cwd() / 'config' / 'tests.yaml'
        sdk_default_config_path = Path(__file__).parent.parent.parent / 'build' / 'config' / 'tests.yaml'

        if app_config_path.exists():
            config_path = app_config_path
            logger.debug(f"Using app config override for test config: {config_path}")
        elif sdk_default_config_path.exists():
            config_path = sdk_default_config_path
            logger.debug(f"Using SDK default test config: {config_path}")
        else:
            error_msg = f"Test configuration file not found. Looked for override at {app_config_path} and default at {sdk_default_config_path}"
            logger.error(f"Test mode loading failed: {error_msg}")
            raise TestModeConfigurationNotAvailable(error_msg)
        
        if not config_path.exists():
            error_msg = f"Test configuration file not found: {config_path}"
            logger.error(f"Test mode loading failed: {error_msg}")
            raise TestModeConfigurationNotAvailable(error_msg)
        
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            error_msg = f"Failed to load test configuration from {config_path}: {e}"
            logger.error(f"Test mode loading failed: {error_msg}")
            raise TestModeConfigurationNotAvailable(error_msg)
        
        logger.debug(f"Loading test mode configuration for: {mode_name}")
        
        # Load and cache the test mode config
        test_mode_config = _load_test_mode_config(mode_name, config_data)
        _test_mode = test_mode_config
        logger.debug(f"Successfully loaded test mode configuration: {mode_name}")
        return test_mode_config
            
    except (TestModeConfigurationNotAvailable, TestModeNotDetectedException, TestModeValidationException):
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        error_msg = f"Unexpected error loading test mode configuration: {e}"
        logger.error(f"Test mode loading failed: {error_msg}")
        raise TestModeConfigurationNotAvailable(error_msg)


def get_mode_name() -> str:
    """Get the current test mode name.
    
    PRINCIPLES ENFORCED:
    - Never returns None, empty string, or blank values
    - Never falls back to defaults
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    
    Returns:
        Test mode name string (never None/empty)
        
    Raises:
        TestModeNotDetectedException: If test mode cannot be definitively identified
    """
    # Check command line arguments for test suite
    import sys
    if '--suite' in sys.argv:
        try:
            mode_index = sys.argv.index('--suite')
            if mode_index + 1 < len(sys.argv):
                explicit_mode = sys.argv[mode_index + 1]
                if explicit_mode and explicit_mode.strip() and not explicit_mode.startswith('-'):
                    logger.debug(f"Using --suite argument: {explicit_mode}")
                    return explicit_mode.strip()
        except (ValueError, IndexError):
            pass
    
    # No auto-selectors - explicit mode required
    error_msg = "--suite command line argument must be set for test execution"
    logger.error(f"Test mode detection failed: {error_msg}")
    raise TestModeNotDetectedException(error_msg)


def is_test_mode() -> bool:
    """Check if test mode is available without throwing exceptions.
    
    This is a safe alternative to get_mode_name() for cases where
    you just want to check if test mode is available without
    requiring it to be set.
    
    Returns:
        True if test mode is available, False otherwise
    """
    try:
        get_mode_name()
        return True
    except TestModeNotDetectedException:
        return False


def _load_test_mode_config(mode_name: str, config_data: Dict[str, Any]) -> TestModeConfig:
    """Load TestModeConfig from configuration data.
    
    PRINCIPLES ENFORCED:
    - Never returns None or invalid configurations
    - Never falls back to defaults
    - Always throws strongly-typed exceptions on failure
    - Uses proper error logging at appropriate levels
    - Never suppresses exceptions inappropriately
    - Validates all required fields strictly
    
    Args:
        mode_name: Name of the test mode to load
        config_data: Loaded YAML configuration data
        
    Returns:
        TestModeConfig instance (never None)
        
    Raises:
        TestModeValidationException: If test mode not found or missing required fields
    """
    if 'modes' not in config_data:
        error_msg = "Test configuration file must contain 'modes' section"
        logger.error(f"Test mode validation failed: {error_msg}")
        raise TestModeValidationException(error_msg)
    
    if mode_name not in config_data['modes']:
        available_modes = list(config_data['modes'].keys())
        error_msg = f"Test mode '{mode_name}' not found. Available modes: {available_modes}"
        logger.error(f"Test mode validation failed: {error_msg}")
        raise TestModeValidationException(error_msg)
    
    mode_config = config_data['modes'][mode_name]
    logger.debug(f"Validating test mode configuration for: {mode_name}")
    
    # Validate required fields
    required_fields = [
        'in-memory-api',
        'default-env'
    ]
    
    for field in required_fields:
        if field not in mode_config:
            error_msg = f"Missing required field '{field}' in test mode '{mode_name}'"
            logger.error(f"Test mode validation failed: {error_msg}")
            raise TestModeValidationException(error_msg)
    
    # Create TestModeConfig instance
    return TestModeConfig(
        mode=mode_name,
        description=mode_config.get('description'),
        in_memory_api=mode_config['in-memory-api'],
        default_env=mode_config['default-env'],
        tests=mode_config.get('tests')
    )


def is_mode_available() -> bool:
    """Check if test mode configuration is available and can be loaded.
    
    NOTE: This function intentionally suppresses exceptions to provide
    a boolean check. This is the ONLY function that should suppress exceptions.
    
    Returns:
        True if test mode configuration can be loaded successfully, False otherwise.
    """
    try:
        get_mode()
        return True
    except Exception:
        return False


def get_api_url() -> str:
    """
    Get the API URL from environment variable or cloud services.
    
    This function:
    1. First tries to get API_TESTING_URL from environment variable
    2. If not available, checks if cloud is enabled and gets project_id
    3. Uses Google Cloud libraries to retrieve Cloud Run service URL
    4. Caches the result to avoid repeated network I/O
    
    PRINCIPLES ENFORCED:
    - Never returns defaults or fallbacks
    - Always returns a real, deterministic URL or throws a typed exception
    - Uses proper error logging at appropriate levels
    
    Returns:
        API URL string from environment variable or Cloud Run service
        
    Raises:
        APIConfigurationException: If no API URL can be determined from environment or cloud services
    """
    # Check cache first
    if hasattr(get_api_url, '_cached_url'):
        return get_api_url._cached_url
    
    # First try to get API_TESTING_URL from environment variable
    api_url = os.environ.get('API_TESTING_URL')
    if api_url and api_url.strip():
        # Cache the result
        get_api_url._cached_url = api_url.strip()
        return get_api_url._cached_url
    
    # If no API_TESTING_URL, check if cloud is enabled
    from .settings import is_cloud_enabled
    if is_cloud_enabled():
        # Safely get project ID
        from .settings import get_project_id
        project_id = get_project_id()
        
        # Use Google Cloud libraries to get Cloud Run service URL
        try:
            from google.cloud import run_v2
            client = run_v2.ServicesClient()
            
            # Get the Cloud Run service URL using configurable app ID
            from .settings import get_app_id
            app_id = get_app_id()
            service_name = f"projects/{project_id}/locations/us-central1/services/{app_id}-api"
            service = client.get_service(name=service_name)
            api_url = service.uri
            
            # Cache the result
            get_api_url._cached_url = api_url
            return api_url
            
        except Exception as e:
            error_msg = f"Failed to get Cloud Run service URL: {e}"
            logger.error(error_msg)
            raise APIConfigurationException(error_msg)
    
    # If we get here, we have no way to determine the API URL
    raise APIConfigurationException("No API_TESTING_URL environment variable set and cloud services not available")
