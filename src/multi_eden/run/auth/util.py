#!/usr/bin/env python3
"""
Authentication utilities.

Provides functions for token validation, user authentication, and authorization.
"""
import json
import jwt
import subprocess
import time
import hashlib
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import logging

import firebase_admin
from firebase_admin import auth, credentials

from multi_eden.run.config.settings import get_setting
from .exceptions import AuthenticationError, AuthorizationError
from . import NON_CLOUD_ENV_NAME, get_custom_auth_base_issuer

# Add the new import for gen_jwt_key
import secrets

logger = logging.getLogger(__name__)

# ============================================================================ #
# Centralized Hash Helper
# ============================================================================ #

def compute_hash(value: str, length: int = 16) -> str:
    """
    Compute a hash using SHA256 with the system salt from values.json.
    
    This is the centralized method for all hash computations in the auth system.
    The salt is always read from the same place (values.json) for consistency.
    
    Args:
        value: The value to hash (should already include any needed string combinations)
        length: Length of the hash to return (default: 16 characters)
        
    Returns:
        str: Hex digest of the specified length
    """
    jwt_key = get_setting('jwt-secret-key')
    combined = f"{value}-{jwt_key}"
    return hashlib.sha256(combined.encode()).hexdigest()[:length]

def compute_token_hash(token: str) -> str:
    """
    Compute hash for token identification.
    
    Args:
        token: The token to hash
        
    Returns:
        str: Hex digest of 8 characters (standard for token identification)
    """
    return compute_hash(token, length=8)

def compute_password_hash(project_id: str, email: str) -> str:
    """
    Compute deterministic password hash for Firebase test users.
    
    Args:
        project_id: The GCP project ID
        email: The user email
        
    Returns:
        str: Hex digest of 16 characters (standard for Firebase passwords)
        
    Note: This is deterministic - same inputs always produce same password.
    If any input changes, the password will be different and authentication will fail.
    """
    combined_value = f"{project_id}-{email}"
    return compute_hash(combined_value, length=16)

def compute_system_info_hash(value: str) -> str:
    """
    Compute hash for system info validation (auth providers, data providers, etc.).
    
    Args:
        value: The value to hash (e.g., "custom", "firebase", "TinyDBDataProvider")
        
    Returns:
        str: Hex digest of 16 characters (standard for system info hashes)
    """
    return compute_hash(value, length=16)

# ============================================================================ #
# Authentication Source Constants
# ============================================================================ #

AUTH_SOURCE_CUSTOM = "auth.rowe360.com"
AUTH_SOURCE_FIREBASE = "firebase"

# ============================================================================ #
# Main Public Functions
# ============================================================================ #

# This function has been removed - use config.mode.custom_auth_enabled instead

def gen_token_using_dates(email: str, issuer: str = None, expiration_datetime: datetime = None, issued_at: datetime = None):
    """
    Generates a custom-signed JWT with absolute expiration and issue times.

    This token is self-contained and includes an issuer claim that identifies it
    as a custom token for the application. It is signed with the
    environment-specific salt, making it verifiable by our own API w/o Firebase.
    
    Security is maintained through environment-specific salts rather than
    complex project_id alignment across server and client processes.
    
    Args:
        email: User email address
        issuer: JWT issuer (defaults to get_custom_auth_base_issuer())
        expiration_datetime: Absolute expiration datetime (defaults to 24 hours from now)
        issued_at: Absolute issue datetime (defaults to now)
        
    Returns:
        str: Encoded JWT token
    """
    if issuer is None:
        issuer = get_custom_auth_base_issuer()
    
    if expiration_datetime is None:
        expiration_datetime = datetime.now(timezone.utc) + timedelta(hours=24)
    
    if issued_at is None:
        issued_at = datetime.now(timezone.utc)
    
    payload = {
        'iss': issuer,
        'sub': email,
        'email': email,
        'uid': email,  # Use email as UID for custom tokens
        'name': email.split('@')[0], # Use local part of email as name
        'iat': issued_at,
        'exp': expiration_datetime
    }
    
    jwt_key = get_setting('jwt-secret-key')
    return jwt.encode(payload, jwt_key, algorithm="HS256")


def gen_token(email: str, issuer: str = None, expiration_hours: int = 24):
    """
    Generates a custom-signed JWT for the given email address.

    This token is self-contained and includes an issuer claim that identifies it
    as a custom token for the the application. It is signed with the
    environment-specific salt, making it verifiable by our own API w/o Firebase.
    
    Security is maintained through environment-specific salts rather than
    complex project_id alignment across server and client processes.
    
    Args:
        email: User email address
        issuer: JWT issuer (defaults to get_custom_auth_base_issuer())
        expiration_hours: Token validity in hours (default: 24)
        
    Returns:
        str: Encoded JWT token
    """
    expiration_datetime = datetime.now(timezone.utc) + timedelta(hours=expiration_hours)
    return gen_token_using_dates(email, issuer, expiration_datetime)

# Test user functions have been moved to auth.testing module
# Import them from there if needed

def gen_jwt_key() -> str:
    """
    Generate a cryptographically secure JWT key suitable for HMAC signing.
    
    Uses secrets.token_urlsafe(32) to generate 32 bytes (256 bits) of random data
    encoded as a URL-safe base64 string. This provides adequate security for HS256
    JWT signing while maintaining readability and avoiding special characters.
    
    Returns:
        str: A 44-character URL-safe base64 string suitable for JWT keys
    """
    return secrets.token_urlsafe(32)

# ============================================================================ #
# Internal Helper Functions
# ============================================================================ #

def _get_firebase_web_api_key(project_id):
    """Gets the Firebase Web API key using the firebase-tools CLI."""
    try:
        project_id = project_id.strip('"')
        app_list_process = subprocess.run(
            ['firebase', 'apps:list', '--project', project_id, '--json'],
            capture_output=True, text=True, check=True,
        )
        apps = json.loads(app_list_process.stdout)
        web_apps = [app for app in apps.get('result', []) if app.get('platform') == 'WEB']
        if not web_apps:
            raise RuntimeError(f"No Firebase web app found for project {project_id}.")
        
        app_id = web_apps[0]['appId']

        sdk_config_process = subprocess.run(
            ['firebase', 'apps:sdkconfig', 'WEB', app_id, '--project', project_id],
            capture_output=True, text=True, check=True
        )
        sdk_config = json.loads(sdk_config_process.stdout)
        return sdk_config.get('apiKey')
    except (subprocess.CalledProcessError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Could not get Firebase Web API key: {e}")

def ensure_firebase_user_exists(email, get_token=False):
    """
    Ensure a Firebase user exists and optionally return a token.
    
    IMPORTANT: Password Generation and Salt Dependencies
    
    The password is generated deterministically using:
    - project_id: The GCP project ID
    - email: The user email
    - salt: A secretly configured string "salt" (⚠️ CRITICAL DEPENDENCY)
    
    If ANY of these change, the password will be different and authentication will fail.
    
    Common scenarios that break authentication:
    1. PROJECT_ID environment variable changes
    2. Email address changes
    3. Salt string changes (e.g., if secrets are regenerated)
    
    When this happens, you must:
    1. Delete the existing Firebase user via Firebase CLI
    2. Let this function recreate the user with the new password
    
    Example Firebase CLI commands:
    - List users: firebase auth:export --project <project-id> --format json
    - Delete user: firebase auth:delete <uid> --project <project-id>
    
    The deterministic approach ensures:
    - Same password generated every time (for same inputs)
    - No need to store passwords in secrets
    - Consistent behavior across environments
    - Easy to recreate users when needed
    
    Args:
        email: User email address
        get_token: Whether to return an ID token for the user
    
    Returns:
        dict: User info with email, password, uid, and optionally id_token
    """
    # Check if cloud services are enabled
    if not is_cloud_enabled():
        raise NotConfiguredForFirebaseException(
            "Firebase operations require cloud services to be enabled. "
            "Ensure host.json exists with a valid project_id."
        )
    
    # Get project ID and API key
    project_id = get_project_id()
    
    # Generate a deterministic password for the user
    # ⚠️ WARNING: If salt, project_id, or email changes, this will generate a different password
    # and authentication will fail until the Firebase user is recreated
    password = compute_password_hash(project_id, email)
    
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        # In Cloud Run, Firebase auto-detects project ID
        # Locally, use explicit project ID if set
        from multi_eden.run.config.settings import is_cloud_run, is_project_id_set, get_project_id
        
        if is_cloud_run():
            # Let Firebase auto-detect project ID in Cloud Run
            firebase_admin.initialize_app(cred)
        elif is_project_id_set():
            # Use explicit project ID for local development with Firebase
            project_id = get_project_id()
            firebase_admin.initialize_app(cred, {'projectId': project_id})
        else:
            raise RuntimeError(
                "Firebase authentication requires either Cloud Run environment or PROJECT_ID setting. "
                "For local development without Firebase, use custom JWT authentication."
            )
    
    try:
        user = auth.get_user_by_email(email)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email, password=password, email_verified=True)
    
    result = {'email': email, 'password': password, 'uid': user.uid}
    
    if get_token:
        # Get Firebase Web API key
        firebase_web_api_key = _get_firebase_web_api_key(project_id)
        if not firebase_web_api_key:
            raise RuntimeError("Could not determine Firebase Web API Key.")
        
        # Sign in the user and get an ID token
        auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_web_api_key}"
        auth_payload = {"email": email, "password": password, "returnSecureToken": True}
        
        # Debug output for Firebase auth
        try:
            import os
            import logging
            if os.getenv('DEBUG_TOKEN_GENERATION', 'false').lower() == 'true':
                logger = logging.getLogger(__name__)
                logger.info("   🔥 FIREBASE AUTH DEBUG:")
                logger.info(f"      URL: {auth_url}")
                logger.info(f"      Email: {email}")
                logger.info(f"      Password: {password[:8]}...")
                logger.info(f"      Project ID: {project_id}")
        except Exception:
            pass
        
        response = requests.post(auth_url, json=auth_payload)
        
        # Debug response details
        try:
            import os
            import logging
            if os.getenv('DEBUG_TOKEN_GENERATION', 'false').lower() == 'true':
                logger = logging.getLogger(__name__)
                logger.info(f"      Response Status: {response.status_code}")
                logger.info(f"      Response Headers: {dict(response.headers)}")
                if response.status_code != 200:
                    logger.info(f"      Error Response: {response.text}")
        except Exception:
            pass
        
        response.raise_for_status()
        result['id_token'] = response.json().get('idToken')
    
    return result