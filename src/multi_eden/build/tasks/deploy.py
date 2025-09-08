"""Deploy module for multi-environment applications."""

import json
import os
import subprocess
import sys
from pathlib import Path
from invoke import task

try:
    from .local import run_command
    from .config.setup import get_sdk_root
except ImportError:
    from local import run_command
    from config.setup import get_sdk_root


def validate_environment(target):
    """Validate that target is specified and required config files exist."""
    if not target:
        raise RuntimeError("❌ Target not specified. Usage: invoke deploy --target=dev|prod|staging")
    
    # Check secrets file
    secrets_path = Path.cwd() / "config" / "secrets" / f"{target}" / "secrets.json"
    if not secrets_path.exists():
        raise RuntimeError(f"❌ Secrets file not found: {secrets_path}")
    
    # Check providers configuration file
    providers_path = Path.cwd() / "config" / "settings" / f"{target}" / "providers.json"
    if not providers_path.exists():
        raise RuntimeError(f"❌ Providers configuration file not found: {providers_path}")
    
    print(f"✅ Target validation passed:")
    print(f"   Secrets: {secrets_path}")
    print(f"   Providers: {providers_path}")
    
    return secrets_path


def read_secrets(secrets_path):
    """Read secrets from JSON file."""
    try:
        with open(secrets_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        raise RuntimeError(f"❌ Failed to read secrets file: {e}")


def detect_deploy_tag(tag=None):
    """Detect or use specified deployment tag."""
    if tag:
        return tag
    
    # Get latest git tag
    result = run_command("git describe --tags --abbrev=0", capture_output=True, check=False)
    if result.returncode == 0:
        return result.stdout.strip()
    
    # Fallback to timestamp
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def verify_image_exists(project_id, image_name, tag):
    """Verify that the Docker image exists in the registry."""
    if not project_id or not image_name:
        raise RuntimeError("❌ Missing project_id or image_name")
    
    # Check if image exists in GCR
    image_url = f"gcr.io/{project_id}/{image_name}:{tag}"
    print(f"🔍 Checking if image exists: {image_url}")
    
    result = run_command(f"gcloud container images describe {image_url}", 
                        capture_output=True, check=False)
    
    if result.returncode != 0:
        raise RuntimeError(f"❌ Image not found: {image_url}")
    
    return True


def run_terraform_deploy(project_id, full_image_name, target):
    """Run Terraform deployment."""
    terraform_dir = get_sdk_root() / "terraform" / "infra"
    
    # Change to terraform directory and run terraform
    original_cwd = Path.cwd()
    try:
        os.chdir(terraform_dir)
        
        # Initialize terraform if needed
        if not (terraform_dir / ".terraform").exists():
            print("🔧 Initializing Terraform...")
            run_command("terraform init")
        
        # Run terraform apply with absolute paths
        print("🚀 Running Terraform deployment...")
        repo_root = str(original_cwd.absolute())
        cmd = f"terraform apply -auto-approve -var=project_id={project_id} -var=registry_project_id={project_id} -var=full_image_name={full_image_name} -var=environment={target} -var=config_root={repo_root}/config"
        
        result = run_command(cmd)
        if result.returncode == 0:
            print("✅ Terraform deployment completed successfully")
            return True
        else:
            print(f"❌ Terraform deployment failed with exit code {result.returncode}")
            return False
            
    finally:
        os.chdir(original_cwd)


@task(help={
    'target': 'Target environment to deploy to (dev|prod|staging)',
    'tag': 'Specific image tag to deploy (optional)'
})
def deploy(ctx, target=None, tag=None):
    """
    Deploy API to Google Cloud Run.
    
    Usage:
        invoke deploy --target=dev                    # Deploy to dev environment
        invoke deploy --target=prod                   # Deploy to prod environment
        invoke deploy --target=dev --tag=v1.0.0       # Deploy specific tag to dev
    
    All configuration is read from the mounted secrets file.
    """
    try:
        if not target:
            raise RuntimeError("❌ Target not specified. Usage: invoke deploy --target=dev|prod|staging")
        
        # Get project_id and image_name from the same source as build task
        from .build import get_build_config
        project_id, image_name = get_build_config()
        
        deploy_tag = detect_deploy_tag(tag)
        verify_image_exists(project_id, image_name, deploy_tag)
        
        # Construct the full image name for Terraform
        full_image_name = f"gcr.io/{project_id}/{image_name}:{deploy_tag}"
        
        if run_terraform_deploy(project_id, full_image_name, target):
            print(f"🎉 Deployment to {target} environment completed successfully!")
            print(f"📦 Image: gcr.io/{project_id}/{image_name}:{deploy_tag}")
            print(f"🏷️  Tag: {deploy_tag}")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        return False


@task(help={
    'api-url': 'API URL to use for frontend (optional, auto-detected if not specified)'
})
def deploy_web(ctx, api_url=None):
    """
    Deploy frontend to Firebase Hosting.
    """
    try:
        print("🌍 Deploying frontend to Firebase Hosting...")
        
        # Check Firebase CLI
        print("🔍 Checking Firebase CLI...")
        if not run_command("firebase --version", capture_output=True, check=False).returncode == 0:
            raise RuntimeError("❌ Firebase CLI not found. Install with: npm install -g firebase-tools")
        
        # Get Cloud Run API URL
        print("📝 Getting Cloud Run API URL...")
        if not api_url:
            # Use terraform/infra directory in the current project
            terraform_dir = Path.cwd() / "terraform" / "infra"
            
            # Change to terraform directory temporarily to get output
            original_cwd = Path.cwd()
            try:
                os.chdir(terraform_dir)
                result = run_command("terraform output -raw cloud_run_url", 
                                   capture_output=True, check=False)
                if result.returncode == 0:
                    api_url = result.stdout.strip()
                else:
                    api_url = "http://localhost:8001"
            finally:
                os.chdir(original_cwd)
        
        print(f"✅ Using API URL: {api_url}")
        
        # Build frontend
        frontend_dir = Path.cwd() / "frontend"
        
        print("🔨 Triggering Terraform frontend deployment...")
        
        # Get project_id and image_name from the same source as build task
        from .build import get_build_config
        project_id, image_name = get_build_config()
        
        # Use the same Terraform deployment function that the main deploy task uses
        # This ensures all required variables are provided
        deploy_tag = detect_deploy_tag(None)  # Use default tag detection
        full_image_name = f"gcr.io/{project_id}/{image_name}:{deploy_tag}"
        
        # Run Terraform deployment which will trigger the null_resource
        # Use dev as default target for frontend deployment
        if run_terraform_deploy(project_id, full_image_name, "dev"):  # Assuming dev environment
            print("✅ Terraform frontend deployment completed!")
        else:
            raise RuntimeError("❌ Terraform deployment failed")
        
        print("✅ Frontend deployment completed via Terraform!")
        return True
        
    except Exception as e:
        print(f"❌ Frontend deployment failed: {e}")
        return False


@task
def status(ctx):
    """Check deployment status."""
    print("🔍 Checking deployment status...")
    print("💡 This is a placeholder - implement status checking logic")
    print("   Consider checking:")
    print("   - Cloud Run service status")
    print("   - Terraform infrastructure state")
    print("   - Image registry status")
    return True
