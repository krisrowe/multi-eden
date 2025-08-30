"""
This module provides tasks for local development including starting the API server,
managing the development environment, and other development utilities.
"""

import subprocess
import sys
import os
import signal
import time
import socket
from pathlib import Path
from invoke import task


def get_repo_root():
    """Get the current working directory (project root where user runs tasks)."""
    # For pip-installed library, use current working directory
    # Users will run tasks from their project root
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


def check_venv_exists():
    """Check if the virtual environment exists."""
    repo_root = get_repo_root()
    venv_path = repo_root / "venv"
    return venv_path.exists()


def get_venv_python():
    """Get the path to the virtual environment's Python executable."""
    repo_root = get_repo_root()
    venv_python = repo_root / "venv" / "bin" / "python"
    
    if not venv_python.exists():
        # Try alternative path for Windows
        venv_python = repo_root / "venv" / "Scripts" / "python.exe"
        if not venv_python.exists():
            return None
    
    return venv_python


def get_pid_file_path():
    """Get the path to the server PID file."""
    repo_root = get_repo_root()
    return repo_root / ".api_server.pid"


def read_and_validate_pid_file():
    """Read and validate the PID file.
    
    Returns:
        tuple: (success: bool, pid: int or None, error_message: str or None)
    """
    try:
        pid_file = get_pid_file_path()
        if not pid_file.exists():
            return False, None, "PID file does not exist"
        
        with open(pid_file, 'r') as f:
            pid_str = f.read().strip()
            
        if not pid_str:
            return False, None, "PID file is empty"
            
        if not pid_str.isdigit():
            return False, None, f"PID file contains non-numeric value: '{pid_str}'"
            
        pid = int(pid_str)
        if pid <= 0:
            return False, None, f"PID file contains invalid PID: {pid}"
            
        return True, pid, None
        
    except Exception as e:
        return False, None, f"Error reading PID file: {e}"

def save_server_pid(pid):
    """Save the server PID to a file."""
    try:
        pid_file = get_pid_file_path()
        print(f"💾 Saving PID {pid} to {pid_file}")
        
        # Write the PID to the file
        with open(pid_file, 'w') as f:
            f.write(str(pid))
        
        # Immediately validate the file was written correctly using the centralized helper
        print(f"✅ PID saved successfully")
        
        success, saved_pid, error_msg = read_and_validate_pid_file()
        if not success:
            print(f"❌ PID validation failed: {error_msg}")
            return False
            
        if saved_pid != pid:
            print(f"❌ PID validation failed: wrote {pid}, read {saved_pid}")
            return False
            
        print(f"✅ PID validation passed: {saved_pid}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save PID: {e}")
        return False


def get_server_pid():
    """Get the server PID from the file."""
    success, pid, error_msg = read_and_validate_pid_file()
    if not success:
        print(f"⚠️  PID file validation failed: {error_msg}")
        return None
    return pid


def clear_server_pid():
    """Clear the server PID file."""
    try:
        pid_file = get_pid_file_path()
        if pid_file.exists():
            pid_file.unlink()
        return True
    except Exception:
        return False


def is_process_running(pid):
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
        return True
    except (OSError, ProcessLookupError):
        return False


def check_port_available(port, check_listening=False, max_retries=10, retry_interval=1):
    """Check if a port is available or listening.
    
    Args:
        port: Port number to check
        check_listening: If True, check if port is listening (occupied)
        max_retries: Maximum number of retries
        retry_interval: Seconds between retries
    
    Returns:
        bool: True if port is available (not listening), False if listening
    """
    import socket
    
    for attempt in range(max_retries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('localhost', port))
                
                if check_listening:
                    # For listening check: True means port is occupied (listening)
                    return result == 0
                else:
                    # For availability check: True means port is free
                    return result != 0
                    
        except Exception:
            # If we can't check, assume port is available
            if not check_listening:
                return True
            else:
                return False
        
        if attempt < max_retries - 1:
            time.sleep(retry_interval)
    
    # After max retries, return the last result
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            
            if check_listening:
                return result == 0
            else:
                return result != 0
    except Exception:
        return not check_listening


@task(help={
    'port': 'Port to run the API server on (default: 8000)',
    'env': 'Configuration environment to use (default: local)',
    'background': 'Run in background (default: True)'
})
def api_start(ctx, port=None, env="local", background=True):
    """Start the API server."""
    try:
        # Get repository root and load API configuration for process detection
        repo_root = get_repo_root()
        try:
            from multi_eden.build.config.app_config import get_api_module_info
            api_info = get_api_module_info(repo_root)
            module_spec = api_info['module']
            module_name = api_info['module_name']
            serve_args = ' '.join(api_info['serve_args'])
        except Exception as e:
            print(f"❌ Failed to load API configuration: {e}")
            print(f"💡 Ensure config/app.yaml exists with proper 'api' configuration")
            print(f"💡 Run 'invoke init-app' to create proper configuration")
            return False
        
        print("🔍 Checking for existing server processes...")
        # Look for uvicorn processes with the configured module
        import os
        current_pid = os.getpid()
        cmd = f"pgrep -f '^[^ ]*python[^ ]* -m uvicorn.*{module_spec}'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            existing_pids = [pid for pid in result.stdout.strip().split('\n') if pid.strip()]
            if existing_pids:  # Only report if there are actual PIDs after filtering
                print(f"❌ Found {len(existing_pids)} existing uvicorn process(es): {existing_pids}")
                print("💡 Please stop existing servers first with 'invoke api-stop'")
                return False
        
        # Also check for the parent python process running the configured module
        cmd = f"pgrep -f '^[^ ]*python[^ ]* -m {module_name} {serve_args}'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            existing_pids = [pid for pid in result.stdout.strip().split('\n') if pid.strip()]
            if existing_pids:  # Only report if there are actual PIDs after filtering
                print(f"❌ Found {len(existing_pids)} existing python process(es): {existing_pids}")
                print("💡 Please stop existing servers first with 'invoke api-stop'")
                return False
        
        print("✅ No existing server processes found")
        
        # Check if server is already running (port check)
        if check_port_available(port, check_listening=True):
            print(f"❌ Port {port} is already in use")
            return False
        
        # Get repository root and virtual environment
        repo_root = get_repo_root()
        
        # Load API configuration to get venv path
        try:
            from multi_eden.build.config.app_config import get_api_module_info
            api_info = get_api_module_info(repo_root)
            venv_path = api_info['venv_path']
        except Exception as e:
            print(f"❌ Failed to load API configuration: {e}")
            print(f"💡 Ensure config/app.yaml exists with proper 'api' configuration")
            print(f"💡 Run 'invoke init-app' to create proper configuration")
            return False
        
        venv_python = repo_root / venv_path / "bin" / "python"
        if not venv_python.exists():
            print(f"❌ Virtual environment not found at {repo_root / venv_path}")
            print(f"💡 Check your config/app.yaml api.venv_path setting")
            return False
        
        # Load environment configuration
        try:
            from multi_eden.build.config.loading import load_env
            load_env(env)
            print(f"🔧 Loaded configuration from {env} environment")
        except Exception as e:
            print(f"⚠️  Could not load configuration for environment '{env}': {e}")
            print(f"⚠️  Continuing with default environment variables")
        
        # Set environment variables
        env_vars = os.environ.copy()
        
        # Override PORT if explicitly provided as parameter
        if port is not None:
            env_vars["PORT"] = str(port)
        
        # Set PYTHONPATH based on API configuration
        working_dir = api_info.get('working_dir', '.')
        if working_dir == '.':
            pythonpath = str(repo_root)
        else:
            pythonpath = str(repo_root / working_dir)
        env_vars["PYTHONPATH"] = pythonpath
        
        # Build the command using API configuration
        serve_command = ' '.join(api_info['serve_args'])
        cmd = f"{venv_python} -m {module_name} {serve_command} --config-env={env}"
        
        print(f"🚀 Starting API server...")
        print(f"📁 Working directory: {repo_root}")
        print(f"🔧 Command: {cmd}")
        
        # Start server and show startup output, then background
        result = subprocess.Popen(
            cmd,
            shell=True,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Combine stderr into stdout
            text=True,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
        )
        
        # Show startup output until server is ready
        startup_lines = []
        server_ready = False
        
        try:
            while True:
                line = result.stdout.readline()
                if not line:  # Process ended
                    break
                    
                startup_lines.append(line.rstrip())
                print(line.rstrip())  # Show runtime config and startup info
                
                # Check if server is ready
                if "Uvicorn running on" in line or "Application startup complete" in line:
                    server_ready = True
                    break
                    
                # Safety check - don't wait forever
                if len(startup_lines) > 50:
                    break
                    
        except KeyboardInterrupt:
            print("\n❌ Server startup interrupted")
            result.terminate()
            return False
            
        if server_ready:
            print("✨ Server startup complete - running in background")
            print(f"🌐 API available at: http://localhost:{env_vars.get('PORT', '8000')}")
            print(f"📝 Process ID: {result.pid}")
            print("💡 Use 'invoke api-stop' to stop the server")
            
            # Save PID to a file for reliable stopping
            if save_server_pid(result.pid):
                print(f"💾 PID {result.pid} saved for future reference")
            else:
                print(f"⚠️  Warning: Could not save PID {result.pid}")
            
            return True
        else:
            print("❌ Server failed to start or startup output not detected")
            if result.poll() is not None:
                print(f"❌ Process exited with code: {result.returncode}")
            result.terminate()
            return False
            
    except Exception as e:
        print(f"❌ Failed to start API server: {e}")
        return False


@task
def api_stop(ctx):
    """Stop the API server with graceful shutdown and reliable fallback."""
    print("🛑 Stopping API server...")
    
    # Step 1: Try graceful shutdown using saved PID
    pid = get_server_pid()
    if pid and is_process_running(pid):
        try:
            print(f"🔄 Gracefully stopping process {pid}...")
            os.kill(pid, signal.SIGTERM)
            
            # Wait up to 5 seconds for graceful shutdown
            for _ in range(5):
                if not is_process_running(pid):
                    print("✅ Server stopped gracefully")
                    clear_server_pid()
                    return True
                time.sleep(1)
        except (ProcessLookupError, PermissionError):
            pass
    
    # Step 2: Reliable fallback - kill ALL matching processes aggressively
    print("🔄 Using reliable fallback method...")
    
    # First try SIGTERM
    subprocess.run(["pkill", "-TERM", "-f", "core serve"], capture_output=True)
    time.sleep(2)
    
    # Then force kill any remaining
    result = subprocess.run(["pkill", "-KILL", "-f", "core serve"], capture_output=True)
    
    # Also kill any python processes that might be lingering
    subprocess.run(["pkill", "-KILL", "-f", "python.*serve"], capture_output=True)
    
    print("✅ All server processes forcefully stopped")
    
    # Clean up PID file
    clear_server_pid()
    
    print("✅ API server stop complete")
    return True


@task
def api_status(ctx):
    """Check the status of the API server."""
    try:
        print("🔍 Checking API server status...")
        
        # Check if we have a saved PID
        pid = get_server_pid()
        if pid:
            if is_process_running(pid):
                print(f"✅ API server is running (PID: {pid})")
                
                # Check if it's actually listening on port 8000
                if check_port_available(8000, check_listening=True):
                    print("🌐 Server is listening on port 8000")
                    print("🔗 API available at: http://localhost:8000")
                else:
                    print("⚠️  Server process running but not listening on port 8000")
                
                return True
            else:
                print("⚠️  Server PID file exists but process is not running")
                clear_server_pid()
        
        # Check if any process is listening on port 8000
        if check_port_available(8000, check_listening=True):
            print("🌐 Port 8000 is in use (server may be running)")
            print("🔗 API available at: http://localhost:8000")
            return True
        else:
            print("ℹ️  API server is not running")
            return False
            
    except Exception as e:
        print(f"❌ Error checking server status: {e}")
        return False


@task
def api_restart(ctx, port=None, env="local"):
    """Restart the API server."""
    try:
        print("🔄 Restarting API server...")
        
        # Stop the server first
        if api_stop(ctx):
            print("⏳ Waiting for server to stop...")
            
            # Poll for port to be fully released (up to 20 seconds)
            if check_port_available(8000, check_listening=True, max_retries=20, retry_interval=1):
                print("✅ Port released, starting new server...")
            else:
                print("⚠️  Port may still be in use, attempting to start anyway...")
        
        # Start the server again
        return api_start(ctx, port=port, env=env, background=True)
        
    except Exception as e:
        print(f"❌ Failed to restart API server: {e}")
        return False


@task
def setup(ctx):
    """
    Set up the development environment.
    
    This replicates the Makefile's setup target functionality.
    """
    try:
        print("🔧 Setting up development environment...")
        
        repo_root = get_repo_root()
        core_dir = repo_root / "core"
        frontend_dir = repo_root / "frontend"
        
        # Create virtual environment if it doesn't exist
        if not check_venv_exists():
            print("🔧 Creating virtual environment...")
            result = run_command("python3 -m venv venv", cwd=core_dir)
            if result.returncode != 0:
                print("❌ Failed to create virtual environment")
                return False
            print("✅ Virtual environment created")
        else:
            print("✅ Virtual environment already exists")
        
        # Install Python dependencies
        print("📦 Installing Python dependencies...")
        venv_pip = core_dir / "venv" / "bin" / "pip"
        if not venv_pip.exists():
            venv_pip = core_dir / "venv" / "Scripts" / "pip.exe"  # Windows
        
        if venv_pip.exists():
            result = run_command(f"{venv_pip} install -q -r requirements.txt", cwd=core_dir)
            if result.returncode == 0:
                print("✅ Python dependencies installed")
            else:
                print("❌ Failed to install Python dependencies")
                return False
        else:
            print("❌ Could not find pip in virtual environment")
            return False
        
        # Install frontend dependencies
        if frontend_dir.exists():
            print("📦 Installing frontend dependencies...")
            result = run_command("npm install --silent", cwd=frontend_dir)
            if result.returncode == 0:
                print("✅ Frontend dependencies installed")
            else:
                print("❌ Failed to install frontend dependencies")
                return False
        else:
            print("ℹ️  Frontend directory not found, skipping npm install")
        
        print("🎉 Development environment setup complete!")
        return True
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        return False



