"""
API tests using InMemoryAPITestClient.

Tests actual HTTP API endpoints using FastAPI TestClient for in-memory testing.
This tests the real API layer and HTTP request/response handling.
"""

import os
import unittest
from fastapi.testclient import TestClient
from multi_eden.build.api_client import InMemoryAPITestClient
from multi_eden.run.api.base import BaseAPI


class TestAPIEndpoints(unittest.TestCase):
    """Test actual API endpoints using in-memory FastAPI TestClient."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class - environment loading handled by pytest plugin."""
        # Create a BaseAPI instance for testing
        cls.api = BaseAPI()
        cls.app = cls.api.app

        # Create FastAPI TestClient
        cls.test_client = TestClient(cls.app)

        # Create our API test client wrapper (no default auth headers)
        cls.api_client = InMemoryAPITestClient(cls.test_client)
        
        # Create auth client with test token for authenticated requests
        from multi_eden.run.auth.testing import get_static_test_user_token
        token_info = get_static_test_user_token()
        auth_headers = {'Authorization': f'Bearer {token_info["token"]}'}
        cls.auth_client = InMemoryAPITestClient(cls.test_client, default_headers=auth_headers)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.api_client.get('/health')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'healthy')
        
        # Check for instance ID header (for in-memory validation)
        self.assertIn('x-instance-id', response.headers)
        self.assertTrue(len(response.headers['x-instance-id']) > 0)
    
    def test_system_info_endpoint(self):
        """Test system info endpoint."""
        response = self.api_client.get('/api/system')
        
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, dict)
        
        # Should contain hashed system configuration info
        self.assertIn('SYS_AP', response.data)  # Auth Provider hash
        self.assertIn('SYS_DP', response.data)  # Data Provider hash
        self.assertIn('SYS_MP', response.data)  # AI Model Provider hash
        self.assertIn('SYS_ENV', response.data) # Environment hash
    
    def test_user_endpoint_without_auth(self):
        """Test user endpoint without authentication (should fail)."""
        # Use client with no default auth headers
        response = self.api_client.get('/api/user')
        
        # Should return 401 or 403 for missing auth
        self.assertIn(response.status_code, [401, 403])
    
    def test_user_endpoint_with_auth(self):
        """Test user endpoint with authentication."""
        # Use client with default auth headers
        response = self.auth_client.get('/api/user')
        
        # Should succeed with valid auth token
        self.assertEqual(response.status_code, 200)
        self.assertIn('uid', response.data)
        self.assertIn('email', response.data)
        self.assertIn('authorized', response.data)
        self.assertTrue(response.data['authorized'])
    
    def test_nonexistent_endpoint(self):
        """Test non-existent endpoint returns 404."""
        response = self.api_client.get('/api/nonexistent')
        
        self.assertEqual(response.status_code, 404)
    
    def test_api_response_structure(self):
        """Test that APIResponse objects have expected structure."""
        response = self.api_client.get('/health')
        
        # Check APIResponse object structure
        self.assertIsNotNone(response.status_code)
        self.assertIsNotNone(response.data)
        self.assertIsNotNone(response.headers)
        self.assertIsInstance(response.headers, dict)
    
    def test_post_request_structure(self):
        """Test POST request handling."""
        # Test with a simple POST to a non-existent endpoint
        response = self.api_client.post('/api/test', json={'test': 'data'})
        
        # Should get 404 for non-existent endpoint, but structure should be correct
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(response.data)
        self.assertIsNotNone(response.headers)
    
    def test_delete_request_structure(self):
        """Test DELETE request handling."""
        # Test with a simple DELETE to a non-existent endpoint
        response = self.api_client.delete('/api/test')
        
        # Should get 404 for non-existent endpoint, but structure should be correct
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(response.data)
        self.assertIsNotNone(response.headers)
    
    def test_http_methods(self):
        """Test different HTTP methods work correctly."""
        # Test GET
        get_response = self.api_client.get('/health')
        self.assertEqual(get_response.status_code, 200)
        
        # Test POST
        post_response = self.api_client.post('/api/test', json={'method': 'POST'})
        self.assertEqual(post_response.status_code, 404)  # Endpoint doesn't exist
        
        # Test DELETE
        delete_response = self.api_client.delete('/api/test')
        self.assertEqual(delete_response.status_code, 404)  # Endpoint doesn't exist
    
    def test_json_request_response(self):
        """Test JSON request/response handling."""
        # Test sending JSON data
        response = self.api_client.post('/api/test', json={
            'test_key': 'test_value',
            'number': 42,
            'boolean': True
        })
        
        # Should get 404 but JSON should be processed correctly
        self.assertEqual(response.status_code, 404)
        self.assertIsNotNone(response.data)
    
    def test_headers_handling(self):
        """Test custom headers are handled correctly."""
        custom_headers = {'X-Test-Header': 'test-value', 'Content-Type': 'application/json'}
        
        response = self.api_client.get('/health', headers=custom_headers)
        
        self.assertEqual(response.status_code, 200)
        # Headers should be processed (though we can't easily verify custom headers in response)
        self.assertIsNotNone(response.headers)


if __name__ == '__main__':
    unittest.main()