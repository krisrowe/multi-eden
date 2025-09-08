"""Authentication module for multi-environment applications - handles token generation and auth tasks.

This module provides tasks for authentication including generating static test user tokens.
"""

import sys
import json
from pathlib import Path
from invoke import task
from multi_eden.run.auth.testing import get_static_test_user_token

from .config.decorators import requires_env_stack

@task(help={
    'config_env': 'Environment to generate token for (required: dev, prod, staging, local-server, etc.)',
    'quiet': 'Suppress metadata output to stderr (token always goes to stdout)',
    'debug': 'Enable debug logging (sets LOG_LEVEL=DEBUG)'
})
@requires_env_stack("local")
def token(ctx, config_env=None, quiet=False, debug=False):
    """
    Generate a static test user token for the specified environment.
    
    Token is always output to stdout. Metadata goes to stderr unless --quiet is used.
    
    Examples:
        invoke token --config-env=dev                        # Token to stdout, metadata to stderr
        invoke token --config-env=local --quiet              # Token to stdout, no metadata
        TOKEN=$(invoke token --config-env=local)             # Capture token (ignores stderr)
        curl -H "Authorization: Bearer $(invoke token --config-env=local --quiet)" http://localhost:8000/api/user
    """
    import sys
    
    try:
        if not config_env or config_env.startswith('--'):
            if not quiet:
                print("❌ Environment required.", file=sys.stderr)
                print("💡 Usage: invoke token --config-env=dev", file=sys.stderr)
            return False
        
        if not quiet:
            print(f"🔑 Generating authentication token for environment: {config_env}", file=sys.stderr)
        

        if not quiet:
            print(f"🔧 Using environment: {config_env}", file=sys.stderr)
            print("🚀 Generating token...", file=sys.stderr)
        
        # Initialize logging for the run package if debug is enabled
        if debug:
            try:
                from multi_eden.run.config.logging import bootstrap_logging
                bootstrap_logging()
            except ImportError:
                pass  # Logging module not available
        

        # Call the token generation function directly
        token_data = get_static_test_user_token()
        
        # Always output token to stdout (no matter what)
        print(token_data['token'])
        
        # Show metadata in stderr only if not quiet
        if not quiet:
            print("✅ Token generated successfully!", file=sys.stderr)
            print(f"   Email: {token_data['meta']['email']}", file=sys.stderr)
            print(f"   Source: {token_data['meta']['source']}", file=sys.stderr)
            print(f"   Hash: {token_data['meta']['hash']}", file=sys.stderr)
        return True
            
    except Exception as e:
        if not quiet:
            print(f"❌ Token generation failed: {e}", file=sys.stderr)
        return False
