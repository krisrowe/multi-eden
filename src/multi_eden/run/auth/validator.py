"""
Handles the core logic for validating tokens and authorizing users.
"""
import logging
import os
import jwt
import yaml
from firebase_admin import auth

from multi_eden.run.config.settings import get_setting
from .config import get_authorization_config
from . import NON_CLOUD_ENV_NAME, CUSTOM_AUTH_BASE_ISSUER
# Import config.mode here to avoid circular imports
from .exceptions import AuthenticationError, AuthorizationError, TokenExpiredError, TokenSignatureError, TokenMalformedError, TokenIssuerError

logger = logging.getLogger(__name__)

def _on_before_validate_custom_token(token: str):
    """Callback hook for when custom JWT validation is about to be performed."""
    pass

def _on_before_validate_firebase_token(token: str):
    """Callback hook for when Firebase token validation is about to be performed."""
    pass


def log_token_safely(token: str, context: str = "Token"):
    """Log token information safely, never failing regardless of token format."""
    try:
        # Log basic info that can't fail
        logger.debug(f"{context}: {len(token)} chars")
        
        # Try to get header, but don't fail if it's malformed
        try:
            header = jwt.get_unverified_header(token)
            logger.debug(f"  - Header: {header}")
        except Exception as e:
            logger.debug(f"  - Header: Failed to parse ({e})")
        
        # Try to get payload, but don't fail if it's malformed  
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            logger.debug(f"  - Payload: {payload}")
        except Exception as e:
            logger.debug(f"  - Payload: Failed to parse ({e})")
        
        # Try to get signature info, but don't fail if it's malformed
        try:
            parts = token.split('.')
            if len(parts) == 3:
                signature = parts[2]
                import hashlib
                signature_hash = hashlib.sha256(signature.encode()).hexdigest()[:16]
                logger.debug(f"  - Signature Hash: {signature_hash}")
            else:
                logger.debug(f"  - Signature: Invalid format ({len(parts)} parts)")
        except Exception as e:
            logger.debug(f"  - Signature: Failed to process ({e})")
            
    except Exception as e:
        # Token is completely unparseable - log safe info only
        logger.debug(f"{context}: Critical logging error: {e}")
        logger.debug(f"  - Token length: {len(token)} chars")
        try:
            # Hash the entire token as a fallback identifier
            import hashlib
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            logger.debug(f"  - Token hash: {token_hash}")
        except Exception:
            logger.debug(f"  - Token hash: Failed to generate")



def _is_firebase_issuer(issuer: str) -> bool:
    """Check if issuer matches Firebase ID token pattern."""
    return issuer and issuer.startswith("https://securetoken.google.com/")


def validate_token(token: str) -> dict:
    """
    Validates a token and returns the user claims if successful.
    
    Raises:
        AuthenticationError: If the token is invalid in any way.
    """
    logger.debug("\n--- AUTH DEBUG LOG ---")
    log_token_safely(token, "Validating Token")

    try:
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        issuer = unverified_claims.get('iss')

        logger.debug(f"  - Decoded Issuer: {issuer}")
        logger.debug(f"  - Unverified Claims: {unverified_claims}")

        # Path 1: Custom JWT Authentication
        # Import provider configuration here to avoid circular imports
        from multi_eden.run.config.providers import is_custom_auth_enabled
        custom_issuer = CUSTOM_AUTH_BASE_ISSUER
        if (issuer == custom_issuer):
            if is_custom_auth_enabled():
                jwt_key = get_setting('jwt-secret-key')
                logger.debug(f"  - Validator Path: Custom JWT")
                logger.debug(f"  - Expected Issuer: {custom_issuer}")
                logger.debug(f"  - Retrieved JWT key (first 8 chars): {jwt_key[:8]}...")

                # Callback hook for testing
                _on_before_validate_custom_token(token) 

                # The library handles the issuer check internally 
                return jwt.decode(token, jwt_key, algorithms=["HS256"], issuer=custom_issuer)
            else:
                raise AuthenticationError("Custom auth is disabled, but token is a custom token.")
        
        # Path 2: Firebase Authentication
        elif _is_firebase_issuer(issuer):
            logger.debug(f"  - Validator Path: Firebase")
            logger.debug(f"  - Firebase Issuer: {issuer}")
            return auth.verify_id_token(token, clock_skew_seconds=10)
        
        # Path 3: Unrecognized issuer
        else:
            raise AuthenticationError(
                f"Unrecognized token issuer: '{issuer}'. "
                f"Expected custom issuer '{custom_issuer}' or Firebase issuer 'https://securetoken.google.com/<project-id>'"
            )

    except (jwt.InvalidTokenError, auth.InvalidIdTokenError, ValueError) as e:
        logger.debug(f"  - ERROR: Token validation failed: {e}")
        
        # Map specific JWT errors to appropriate custom exceptions
        if isinstance(e, jwt.ExpiredSignatureError):
            raise TokenExpiredError(f"Token has expired: {e}")
        elif isinstance(e, jwt.InvalidSignatureError):
            raise TokenSignatureError(f"Token has invalid signature: {e}")
        elif isinstance(e, jwt.DecodeError):
            raise TokenMalformedError(f"Token is malformed: {e}")
        elif isinstance(e, jwt.InvalidIssuerError):
            raise TokenIssuerError(f"Token has invalid issuer: {e}")
        else:
            # For other JWT errors or ValueError, raise generic AuthenticationError
            raise AuthenticationError(f"Invalid token: {e}")
    
    except Exception as e:
        logger.debug(f"  - ERROR: An unexpected error occurred during validation: {e}")
        raise AuthenticationError(f"An unexpected error occurred: {e}")


def authorize_user(email: str):
    """
    Checks if a user is authorized based on configuration.
    
    If all_authenticated_users is True, any authenticated user is allowed.
    Otherwise, checks if the user's email is in the allowed list.
    
    Raises:
        AuthorizationError: If the user is not authorized.
    """
    try:
        # Get authorization configuration
        authorization = get_authorization_config()
        
        # If all authenticated users are allowed, skip email check
        if authorization.all_authenticated_users:
            return
        
        # Otherwise, check against allowed emails list
        allowed_emails = authorization.allowed_user_emails
        if email in allowed_emails:
            return
        else:
            raise AuthorizationError(f"User {email} is not authorized.")
    except Exception as e:
        raise AuthorizationError(f"Could not determine user authorization: {e}")
