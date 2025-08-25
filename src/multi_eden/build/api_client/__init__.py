"""
API Client package for testing.

Provides consistent interface across unit, integration, and API test suites.
"""

from .base_client import APITestClient
from .in_memory_client import InMemoryAPITestClient
from .remote_client import RemoteAPITestClient
from .response import APIResponse

__all__ = [
    'APITestClient',
    'InMemoryAPITestClient', 
    'RemoteAPITestClient',
    'APIResponse'
]
