"""
Generic API response wrapper for API clients.

Provides consistent interface regardless of underlying HTTP library.
"""
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class APIResponse:
    """Unified response wrapper for both in-memory and HTTP API clients.
    
    This provides a consistent interface regardless of underlying HTTP library.
    """
    status_code: int
    data: Any
    headers: Dict[str, str]
    
    def json(self):
        """Return the response data (for compatibility with FastAPI Response)."""
        return self.data
    
    @property
    def text(self):
        """Return the response data as text if it's a string."""
        if isinstance(self.data, str):
            return self.data
        return str(self.data)
