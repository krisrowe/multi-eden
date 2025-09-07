"""
In-memory API client using FastAPI TestClient.

Used by unit and integration test suites for fast, isolated testing.
This is a generic, reusable client that doesn't know about specific auth frameworks.
"""
from .base_client import APITestClient
from .response import APIResponse


class InMemoryAPITestClient(APITestClient):
    """In-memory API client using FastAPI TestClient.
    
    Used by unit and integration test suites for fast, isolated testing.
    This is a generic, reusable client that doesn't know about specific auth frameworks.
    """
    
    def __init__(self, fastapi_client, default_headers=None):
        """Initialize with FastAPI TestClient instance.
        
        Args:
            fastapi_client: FastAPI TestClient instance
            default_headers: Optional default headers to include in all requests
        """
        self.client = fastapi_client
        self.default_headers = default_headers or {}
    
    def get(self, path, headers=None):
        """Make GET request using FastAPI TestClient."""
        # Merge default headers with request-specific headers
        merged_headers = {**self.default_headers}
        if headers:
            merged_headers.update(headers)
        
        response = self.client.get(path, headers=merged_headers)
        
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
        # Merge default headers with request-specific headers
        merged_headers = {**self.default_headers}
        if headers:
            merged_headers.update(headers)
        
        response = self.client.post(path, json=json, headers=merged_headers)
        
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
        # Merge default headers with request-specific headers
        merged_headers = {**self.default_headers}
        if headers:
            merged_headers.update(headers)
        
        response = self.client.delete(path, headers=merged_headers)
        
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
