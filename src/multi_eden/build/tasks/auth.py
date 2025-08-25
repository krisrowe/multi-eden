"""Authentication module for multi-environment applications - handles token generation and auth tasks.

This module provides tasks for authentication including generating static test user tokens.
"""

import subprocess
from pathlib import Path
from invoke import task

try:
    from .local import run_command, check_venv_exists, get_venv_python
except ImportError:
    from local import run_command, check_venv_exists, get_venv_python


@task(help={
    'env': 'Environment to generate token for (required: dev, prod, staging, local-server, etc.)'
})
def token(ctx, env=None):
    """
    Generate a static test user token for the specified environment.
    
    Uses the SDK's built-in authentication module to generate tokens.
    
    Examples:
        invoke token --env=dev              # Generate token for dev environment
        invoke token --env=local-server     # Generate token for local-server environment
        invoke token --env=prod             # Generate token for prod environment
    """
    try:
        if not env or env.startswith('--'):
            print("❌ Environment required.")
            print("💡 Usage: invoke token --env=dev")
            return False
        
        print(f"🔑 Generating authentication token for environment: {env}")
        
        # Check if virtual environment exists
        if not check_venv_exists():
            print("❌ Virtual environment not found.")
            print("💡 Run 'invoke setup' first to create the virtual environment.")
            return False
        
        # Get virtual environment Python
        venv_python = get_venv_python()
        if not venv_python:
            print("❌ Could not find Python executable in virtual environment.")
            return False
        
        # Build the command using the SDK's own auth module
        cmd = f"{venv_python} -m multi_eden.run.auth.cli generate-static-test-user-token --config-env={env}"
        
        print(f"🔧 Using environment: {env}")
        print("🚀 Generating token...")
        
        # Run the command
        result = run_command(cmd, cwd=Path.cwd())
        
        if result.returncode == 0:
            print("✅ Token generated successfully!")
            return True
        else:
            print("❌ Token generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        return False
