"""
Remote HTTP API client using requests library.

Used by API test suite for real network interface testing.
"""
import os
import requests
from .base_client import APITestClient
from .response import APIResponse
from multi_eden.run.config.providers import simple_provider_name


@simple_provider_name("HTTP")
class RemoteAPITestClient(APITestClient):
    """Remote HTTP API client using requests library.
    
    Used by API test suite for real network interface testing.
    """
    
    def __init__(self, base_url, auth_required=True):
        """Initialize with base URL for remote API.
        
        Args:
            base_url: Base URL for the remote API (e.g., http://localhost:8001)
            auth_required: Whether to include auth headers by default
        """
        self.base_url = base_url.rstrip('/')
        self.auth_required = auth_required
        
        if auth_required:
            # Get auth token for HTTP tests
            from multi_eden.run.auth.testing import get_static_test_user_token
            token_info = get_static_test_user_token()
            self.token = token_info['token']
    
    def get(self, path, headers=None):
        """Make GET request over HTTP."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        url = f"{self.base_url}{path}"
        response = requests.get(url, headers=headers)
        
        try:
            data = response.json()
        except:
            data = response.text
        
        # Return APIResponse object for consistency
        return APIResponse(
            status_code=response.status_code,
            data=data,
            headers=dict(response.headers)
        )
    
    def post(self, path, json=None, headers=None):
        """Make POST request over HTTP."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        url = f"{self.base_url}{path}"
        response = requests.post(url, json=json, headers=headers)
        
        try:
            data = response.json()
        except:
            data = response.text
        
        # Return APIResponse object for consistency
        return APIResponse(
            status_code=response.status_code,
            data=data,
            headers=dict(response.headers)
        )
    
    def delete(self, path, headers=None):
        """Make DELETE request over HTTP."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        url = f"{self.base_url}{path}"
        response = requests.delete(url, headers=headers)
        
        try:
            data = response.json()
        except:
            data = response.text
        
        # Return APIResponse object for consistency
        return APIResponse(
            status_code=response.status_code,
            data=data,
            headers=dict(response.headers)
        )
