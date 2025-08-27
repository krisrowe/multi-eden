"""Build module for multi-environment applications.

This module handles the smart incremental build pipeline for Docker images,
including git state validation, tag management, and Cloud Build integration.
"""

import subprocess
import sys
import os
from pathlib import Path
from invoke import task
from datetime import datetime





def run_command(cmd, cwd=None, check=True, capture_output=False):
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            check=check,
            capture_output=capture_output,
            text=True
        )
        return result
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e


def validate_git_state():
    """Validate git repository state."""
    repo_root = Path.cwd()
    
    print("🔍 Validating git state...")
    
    # Check if we're in a git repository
    if not (repo_root / ".git").exists():
        raise RuntimeError("❌ Not a git repository")
    
    # Check if remote is configured
    result = run_command("git remote -v", cwd=repo_root, capture_output=True)
    if not result.stdout.strip():
        raise RuntimeError("❌ No remote repository configured")
    
    # Check for uncommitted changes
    result = run_command("git status --porcelain", cwd=repo_root, capture_output=True)
    if result.stdout.strip():
        raise RuntimeError("❌ Working directory has uncommitted changes\nPlease commit or stash changes before building")
    
    # Check if local commits are pushed to remote
    result = run_command("git log --oneline origin/master..HEAD", cwd=repo_root, capture_output=True)
    if result.stdout.strip():
        raise RuntimeError("❌ Local commits not pushed to remote\nPlease push commits before building")
    
    print("✅ Git state validated - clean and current with remote")


def check_build_config():
    """Check if build configuration exists."""
    app_config_path = Path.cwd() / "config" / "app.yaml"
    project_config_path = Path.cwd() / ".config-project"
    
    if not app_config_path.exists():
        raise RuntimeError("❌ App config not found at config/app.yaml")
    
    if not project_config_path.exists():
        raise RuntimeError("❌ Project config not found at .config-project")
    
    return app_config_path, project_config_path


def get_build_config():
    """Read build configuration from app.yaml and .config-project."""
    app_config_path, project_config_path = check_build_config()
    
    # Read app ID from config/app.yaml
    import yaml
    with open(app_config_path) as f:
        app_config = yaml.safe_load(f)
        image_name = app_config.get('id')
    
    # Read project ID from .config-project
    with open(project_config_path) as f:
        project_id = f.read().strip()
    
    if not project_id:
        raise RuntimeError("❌ project_id not found in .config-project")
    
    if not image_name:
        raise RuntimeError("❌ image_name not found in config/app.yaml")
    
    return project_id, image_name


def check_existing_tag():
    """Check if current commit already has a tag."""
    repo_root = Path.cwd()
    current_commit = run_command("git rev-parse HEAD", cwd=repo_root, capture_output=True).stdout.strip()
    existing_tag = run_command("git tag --contains " + current_commit, cwd=repo_root, capture_output=True).stdout.strip()
    
    if existing_tag:
        return existing_tag.split('\n')[0]  # Get first tag
    return None


def check_image_exists(project_id, image_name, tag):
    """Check if Docker image exists in GCR."""
    image_path = f"gcr.io/{project_id}/{image_name}:{tag}"
    result = run_command(f"gcloud container images describe {image_path}", 
                        capture_output=True, check=False)
    return result.returncode == 0


def create_timestamp_tag():
    """Create a new timestamp tag."""
    repo_root = Path.cwd()
    timestamp_tag = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    print(f"🏷️  No existing tag found - creating new timestamp tag...")
    print(f"✅ New tag: {timestamp_tag}")
    
    # Create and push tag
    run_command(f"git tag {timestamp_tag}", cwd=repo_root)
    print("📤 Pushing tag to remote...")
    run_command(f"git push origin {timestamp_tag}", cwd=repo_root)
    print("✅ Tag pushed successfully")
    
    return timestamp_tag


def run_cloud_build(project_id, image_name, tag):
    """Run Cloud Build to create Docker image."""
    print(f"🚀 Starting Cloud Build for tag: {tag}")
    print(f"🔧 Using project: {project_id}")
    
    cmd = f"gcloud builds submit --project={project_id} --tag gcr.io/{project_id}/{image_name}:{tag} ."
    result = run_command(cmd, cwd=Path.cwd())
    
    if result.returncode == 0:
        print("✅ Cloud Build completed successfully")
        return True
    else:
        print("❌ Cloud Build failed")
        return False


@task(help={
    'force': 'Force rebuild even if tag exists',
    'tag': 'Use specific tag instead of auto-detecting'
})
def build(ctx, force=False, tag=None):
    """
    Build new Docker image and manage tags.
    
    Examples:
        invoke build                    # Auto-detect or create tag
        invoke build --force           # Force rebuild
        invoke build --tag=v1.0.0      # Use specific tag
    """
    try:
        print("🏗️  Starting smart incremental build pipeline...")
        
        # Validate git state
        validate_git_state()
        
        # Load environment configuration for build
        try:
            from multi_eden.build.config.env import load_env
            # Use a default environment for build operations
            load_env("dev")  # Default to dev environment for builds
            print(f"🔧 Loaded build configuration from dev environment")
        except Exception as e:
            print(f"⚠️  Could not load build configuration: {e}")
            print(f"⚠️  Continuing with default environment variables")
        
        # Get build configuration
        project_id, image_name = get_build_config()
        print(f"✅ Using project: {project_id}")
        print(f"✅ Using registry: gcr.io/{project_id}")
        print(f"✅ Using image: {image_name}")
        
        # Check for existing tags
        print("🔍 Checking for existing tags and images...")
        
        if tag:
            # Use specified tag
            deploy_tag = tag
            print(f"🏷️ Using specified TAG: {deploy_tag}")
        else:
            # Check if current commit already has a tag
            existing_tag = check_existing_tag()
            if existing_tag:
                deploy_tag = existing_tag
                print(f"✅ Commit already tagged as: {deploy_tag}")
                
                # Check if image exists
                print("🔍 Checking if image exists in GCR...")
                if check_image_exists(project_id, image_name, deploy_tag):
                    print("✅ Image already exists in GCR")
                    print(f"📝 IMAGE_TAG for deployment: {deploy_tag}")
                    print("💡 Use this tag with: invoke deploy")
                    print("")
                    print("🎉 Build pipeline completed (reused existing resources)!")
                    print(f"📦 Image: gcr.io/{project_id}/{image_name}:{deploy_tag}")
                    print(f"🏷️  Tag: {deploy_tag}")
                    print("")
                    print("Next steps:")
                    print("  invoke deploy    # Deploy to Cloud Run")
                    print("  invoke status    # Check deployment status")
                    return True
                else:
                    print("⚠️  Tag exists but image missing - rebuilding image...")
                    if not force:
                        print("💡 Use --force to rebuild existing tag")
                        return False
            else:
                # Create new timestamp tag
                deploy_tag = create_timestamp_tag()
        
        # Run Cloud Build
        if run_cloud_build(project_id, image_name, deploy_tag):
            print(f"📝 IMAGE_TAG for deployment: {deploy_tag}")
            print("💡 Use this tag with: invoke deploy")
            print("")
            print("🎉 Build pipeline completed!")
            print(f"📦 Image: gcr.io/{project_id}/{image_name}:{deploy_tag}")
            print(f"🏷️  Tag: {deploy_tag}")
            print("")
            print("Next steps:")
            print("  invoke deploy    # Deploy to Cloud Run")
            print("  invoke status    # Check deployment status")
            return True
        else:
            return False
            
    except Exception as e:
        print(f"❌ Build failed: {e}")
        return False


@task
def status(ctx):
    """Check build and deployment status."""
    print("🔍 Checking build and deployment status...")
    print("💡 This is a placeholder - implement status checking logic")
    print("   Consider checking:")
    print("   - Docker image tags in GCR")
    print("   - Cloud Run deployment status")
    print("   - Terraform infrastructure state")
