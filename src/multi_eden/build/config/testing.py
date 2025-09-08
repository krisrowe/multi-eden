"""
Testing utilities for configuration and API testing.
"""
import os
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


def get_test_api_url() -> List[Tuple[str, str, str]]:
    """Get the test API URL based on current environment configuration.
    
    Only returns a URL when:
    - TEST_API_MODE=REMOTE (API tests need external server)
    - TEST_API_URL is not already set (don't override explicit values)
    
    Returns:
        list: List of (var_name, var_value, var_source) tuples
    """
    # Only inject if API tests need external server
    if os.getenv('TEST_API_MODE', '') != 'REMOTE':
        return []
    
    # Don't override explicit TEST_API_URL
    if os.getenv('TEST_API_URL'):
        return []
    
    # Build API URL from available environment variables
    api_url = _build_api_url_from_env()
    
    if api_url:
        return [('TEST_API_URL', api_url, 'testing-utility')]
    
    return []


def _build_api_url_from_env() -> Optional[str]:
    """Build API URL from environment variables.
    
    Returns:
        str: API URL if buildable, None otherwise
    """
    # Local development
    if os.getenv('TARGET_LOCAL', '').lower() == 'true':
        port = os.getenv('TARGET_PORT') or os.getenv('PORT', '8000')
        if port and port != '80':
            return f'http://localhost:{port}'
        else:
            return 'http://localhost'
    
    # Cloud environment - construct Cloud Run URL
    target_project_id = os.getenv('TARGET_PROJECT_ID')
    if target_project_id:
        target_app_id = os.getenv('TARGET_APP_ID')
        if target_app_id:
            try:
                from multi_eden.internal.gcp import get_cloud_run_service_url
                service_name = f'{target_app_id}-api'
                region = os.getenv('TARGET_GCP_REGION', 'us-central1')
                return get_cloud_run_service_url(target_project_id, service_name, region)
            except Exception as e:
                logger.warning(f'Could not get Cloud Run URL via API: {e}')
                # Could add fallback URL construction here if needed
    
    # Fallback to PROJECT_ID/APP_ID (non-side-loaded)
    project_id = os.getenv('PROJECT_ID')
    if project_id:
        app_id = os.getenv('APP_ID')
        if app_id:
            try:
                from multi_eden.internal.gcp import get_cloud_run_service_url
                service_name = f'{app_id}-api'
                region = os.getenv('GCP_REGION', 'us-central1')
                return get_cloud_run_service_url(project_id, service_name, region)
            except Exception as e:
                logger.warning(f'Could not get Cloud Run URL via API: {e}')
    
    return None


def validate_remote_api_testing_config(staged_vars: dict, profile_name: str = None) -> None:
    """Validate that remote API testing has required configuration.
    
    Args:
        staged_vars: Dictionary of staged environment variables
        profile_name: Name of the profile that triggered validation (for guidance)
        
    Raises:
        RemoteApiTestingException: If TEST_API_MODE=REMOTE but required vars missing
    """
    from multi_eden.build.config.exceptions import RemoteApiTestingException
    
    # Check if we're in remote API testing mode
    test_api_mode = staged_vars.get('TEST_API_MODE', [None])[0] if 'TEST_API_MODE' in staged_vars else None
    if test_api_mode != 'REMOTE':
        return  # Not in remote mode, no validation needed
    
    # Check for required variables for remote API testing
    missing_vars = []
    
    # Check for explicit TEST_API_URL first
    if 'TEST_API_URL' in staged_vars:
        return  # Explicit URL provided, no further validation needed
    
    # Check for local testing configuration
    target_local = staged_vars.get('TARGET_LOCAL', [None])[0] if 'TARGET_LOCAL' in staged_vars else None
    if target_local and target_local.lower() == 'true':
        return  # Local testing configured, no further validation needed
    
    # Check for cloud testing configuration
    target_project_id = staged_vars.get('TARGET_PROJECT_ID', [None])[0] if 'TARGET_PROJECT_ID' in staged_vars else None
    target_app_id = staged_vars.get('TARGET_APP_ID', [None])[0] if 'TARGET_APP_ID' in staged_vars else None
    
    if not target_project_id:
        missing_vars.append('TARGET_PROJECT_ID')
    if not target_app_id:
        missing_vars.append('TARGET_APP_ID')
    
    # If we have cloud config, we're good
    if target_project_id and target_app_id:
        return
    
    # Check fallback to non-side-loaded variables
    project_id = staged_vars.get('PROJECT_ID', [None])[0] if 'PROJECT_ID' in staged_vars else None
    app_id = staged_vars.get('APP_ID', [None])[0] if 'APP_ID' in staged_vars else None
    
    if project_id and app_id:
        return  # Fallback config available
    
    # If we get here, we're missing required configuration
    if missing_vars:
        raise RemoteApiTestingException(
            f"Remote API testing requires target configuration but missing: {', '.join(missing_vars)}",
            missing_vars=missing_vars,
            profile_name=profile_name
        )


def create_remote_api_testing_validator(profile_name: str = None):
    """Create a validation callback that includes profile context.
    
    Args:
        profile_name: Name of the profile that will trigger validation
        
    Returns:
        callable: Validation callback function
    """
    def validator(staged_vars: dict) -> None:
        return validate_remote_api_testing_config(staged_vars, profile_name)
    
    return validator
