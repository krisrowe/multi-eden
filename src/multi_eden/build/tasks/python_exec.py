"""
Python execution task runner for multi-environment applications.

This module provides tasks for executing Python code with proper environment configuration,
without needing to manually set environment variables or understand the configuration system.
Perfect for development debugging, script execution, and automated code execution.
"""

import subprocess
import sys
from pathlib import Path
from invoke import task
from multi_eden.build.tasks.config.decorators import config


def get_repo_root():
    """Get the current working directory (project root where user runs tasks)."""
    return Path.cwd()


def run_command(cmd, cwd=None, check=True, capture_output=False, env=None):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True,
            env=env
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e


@task(help={
    'module': 'Python module to run (e.g., "core.api" or "core.cli")',
    'script': 'Python script file to run (relative to core directory)',
    'code': 'Python code to execute (use quotes for multi-line)',
    'args': 'Additional arguments to pass to the module/script'
})
@config()
def py(ctx, config_env=None, module=None, script=None, code=None, args=""):
    """
    Execute Python code with proper environment configuration.
    
    This is the primary way to execute Python code with
    the correct environment variables set. Use one of:
    --module: Run a Python module (e.g., "core.api")
    --script: Run a Python script file (e.g., "debug_hashes.py")
    --code: Execute Python code directly (e.g., "print('hello')")
    
    Examples:
        invoke py --module="core.api" --config-env=local-server
        invoke py --script="debug_hashes.py" --config-env=unit-testing
        invoke py --code="import os; print(os.environ.get('STUB_AI'))" --config-env=dev
        invoke py --module="core.cli" --args="segment --food-description '200g chicken'" --config-env=dev
    """
    # Validate that exactly one execution mode is specified
    execution_modes = [mode for mode in [module, script, code] if mode is not None]
    if len(execution_modes) != 1:
        print("❌ Error: Exactly one execution mode must be specified")
        print("   Use one of: --module, --script, or --code")
        print("   Examples:")
        print("     invoke py --module=core.api --config-env=local-server")
        print("     invoke py --script=debug_hashes.py --config-env=unit-testing")
        print("     invoke py --code=\"print('hello')\" --config-env=dev")
        return False
    
    try:
        print(f"🐍 Python execution with environment: {config_env}")
        
        repo_root = get_repo_root()
        working_dir = repo_root  # Use repo root instead of core directory
        
        # Build and execute command based on mode
        if module:
            return _execute_module(module, args, working_dir)
        elif script:
            return _execute_script(script, args, working_dir)
        elif code:
            return _execute_code(code, working_dir)
        else:
            print("❌ No execution mode specified")
            return False
            
    except Exception as e:
        print(f"❌ Python execution failed: {e}")
        return False


def _execute_module(module, args, core_dir):
    """Execute a Python module."""
    print(f"🚀 Executing module: {module}")
    
    # Build the command
    cmd = f"python -m {module}"
    if args:
        cmd += f" {args}"
    
    print(f"📝 Command: {cmd}")
    print(f"📁 Working directory: {core_dir}")
    
    # Execute the module
    result = run_command(cmd, cwd=str(core_dir))
    
    if result.returncode == 0:
        print("✅ Module execution completed successfully")
        return True
    else:
        print(f"❌ Module execution failed with exit code {result.returncode}")
        if result.stderr:
            print(f"Error output: {result.stderr}")
        return False


def _execute_script(script, args, core_dir):
    """Execute a Python script file."""
    print(f"🚀 Executing script: {script}")
    
    script_path = core_dir / script
    if not script_path.exists():
        print(f"❌ Script file not found: {script_path}")
        return False
    
    # Build the command
    cmd = f"python {script}"
    if args:
        cmd += f" {args}"
    
    print(f"📝 Command: {cmd}")
    print(f"📁 Working directory: {core_dir}")
    
    # Execute the script
    result = run_command(cmd, cwd=str(core_dir))
    
    if result.returncode == 0:
        print("✅ Script execution completed successfully")
        return True
    else:
        print(f"❌ Script execution failed with exit code {result.returncode}")
        if result.stderr:
            print(f"Error output: {result.stderr}")
        return False


def _execute_code(code, core_dir):
    """Execute Python code directly."""
    print(f"🚀 Executing Python code")
    print(f"📝 Code: {code[:100]}{'...' if len(code) > 100 else ''}")
    
    # Build the command
    cmd = f'python -c "{code}"'
    
    print(f"📝 Command: {cmd}")
    print(f"📁 Working directory: {core_dir}")
    
    # Execute the code
    result = run_command(cmd, cwd=str(core_dir))
    
    if result.returncode == 0:
        print("✅ Code execution completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    else:
        print(f"❌ Code execution failed with exit code {result.returncode}")
        if result.stderr:
            print(f"Error output: {result.stderr}")
        return False


@task(help={
})
@config()
def env(ctx, config_env=None):
    """
    Show current environment configuration for debugging.
    
    Useful for understanding what environment variables
    are available and what configuration is loaded.
    """
    try:
        print(f"🔧 Environment Configuration for: {config_env}")
        print("=" * 50)
        
        # Display environment variables
        import os
        from ..secrets import secrets_manifest

        
        # Get secret env vars from manifest instead of hardcoding
        secret_env_vars = secrets_manifest.get_env_var_names()
        key_vars = [
            # Key environment variables
            'PORT', 'APP_ID', 'PROJECT_ID', 'CUSTOM_AUTH_ENABLED', 'STUB_AI', 'STUB_DB',
            'CLOUD_PROJECT_ID'  # Legacy display name for PROJECT_ID
        ] + secret_env_vars
        
        print("\n📋 Key Environment Variables:")
        for var in key_vars:
            value = os.environ.get(var, 'NOT SET')
            # Truncate secret values for display
            if var in secret_env_vars and value != 'NOT SET':
                value = f"{value[:8]}..." if len(value) > 8 else value
            print(f"   {var}: {value}")
        
        print("\n🎯 Usage Examples:")
        print("   # Run API server")
        print(f"   invoke py --module=core.api --config-env={config_env}")
        print("   # Execute Python code")
        print(f"   invoke py --code='import os; print(os.environ.get(\"STUB_AI\"))' --config-env={config_env}")
        print("   # Run script")
        print(f"   invoke py --script=debug_hashes.py --config-env={config_env}")
        
        return True
        
    except Exception as e:
        print(f"❌ Environment inspection failed: {e}")
        return False
