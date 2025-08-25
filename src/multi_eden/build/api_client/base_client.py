"""
Base API client abstract class for testing.

Provides consistent interface regardless of whether tests run in-memory or over HTTP.
"""
from abc import ABC, abstractmethod


class APITestClient(ABC):
    """Abstract base class for API testing clients.
    
    Provides consistent interface regardless of whether tests run in-memory or over HTTP.
    """
    
    @abstractmethod
    def get(self, path, headers=None):
        """Make GET request to API endpoint."""
        pass
    
    @abstractmethod
    def post(self, path, json=None, headers=None):
        """Make POST request to API endpoint."""
        pass
    
    @abstractmethod
    def delete(self, path, headers=None):
        """Make DELETE request to API endpoint."""
        pass
