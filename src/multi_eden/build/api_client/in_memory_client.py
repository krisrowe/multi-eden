"""
In-memory API client using FastAPI TestClient.

Used by unit and integration test suites for fast, isolated testing.
"""
from .base_client import APITestClient
from .response import APIResponse
from multi_eden.run.config.providers import simple_provider_name


@simple_provider_name("In Memory")
class InMemoryAPITestClient(APITestClient):
    """In-memory API client using FastAPI TestClient.
    
    Used by unit and integration test suites for fast, isolated testing.
    """
    
    def __init__(self, fastapi_client, auth_required=True):
        """Initialize with FastAPI TestClient instance.
        
        Args:
            fastapi_client: FastAPI TestClient instance
            auth_required: Whether to include auth headers by default
        """
        self.client = fastapi_client
        self.auth_required = auth_required
        
        if auth_required:
            # Get auth token for in-memory tests
            from multi_eden.run.auth.testing import get_static_test_user_token
            token_info = get_static_test_user_token()
            self.token = token_info['token']
    
    def get(self, path, headers=None):
        """Make GET request using FastAPI TestClient."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        response = self.client.get(path, headers=headers)
        
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
        """Make POST request using FastAPI TestClient."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        response = self.client.post(path, json=json, headers=headers)
        
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
        """Make DELETE request using FastAPI TestClient."""
        if headers is None and self.auth_required:
            headers = {'Authorization': f'Bearer {self.token}'}
        
        response = self.client.delete(path, headers=headers)
        
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
