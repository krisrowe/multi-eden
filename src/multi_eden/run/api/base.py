"""
Base API class for Multi-Eden applications.

Provides standard health check, system info, authentication, and user endpoints.
"""

import os
import secrets
from typing import Dict, Any

from fastapi import FastAPI, Response, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse


class BaseAPI:
    """Base API class with standard Multi-Eden endpoints."""
    
    def __init__(self):
        """Initialize the base API."""
        self.app = FastAPI(
            title="Multi-Eden Application",
            description="Built with Multi-Eden SDK",
            version="1.0.0"
        )
        self._instance_id = self._generate_instance_id()
        self._security = HTTPBearer(auto_error=False)
        self._setup_base_routes()
    
    def _generate_instance_id(self) -> str:
        """Generate a unique instance ID for this service instance."""
        return secrets.token_hex(16)  # 32 hex characters for uniqueness
    
    def _setup_base_routes(self):
        """Set up base health and system routes."""
        
        # Create dependency functions that can access self
        async def get_authenticated_user(credentials: HTTPAuthorizationCredentials = Depends(self._security)):
            return await self._get_authenticated_user(credentials)
        
        async def get_authorized_user(user_claims: dict = Depends(get_authenticated_user)):
            return await self._get_authorized_user(user_claims)
        
        @self.app.get('/health')
        async def health_check():
            """Health check endpoint that includes instance ID for in-memory validation."""
            # Add instance ID header for in-memory validation
            response = Response(content='{"status": "healthy"}', media_type="application/json")
            response.headers['x-instance-id'] = self._instance_id
            return response
        
        @self.app.get('/api/system')
        async def get_system_info():
            """Returns hashed system configuration for debugging and testing."""
            return self._get_system_info()
        
        @self.app.get('/api/user')
        async def get_user(user_claims: dict = Depends(get_authenticated_user)):
            """Returns the authenticated user's information."""
            try:
                from multi_eden.run.auth.util import detect_auth_method
                auth_method = detect_auth_method(user_claims.get("iss", ""))
            except ImportError:
                auth_method = "unknown"
            
            return {
                "uid": user_claims.get("uid") or user_claims.get("sub"),
                "email": user_claims.get("email"),
                "authorized": True,
                "name": user_claims.get("name"),
                "auth_method": auth_method
            }
        
        # Store dependency functions for subclass access
        self.get_authenticated_user = get_authenticated_user
        self.get_authorized_user = get_authorized_user
    
    def _get_system_info(self) -> Dict[str, str]:
        """Get hashed system configuration information."""
        try:
            # Get current providers
            from multi_eden.run.config.providers import is_custom_auth_enabled, is_ai_mocked
            
            auth_provider_name = "custom" if is_custom_auth_enabled() else "firebase"
            
            # Try to get data provider info (may not be available in all apps)
            try:
                from multi_eden.run.config.providers import get_data_provider_stub_mode
                data_provider_name = "TinyDBDataProvider" if get_data_provider_stub_mode() else "FirebaseDataProvider"
            except (ImportError, AttributeError):
                data_provider_name = "unknown"
            
            # Check if AI model is mocked
            ai_mocked = is_ai_mocked()
            ai_client_type = "MockGeminiClient" if ai_mocked else "GeminiClient"
            
            # Get project info
            project_id = os.getenv('PROJECT_ID', 'unknown-project')
            
            return {
                "SYS_AP": self._hash_value(auth_provider_name),
                "SYS_DP": self._hash_value(data_provider_name),
                "SYS_MP": self._hash_value(ai_client_type),
                "SYS_ENV": self._hash_value(project_id)
            }
        except Exception as e:
            # Fallback for apps that don't use all Multi-Eden features
            return {
                "SYS_AP": self._hash_value("unknown"),
                "SYS_DP": self._hash_value("unknown"),
                "SYS_MP": self._hash_value("unknown"),
                "SYS_ENV": self._hash_value("unknown")
            }
    
    def _hash_value(self, value: str) -> str:
        """Hash a value with the system salt."""
        try:
            from multi_eden.run.auth.util import compute_system_info_hash
            return compute_system_info_hash(value)
        except Exception:
            # Fallback hash if auth utils not available
            import hashlib
            return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    async def _get_authenticated_user(self, credentials: HTTPAuthorizationCredentials):
        """
        FastAPI dependency to handle authentication only (no authorization).
        
        Used for endpoints like /api/user that need to know who the user is
        but don't require authorization checks.
        """
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        token = credentials.credentials
        try:
            from multi_eden.run.auth.validator import validate_token
            from multi_eden.run.auth.exceptions import AuthenticationError
            
            user_claims = validate_token(token)
            return user_claims
            
        except (ImportError, AuthenticationError) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
    
    async def _get_authorized_user(self, user_claims: dict):
        """
        FastAPI dependency to handle authorization (requires authentication first).
        
        Reuses _get_authenticated_user and adds authorization checks.
        Used for endpoints that require both authentication and authorization.
        """
        try:
            from multi_eden.run.auth.validator import authorize_user
            from multi_eden.run.auth.exceptions import AuthorizationError
            
            authorize_user(user_claims.get('email'))
            return user_claims
            
        except (ImportError, AuthorizationError) as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
