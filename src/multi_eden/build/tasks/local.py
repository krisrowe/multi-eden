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
    'env': 'Configuration environment to use (default: local-server)',
    'background': 'Run in background (default: True)'
})
def api_start(ctx, port=8000, env="local-server", background=True):
    """Start the API server."""
    try:
        # Check if there are already Python processes running core serve
        print("🔍 Checking for existing server processes...")
        # Look for uvicorn processes since that's what actually runs the server
        cmd = "pgrep -f 'uvicorn.*core.api:app'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            existing_pids = result.stdout.strip().split('\n')
            print(f"❌ Found {len(existing_pids)} existing uvicorn process(es): {existing_pids}")
            print("💡 Please stop existing servers first with 'invoke api-stop'")
            return False
        
        # Also check for the parent python process
        cmd = "pgrep -f 'python.*core serve'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            existing_pids = result.stdout.strip().split('\n')
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
        venv_python = repo_root / "core" / "venv" / "bin" / "python"
        
        if not venv_python.exists():
            print(f"❌ Virtual environment not found at {venv_python}")
            return False
        
        # Load environment configuration
        try:
            from multi_eden.build.secrets import load_env
            load_env(env)
            print(f"🔧 Loaded configuration from {env} environment")
        except Exception as e:
            print(f"⚠️  Could not load configuration for environment '{env}': {e}")
            print(f"⚠️  Continuing with default environment variables")
        
        # Set environment variables
        env_vars = os.environ.copy()
        env_vars["PYTHONPATH"] = str(repo_root / "core")
        
        # Build the command
        cmd = f"{venv_python} -m core serve --config-env={env}"
        
        print(f"🚀 Starting API server...")
        print(f"📁 Working directory: {repo_root}")
        print(f"🔧 Command: {cmd}")
        print(f"🌐 Port: {port}")
        
        # Start in background with proper process management
        result = subprocess.Popen(
            cmd,
            shell=True,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # Create new process group
        )
        
        # Wait a moment to check if it started successfully
        time.sleep(2)
        
        if result.poll() is None:
            # Process is running, now check if it's actually listening on the port
            print("⏳ Waiting for server to start listening...")
            
            # Poll for server to start listening (up to 30 seconds)
            if check_port_available(port, check_listening=True, max_retries=30, retry_interval=1):
                print("✅ API server started successfully in background")
                print(f"🌐 API running on http://localhost:{port}")
                print(f"📝 Process ID: {result.pid}")
                print("💡 Use 'invoke api-stop' to stop the server")
                
                # Save PID to a file for reliable stopping
                if save_server_pid(result.pid):
                    print(f"💾 PID {result.pid} saved for future reference")
                else:
                    print(f"⚠️  Warning: Could not save PID {result.pid}")
                
                return True
            else:
                print("❌ API server process started but not listening on port")
                result.terminate()
                return False
        else:
            print("❌ API server failed to start")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start API server: {e}")
        return False


@task
def api_stop(ctx):
    """Stop the API server."""
    try:
        print("🛑 Stopping API server...")
        
        # Try to stop using saved PID first
        pid = get_server_pid()
        if pid:
            try:
                # Try graceful termination first
                os.kill(pid, signal.SIGTERM)
                print("⏳ Waiting for graceful shutdown...")
                
                # Poll for process to stop (up to 15 seconds)
                for attempt in range(15):
                    if not is_process_running(pid):
                        break
                    time.sleep(1)
                
                # Check if process is still running
                if is_process_running(pid):
                    print("🔄 Process still running, force killing...")
                    os.kill(pid, signal.SIGKILL)
                    
                    # Poll for process to stop (up to 10 seconds)
                    for attempt in range(10):
                        if not is_process_running(pid):
                            break
                        time.sleep(1)
                
                # Wait for port to be released
                print("⏳ Waiting for port to be released...")
                # Poll until port is released or max retries reached
                for attempt in range(20):  # Wait up to 20 seconds
                    if not check_port_available(8000, check_listening=True):
                        print("✅ API server stopped gracefully")
                        clear_server_pid()
                        return True
                    time.sleep(1)
                
                print("⚠️  Port still appears to be in use after 20 seconds")
                clear_server_pid()
                return False
                    
            except (ProcessLookupError, PermissionError):
                print("⚠️  Could not stop process by PID, trying alternative method...")
        
        # Fallback: Find and kill ALL Python processes running core serve
        print("🔍 Looking for Python processes running core serve...")
        
        # First, try to find all such processes
        cmd = "pgrep -f 'python.*core serve'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"🔍 Found {len(pids)} process(es) to stop: {pids}")
            
            # Kill each process
            for pid_str in pids:
                if pid_str.strip().isdigit():
                    try:
                        pid_int = int(pid_str.strip())
                        print(f"🛑 Stopping process {pid_int}...")
                        os.kill(pid_int, signal.SIGTERM)
                    except (ValueError, ProcessLookupError, PermissionError) as e:
                        print(f"⚠️  Could not stop process {pid_str}: {e}")
            
            # Wait a moment for processes to stop
            time.sleep(3)
            
            # Force kill any remaining processes
            cmd = "pkill -9 -f 'python.*core serve'"
            result = run_command(cmd, check=False)
            
            if result.returncode == 0:
                print("✅ All processes stopped using alternative method")
                clear_server_pid()
                
                # Wait for port to be released
                print("⏳ Waiting for port to be released...")
                # Poll until port is released or max retries reached
                for attempt in range(20):  # Wait up to 20 seconds
                    if not check_port_available(8000, check_listening=True):
                        print("✅ Port released successfully")
                        return True
                    time.sleep(1)
                
                print("⚠️  Port still appears to be in use after 20 seconds")
                return False
            else:
                print("⚠️  Could not stop all processes")
                return False
        else:
            print("ℹ️  No Python processes running core serve found")
            
        # Also check for uvicorn processes
        print("🔍 Looking for uvicorn processes...")
        cmd = "pgrep -f 'uvicorn.*core.api:app'"
        result = run_command(cmd, check=False, capture_output=True)
        
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print(f"🔍 Found {len(pids)} uvicorn process(es) to stop: {pids}")
            
            # Kill each uvicorn process
            for pid_str in pids:
                if pid_str.strip().isdigit():
                    try:
                        pid_int = int(pid_str.strip())
                        print(f"🛑 Stopping uvicorn process {pid_int}...")
                        os.kill(pid_int, signal.SIGTERM)
                    except (ValueError, ProcessLookupError, PermissionError) as e:
                        print(f"⚠️  Could not stop uvicorn process {pid_str}: {e}")
            
            # Wait a moment for processes to stop
            time.sleep(3)
            
            # Force kill any remaining uvicorn processes
            cmd = "pkill -9 -f 'uvicorn.*core.api:app'"
            result = run_command(cmd, check=False)
            
            if result.returncode == 0:
                print("✅ All uvicorn processes stopped")
                clear_server_pid()
                
                # Wait for port to be released
                print("⏳ Waiting for port to be released...")
                # Poll until port is released or max retries reached
                for attempt in range(20):  # Wait up to 20 seconds
                    if not check_port_available(8000, check_listening=True):
                        print("✅ Port released successfully")
                        return True
                    time.sleep(1)
                
                print("⚠️  Port still appears to be in use after 20 seconds")
                return False
            else:
                print("⚠️  Could not stop all uvicorn processes")
                return False
        else:
            print("ℹ️  No uvicorn processes found")
            clear_server_pid()
            return True
            
    except Exception as e:
        print(f"❌ Failed to stop API server: {e}")
        return False


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
def api_restart(ctx, port=8000, env="local-server"):
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



