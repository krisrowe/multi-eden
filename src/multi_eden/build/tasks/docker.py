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
from multi_eden.build.tasks.config.decorators import config


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
@config()
def docker_build(ctx, profile=None):
    """
    Build local Docker image.
    
    This replicates the Makefile's docker-build target.
    """
    try:
        print("🐳 Building local Docker image...")
        print(f"🔧 Using configuration environment: {profile}")
        
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
    'port': 'Port to expose (default: 8001)',
    'container_name': 'Container name'
})
@config("local-docker")
def docker_run(ctx, profile=None, port=8001, container_name = "multi-eden-app"):
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
        print(f"🔧 Using configuration environment: {profile}")
        
        repo_root = get_repo_root()
        
        # Stop and remove existing container
        print(f"🧹 Cleaning up existing container: {container_name}")
        run_command(f"docker rm -f {container_name}", check=False)
        
        # Get the actual built image name and tag
        from multi_eden.build.tasks.build import get_build_config, check_existing_tag
        
        try:
            project_id, image_name = get_build_config()
            existing_tag = check_existing_tag()
            
            if existing_tag:
                full_image_name = f"gcr.io/{project_id}/{image_name}:{existing_tag}"
                print(f"🏷️  Using image: {full_image_name}")
            else:
                print("❌ No tagged image found. Please run 'invoke build' first.")
                return False
                
        except Exception as e:
            print(f"❌ Could not determine image name: {e}")
            print("💡 Please run 'invoke build' first to create an image.")
            return False
        
        # Environment variables are already loaded by the decorator
        # Use the port parameter, fallback to environment PORT, then default to 8001
        port = port or os.environ.get("PORT", "8001")
        
        # Follow Cloud Run conventions: container listens on standard port 8000
        # Cloud Run will set PORT automatically, local Docker should mimic this
        container_internal_port = 8000
        
        # Build Docker run command
        cmd_parts = [
            "docker run -d",
            f"--name {container_name}",
            f"-p {port}:{container_internal_port}",  # Map host port to standard container port
            f"-e CONFIG_ENV={profile}"
        ]
        

        
        # Add ALL runtime settings environment variables (from settings_manifest.yaml)
        runtime_env_vars = [
            # Secrets (from settings_manifest.yaml)
            "JWT_SECRET_KEY", "ALLOWED_USER_EMAILS", "GEMINI_API_KEY",
            # Legacy (for backward compatibility)
            "CUSTOM_AUTH_SALT"
        ]
        for env_var in runtime_env_vars:
            if env_var in os.environ:
                cmd_parts.append(f"-e {env_var}={os.environ[env_var]}")
        
        cmd_parts.append(full_image_name)
        
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
})
@config()
def compose_up(ctx, profile=None, api_url="http://localhost:8001"):
    """
    Start full stack with Docker Compose.
    
    This replicates the Makefile's compose-up target.
    
    Examples:
        invoke compose-up                    # Use local-server environment
        invoke compose-up --config-env=dev         # Use dev environment
        invoke compose-up --config-env=prod        # Use prod environment
    """
    try:
        print(f"🔧 Using configuration environment: {profile}")
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
        
        token_cmd = f"{venv_python} -m core.auth.cli generate-static-test-user-token --config-env={profile}"
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
        env_vars["CONFIG_ENV"] = profile
        
        # Load and inject environment variables from configuration files
        try:
            from multi_eden.build.config.loading import load_env
            
            # Environment variables are already loaded by the decorator
            
            # Copy key environment variables set by load_env() to our env_vars dict
            key_env_vars = ["PORT", "APP_ID", "PROJECT_ID", "CUSTOM_AUTH_ENABLED", "STUB_AI", "STUB_DB"]
            for env_var_name in key_env_vars:
                if os.environ.get(env_var_name):
                    env_vars[env_var_name] = os.environ[env_var_name]
                    print(f"🔧 {env_var_name}={os.environ[env_var_name]} (from config)")
            
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
        # Display all environment variables from manifest
        for env_var_name in env_vars_manifest.get_env_var_names():
            print(f"   {env_var_name}: {env_vars.get(env_var_name, 'not set')}")
        
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
})
@config()
def compose_down(ctx, profile=None):
    """
    Stop Docker Compose services.
    
    This replicates the Makefile's compose-down target.
    """
    try:
        print("🚫 Stopping Docker Compose services...")
        print(f"🔧 Using configuration environment: {profile}")
        
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
})
@config()
def compose_logs(ctx, profile=None):
    """
    View Docker Compose logs.
    
    This replicates the Makefile's compose-logs target.
    """
    try:
        print("📜 Viewing Docker Compose logs...")
        print(f"🔧 Using configuration environment: {profile}")
        
        # Note: This will run in foreground to show logs
        result = run_command("docker compose logs -f")
        
        # This command runs until interrupted, so we may not reach here
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Compose logs failed: {e}")
        return False


@task(help={
})
@config()
def compose_restart(ctx, profile=None):
    """
    Restart Docker Compose services.
    
    This replicates the Makefile's compose-restart target.
    """
    try:
        print("🔄 Restarting Docker Compose services...")
        print(f"🔧 Using configuration environment: {profile}")
        
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
})
@config()
def docker_status(ctx, profile=None):
    """
    Check Docker container status.
    
    This replicates the Makefile's docker-status target.
    """
    try:
        print("🔍 Checking Docker status...")
        print(f"🔧 Using configuration environment: {profile}")
        
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
})
@config()
def docker_cleanup(ctx, profile=None):
    """
    Clean up Docker resources.
    
    This replicates the Makefile's docker-cleanup target.
    """
    try:
        print("🧹 Cleaning up Docker resources...")
        print(f"🔧 Using configuration environment: {profile}")
        
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
