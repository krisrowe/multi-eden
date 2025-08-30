"""
Test user management utilities for Firebase Authentication.

This module contains functions specifically for managing test users,
while leveraging the general-purpose authentication utilities from util.py.
"""

import logging
from .util import (
    gen_token,
    ensure_firebase_user_exists,
    AUTH_SOURCE_CUSTOM,
    AUTH_SOURCE_FIREBASE
)

from multi_eden.run.config.settings import get_setting

# Static Test User Email (used across all test suites)
STATIC_TEST_USER_EMAIL = f"test-user@static.{get_setting('app-id')}.app"

# Module-level cache for Firebase tokens to avoid redundant API calls
# Only cache Firebase tokens since custom tokens are generated locally (fast)
_firebase_token_cache = None

def get_static_test_user_token():
    """
    Gets a token for the single, known static test user.

    This is the primary entry point for local development tools like `make web-start`.
    It checks if custom auth is enabled and returns either a custom-signed JWT
    or a real Firebase ID token for the same, consistent user email.
    
    For Firebase tokens, uses a module-level cache to avoid redundant API calls.
    
    Returns:
        dict: JSON structure with meta (source, hash) and token
    """
    global _firebase_token_cache
    
    # Import config.mode here to avoid circular imports
    from multi_eden.run.config.providers import is_custom_auth_enabled
    
    if is_custom_auth_enabled():
        # Custom tokens are generated locally (fast) - no need to cache
        token = gen_token(STATIC_TEST_USER_EMAIL)
        source = AUTH_SOURCE_CUSTOM
    else:
        # Check cache first for Firebase tokens (avoid expensive API calls)
        if _firebase_token_cache is not None:
            logger = logging.getLogger(__name__)
            logger.debug("Using cached Firebase token for static test user")
            return _firebase_token_cache
        
        # Get a real Firebase token for the static user
        auth_info = ensure_firebase_user_exists(
            email=STATIC_TEST_USER_EMAIL,
            get_token=True
        )
        token = auth_info['id_token']
        source = AUTH_SOURCE_FIREBASE

    # Calculate token hash for debugging/validation
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    
    result = {
        "meta": {
            "email": STATIC_TEST_USER_EMAIL,
            "source": source,
            "hash": token_hash
        },
        "token": token
    }
    
    # Cache Firebase tokens to avoid redundant API calls
    if source == AUTH_SOURCE_FIREBASE:
        _firebase_token_cache = result
    
    # Always log the auth source being used
    logger = logging.getLogger(__name__)
    logger.info(f"🔑 Generated token using: {source}")
    
    # Debug output for token generation (controlled by environment variable)
    try:
        import os
        if os.getenv('DEBUG_TOKEN_GENERATION', 'false').lower() == 'true':
            logger.info("🔍 TOKEN DEBUG INFO:")
            logger.info(f"   Source: {source}")
            logger.info(f"   Hash: {token_hash}")
            logger.info(f"   Token Length: {len(token)}")
            logger.info(f"   Cached: {source == AUTH_SOURCE_FIREBASE}")
            
            if source == AUTH_SOURCE_FIREBASE:
                # For Firebase tokens, show basic info (can't decode without secret)
                logger.info("   Firebase Token Type: ID Token")
                logger.info("   Note: Firebase ID tokens are signed and require the project's private key to decode")
            elif source == AUTH_SOURCE_CUSTOM:
                # For custom JWT tokens, we can decode them
                try:
                    import jwt
                    # Decode without verification to see payload
                    decoded = jwt.decode(token, options={"verify_signature": False})
                    logger.info("   Custom JWT Payload:")
                    for key, value in decoded.items():
                        if key in ['exp', 'iat', 'nbf']:
                            # Convert timestamps to readable format
                            from datetime import datetime
                            dt = datetime.fromtimestamp(value)
                            logger.info(f"     {key}: {dt.isoformat()}")
                        else:
                            logger.info(f"     {key}: {value}")
                except ImportError:
                    logger.info("   Custom JWT (PyJWT not available for decoding)")
                except Exception as e:
                    logger.info(f"   Custom JWT (Error decoding: {e})")
            
            logger.info("   End Token Debug")
    except Exception as e:
        # Don't let debug output break the main function
        pass
    
    return result

def _clear_firebase_token_cache():
    """
    Clear the cached Firebase token.
    
    This should be called whenever the static test user is deleted or recreated
    to ensure we don't use stale tokens.
    """
    global _firebase_token_cache
    _firebase_token_cache = None
    logger = logging.getLogger(__name__)
    logger.debug("Cleared Firebase token cache")

def delete_static_test_user():
    """
    Delete the static test user from Firebase Authentication.
    
    This is useful when the password generation logic changes (e.g., salt changes)
    and the existing user can no longer authenticate with the new password.
    
    Returns:
        bool: True if user was deleted or didn't exist, False if deletion failed
    """
    logger = logging.getLogger(__name__)
    
    try:
        import firebase_admin
        from firebase_admin import auth, credentials
        # Initialize Firebase Admin SDK if not already done
        if not firebase_admin._apps:
            # For now, we'll use environment variables since Firebase config isn't in our new config yet
            import os
            service_account_info = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY')
            if not service_account_info:
                raise ValueError("FIREBASE_SERVICE_ACCOUNT_KEY environment variable is required")
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
        
        # Try to get user by email
        try:
            user = auth.get_user_by_email(STATIC_TEST_USER_EMAIL)
            logger.info(f"Found existing static test user: {user.uid} ({user.email})")
            
            # Delete the user
            auth.delete_user(user.uid)
            logger.info(f"✅ Successfully deleted static test user: {STATIC_TEST_USER_EMAIL}")
            
            # Clear cached token since user was deleted
            _clear_firebase_token_cache()
            return True
            
        except auth.UserNotFoundError:
            logger.info(f"ℹ️  Static test user {STATIC_TEST_USER_EMAIL} not found in Firebase - nothing to delete")
            
            # Clear cached token just in case
            _clear_firebase_token_cache()
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to delete static test user {STATIC_TEST_USER_EMAIL}: {e}")
        return False

def ensure_static_firebase_test_user():
    """
    Ensure the static Firebase test user exists and can authenticate successfully.
    
    If authentication fails, automatically recreate the user and try again.
    This is useful for Firestore tests that need working Firebase authentication.
    
    Returns:
        dict: Token info if successful, None if failed after recreation attempt
    """
    logger = logging.getLogger(__name__)
    
    logger.info("🔍 Ensuring static Firebase test user exists and can authenticate...")
    
    # First attempt: try to get token with existing user
    try:
        token_info = get_static_test_user_token()
        logger.info("✅ Static Firebase test user authentication successful")
        return token_info
        
    except Exception as first_error:
        logger.warning(f"⚠️  Static Firebase test user authentication failed: {first_error}")
        logger.info("🔄 Attempting to recreate static Firebase test user...")
        
        # Recreate user and try again
        recreated_token = recreate_static_test_user()
        if recreated_token:
            logger.info("✅ Static Firebase test user recreated and authenticated successfully")
            return recreated_token
        else:
            logger.error("❌ Failed to recreate and authenticate static Firebase test user")
            return None

def recreate_static_test_user():
    """
    Recreate the static test user by deleting the existing one and creating a new one.
    
    This is the main function for fixing authentication issues when password logic changes.
    
    Returns:
        dict: Token info if successful, None if failed
    """
    logger = logging.getLogger(__name__)
    
    logger.info("🔄 Recreating static test user...")
    
    # Clear any cached token before recreation
    _clear_firebase_token_cache()
    
    # Step 1: Delete existing user
    if not delete_static_test_user():
        logger.error("❌ Failed to delete existing static test user")
        return None
    
    # Step 2: Create new user with current password logic
    try:
        token_info = get_static_test_user_token()
        logger.info(f"✅ Successfully recreated static test user:")
        logger.info(f"   Email: {token_info['meta'].get('email', 'N/A')}")
        logger.info(f"   Source: {token_info['meta']['source']}")
        logger.info(f"   Token length: {len(token_info['token'])} chars")
        return token_info
        
    except Exception as e:
        logger.error(f"❌ Failed to recreate static test user: {e}")
        return None
