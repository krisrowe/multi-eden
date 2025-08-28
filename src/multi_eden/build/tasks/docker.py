"""
This module handles local Docker operations including building images,
running containers, and managing Docker Compose stacks.
"""

import subprocess
import sys
import os
import json
from pathlib import Path
from invoke import task
from multi_eden.build.tasks.config.decorators import requires_config_env


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


@task
@requires_config_env
def docker_build(ctx, config_env=None):
    """
    Build local Docker image.
    
    This replicates the Makefile's docker-build target.
    """
    try:
        print("🐳 Building local Docker image...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        repo_root = get_repo_root()
        core_dir = repo_root / "core"
        
        print(f"📁 Building from: {core_dir}")
        
        # Build Docker image
        cmd = "docker build -t my-app-api:local ."
        result = run_command(cmd, cwd=str(core_dir))
        
        if result.returncode == 0:
            print("✅ Docker image built")
            return True
        else:
            print("❌ Docker build failed")
            return False
            
    except Exception as e:
        print(f"❌ Docker build failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)',
    'port': 'Port to expose (default: 8001)',
    'container_name': 'Container name'
})
@requires_config_env
def docker_run(ctx, config_env=None, port=8001, container_name = "my-app:local"):
    """
    Start local Docker API container.
    
    This replicates the Makefile's docker-run target.
    
    Examples:
        invoke docker-run                                    # Use default environment
        invoke docker-run --config-env=local-docker         # Specify environment
        invoke docker-run --port=8002                       # Use different port
    """
    try:
        print("🐳 Starting local Docker API...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        repo_root = get_repo_root()
        
        # Stop and remove existing container
        print(f"🧹 Cleaning up existing container: {container_name}")
        run_command(f"docker rm -f {container_name}", check=False)
        
        # Build Docker run command
        cmd_parts = [
            "docker run -d",
            f"--name {container_name}",
            f"-p {port}:8080",
            f"-e CONFIG_ENV={config_env}",
            f"-v {repo_root}/secrets:/app/core/secrets:ro",
            f"-v {repo_root}/config/settings/{config_env}:/app/config/settings/static:ro",
            f"-v {repo_root}/config/secrets/{config_env}:/app/config/secrets/static:ro",
            "my-app:local"
        ]
        
        cmd = " ".join(cmd_parts)
        
        # Run container
        result = run_command(cmd)
        
        if result.returncode == 0:
            print(f"✅ Docker API running on http://localhost:{port}")
            
            # Wait a moment and check health
            print("⏳ Waiting for API to start...")
            import time
            time.sleep(3)
            
            # Check health endpoint
            health_result = run_command(f"curl -s http://localhost:{port}/health", check=False)
            if health_result.returncode == 0:
                print("✅ API is healthy")
            else:
                print("⚠️  API may still be starting")
            
            return True
        else:
            print("❌ Failed to start Docker container")
            return False
            
    except Exception as e:
        print(f"❌ Docker run failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def compose_up(ctx, config_env=None, api_url="http://localhost:8001"):
    """
    Start full stack with Docker Compose.
    
    This replicates the Makefile's compose-up target.
    
    Examples:
        invoke compose-up                    # Use local-server environment
        invoke compose-up --config-env=dev         # Use dev environment
        invoke compose-up --config-env=prod        # Use prod environment
    """
    try:
        print(f"🔧 Using configuration environment: {config_env}")
        print("🐳 Starting full stack with Docker Compose...")
        
        repo_root = get_repo_root()
        
        # Clean up any existing standalone containers
        print("🧹 Cleaning up any existing standalone containers...")
        run_command("docker stop my-app-local", check=False)
        run_command("docker rm my-app-local", check=False)
        
        # Generate auth token
        print("🔑 Generating auth token...")
        venv_python = repo_root / "venv" / "bin" / "python"
        
        if not venv_python.exists():
            print("❌ Virtual environment not found. Run 'make setup' first.")
            return False
        
        token_cmd = f"{venv_python} -m core.auth.cli generate-static-test-user-token --config-env={config_env}"
        token_result = run_command(token_cmd, cwd=str(repo_root), capture_output=True)
        
        if token_result.returncode != 0:
            print("❌ Failed to generate auth token")
            return False
        
        # Parse token from JSON response
        try:
            token_json = json.loads(token_result.stdout.strip())
            token = token_json.get('token')
            
            if not token or token == "null":
                print("❌ Failed to extract token from JSON response")
                return False
                
            print("✅ Token ready")
            
        except json.JSONDecodeError:
            print("❌ Failed to parse token JSON response")
            return False
        
        # Start Docker Compose
        print("🚀 Starting services...")
        env_vars = os.environ.copy()
        env_vars["VITE_API_URL"] = api_url
        env_vars["VITE_AUTH_TOKEN"] = token
        env_vars["CONFIG_ENV"] = config_env
        
        # Load and inject environment variables from configuration files
        try:
            from multi_eden.build.secrets import load_env
            
            load_env(config_env)
            
            # Copy environment variables set by load_env() to our env_vars dict
            if os.environ.get('STUB_AI'):
                env_vars['STUB_AI'] = os.environ['STUB_AI']
                print(f"🔧 STUB_AI={os.environ['STUB_AI']} (from config)")
            
            if os.environ.get('STUB_DB'):
                env_vars['STUB_DB'] = os.environ['STUB_DB']
                print(f"🔧 STUB_DB={os.environ['STUB_DB']} (from config)")
            
            if os.environ.get('CUSTOM_AUTH_ENABLED'):
                env_vars['CUSTOM_AUTH_ENABLED'] = os.environ['CUSTOM_AUTH_ENABLED']
                print(f"🔧 CUSTOM_AUTH_ENABLED={os.environ['CUSTOM_AUTH_ENABLED']} (from config)")
            
            # Copy all secret environment variables using manifest
            from ..secrets import secrets_manifest
            secrets_manifest.copy_set_env_vars_to_dict(env_vars)
            
            # Show which secrets were set
            for env_var in secrets_manifest.get_env_var_names():
                if os.environ.get(env_var):
                    print(f"🔧 {env_var} set (from config)")
            
            # ALL_AUTHENTICATED_USERS removed - now handled via wildcard in allowed-user-emails
            
            # ALLOWED_USER_EMAILS now handled via secrets manifest
            
        except Exception as e:
            print(f"⚠️  Could not load provider configuration: {e}")
            print(f"⚠️  Using default environment variables")
        
        print(f"🔧 Environment variables:")
        print(f"   VITE_API_URL: {env_vars.get('VITE_API_URL')}")
        print(f"   VITE_AUTH_TOKEN: {env_vars.get('VITE_AUTH_TOKEN')[:20]}..." if env_vars.get('VITE_AUTH_TOKEN') else "   VITE_AUTH_TOKEN: None")
        print(f"   CONFIG_ENV: {env_vars.get('CONFIG_ENV')}")
        print(f"   STUB_AI: {env_vars.get('STUB_AI', 'not set')}")
        print(f"   STUB_DB: {env_vars.get('STUB_DB', 'not set')}")
        print(f"   CUSTOM_AUTH_ENABLED: {env_vars.get('CUSTOM_AUTH_ENABLED', 'not set')}")
        
        compose_cmd = "docker compose up --build -d"
        result = run_command(compose_cmd, env=env_vars)
        
        if result.returncode == 0:
            print("✅ Docker Compose services started successfully in background")
            print("🔍 Use 'invoke compose-logs' to view logs")
            print("🛑 Use 'invoke compose-down' to stop services")
            
            # Wait a moment for containers to start, then check what config was mounted
            import time
            time.sleep(5)
            
            try:
                # Check what config files are actually mounted
                print("🔍 Checking mounted configuration...")
                check_cmd = "docker exec my-app-api cat /app/config/settings/static/providers.json"
                check_result = run_command(check_cmd, capture_output=True)
                if check_result.returncode == 0:
                    print("✅ Config mounted successfully:")
                    print(f"   providers.json: {check_result.stdout.strip()}")
                else:
                    print("❌ Could not read mounted config")
            except Exception as e:
                print(f"⚠️ Could not verify mounted config: {e}")
            
            return True
        else:
            print("❌ Docker Compose failed to start services")
            return False
            
    except Exception as e:
        print(f"❌ Compose up failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def compose_down(ctx, config_env=None):
    """
    Stop Docker Compose services.
    
    This replicates the Makefile's compose-down target.
    """
    try:
        print("🚫 Stopping Docker Compose services...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        result = run_command("docker compose down")
        
        if result.returncode == 0:
            print("✅ Docker Compose services stopped")
            return True
        else:
            print("❌ Failed to stop Docker Compose services")
            return False
            
    except Exception as e:
        print(f"❌ Compose down failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def compose_logs(ctx, config_env=None):
    """
    View Docker Compose logs.
    
    This replicates the Makefile's compose-logs target.
    """
    try:
        print("📜 Viewing Docker Compose logs...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        # Note: This will run in foreground to show logs
        result = run_command("docker compose logs -f")
        
        # This command runs until interrupted, so we may not reach here
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Compose logs failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def compose_restart(ctx, config_env=None):
    """
    Restart Docker Compose services.
    
    This replicates the Makefile's compose-restart target.
    """
    try:
        print("🔄 Restarting Docker Compose services...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        result = run_command("docker compose restart")
        
        if result.returncode == 0:
            print("✅ Docker Compose services restarted")
            return True
        else:
            print("❌ Failed to restart Docker Compose services")
            return False
            
    except Exception as e:
        print(f"❌ Compose restart failed: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def docker_status(ctx, config_env=None):
    """
    Check Docker container status.
    
    This replicates the Makefile's docker-status target.
    """
    try:
        print("🔍 Checking Docker status...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        print("\n📦 Standalone Container:")
        result = run_command("docker ps -a --format 'table {{.ID}}\t{{.Image}}\t{{.Command}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}' | grep my-app", check=False)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("ℹ️  No standalone containers found")
        
        print("\n🐳 Docker Compose Services:")
        result = run_command("docker-compose ps", check=False)
        if result.returncode == 0:
            print(result.stdout)
        else:
            print("ℹ️  No compose services found")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to check Docker status: {e}")
        return False


@task(help={
    'config_env': 'Configuration environment to use (defaults to task default)'
})
@requires_config_env
def docker_cleanup(ctx, config_env=None):
    """
    Clean up Docker resources.
    
    This replicates the Makefile's docker-cleanup target.
    """
    try:
        print("🧹 Cleaning up Docker resources...")
        print(f"🔧 Using configuration environment: {config_env}")
        
        # Clean up standalone container
        print("📦 Cleaning up standalone container...")
        run_command("docker rm -f my-app-local", check=False)
        
        # Clean up compose services
        print("🐳 Cleaning up compose services...")
        run_command("docker-compose down", check=False)
        
        # Remove local image
        print("🖼️  Removing local image...")
        run_command("docker rmi my-app-api:local", check=False)
        
        print("✅ Docker cleanup completed")
        return True
        
    except Exception as e:
        print(f"❌ Docker cleanup failed: {e}")
        return False
