"""
Testing-related configuration validators.

This module provides validators for testing-specific configuration requirements,
such as remote API testing validation.
"""

from typing import Dict
from .base import BaseValidator
from multi_eden.build.config.exceptions import RemoteApiTestingException
from ..models import StagedVariable, LoadParams


class RemoteApiTestingValidator(BaseValidator):
    """Validator for remote API testing configuration.
    
    This validator ensures that when TEST_API_MODE=REMOTE is set, the required
    target configuration variables are available to build the API URL.
    """
    
    def validate(self, staged_vars: Dict[str, StagedVariable], 
                params: LoadParams) -> None:
        """Validate that remote API testing has required configuration.
        
        Only validates if TEST_API_MODE=REMOTE is set. If not set, quietly returns.
        
        Args:
            staged_vars: Dictionary of staged environment variables with metadata
            params: Load parameters providing context for validation
            
        Raises:
            RemoteApiTestingException: If TEST_API_MODE=REMOTE but required vars missing
        """
        # Only validate if TEST_API_MODE=REMOTE is set
        test_api_mode_var = staged_vars.get('TEST_API_MODE')
        test_api_mode = test_api_mode_var.value if test_api_mode_var else None
        if test_api_mode != 'REMOTE':
            return  # Not doing remote API testing, no validation needed
        
        # Check for explicit TEST_API_URL first
        if 'TEST_API_URL' in staged_vars:
            return  # Explicit URL provided, no further validation needed
        
        # Check for local testing configuration
        local_var = staged_vars.get('LOCAL')
        local_value = local_var.value if local_var else None
        if local_value and local_value.lower() == 'true':
            return  # Local testing configured, no further validation needed
        
        # Check for cloud testing configuration
        project_id_var = staged_vars.get('PROJECT_ID')
        project_id = project_id_var.value if project_id_var else None
        app_id_var = staged_vars.get('APP_ID')
        app_id = app_id_var.value if app_id_var else None
        
        if project_id and app_id:
            return  # Cloud config available
        
        # If we get here, we're missing required configuration
        missing_vars = []
        if not project_id:
            missing_vars.append('PROJECT_ID')
        if not app_id:
            missing_vars.append('APP_ID')
        
        # Use LoadParams for better context
        profile_name = params.base_layer or params.top_layer
        raise RemoteApiTestingException(
            f"Remote API testing requires target configuration (from profile '{profile_name}')",
            missing_vars=missing_vars,
            profile_name=profile_name
        )

