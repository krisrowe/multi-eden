"""
Docker Build Management

Handles Docker builds using in-memory Dockerfile generation to avoid
file pollution and cleanup issues.
"""

import subprocess
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class DockerBuildError(Exception):
    """Raised when Docker build fails."""
    pass


def build_image_from_memory(
    dockerfile_content: str,
    image_name: str,
    tag: str,
    build_context: str = ".",
    project_id: Optional[str] = None
) -> bool:
    """
    Build Docker image using Dockerfile content from memory.
    
    Args:
        dockerfile_content: Dockerfile content as string
        image_name: Name of the Docker image
        tag: Tag for the image
        build_context: Build context directory (default: current directory)
        project_id: GCP project ID (for GCR images)
        
    Returns:
        True if build succeeded
        
    Raises:
        DockerBuildError: If build fails
    """
    # Construct full image name
    if project_id:
        full_image_name = f"gcr.io/{project_id}/{image_name}:{tag}"
    else:
        full_image_name = f"{image_name}:{tag}"
    
    logger.info(f"Building Docker image: {full_image_name}")
    logger.debug(f"Build context: {build_context}")
    
    # Build command: docker build -f - -t <image> <context>
    cmd = [
        "docker", "build",
        "-f", "-",  # Read Dockerfile from stdin
        "-t", full_image_name,
        build_context
    ]
    
    try:
        result = subprocess.run(
            cmd,
            input=dockerfile_content,
            text=True,
            capture_output=True,
            check=True,
            cwd=build_context
        )
        
        logger.info(f"✅ Docker build completed successfully")
        logger.debug(f"Build output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Docker build failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nError output: {e.stderr}"
        if e.stdout:
            error_msg += f"\nBuild output: {e.stdout}"
        
        logger.error(error_msg)
        raise DockerBuildError(error_msg)


def build_with_cloud_build(
    dockerfile_content: str,
    image_name: str,
    tag: str,
    project_id: str,
    build_context: str = "."
) -> bool:
    """
    Build Docker image using Google Cloud Build with in-memory Dockerfile.
    
    Args:
        dockerfile_content: Dockerfile content as string
        image_name: Name of the Docker image
        tag: Tag for the image
        project_id: GCP project ID
        build_context: Build context directory
        
    Returns:
        True if build succeeded
        
    Raises:
        DockerBuildError: If build fails
    """
    full_image_name = f"gcr.io/{project_id}/{image_name}:{tag}"
    
    logger.info(f"Building with Cloud Build: {full_image_name}")
    
    # Create temporary cloudbuild.yaml content
    cloudbuild_config = f"""
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-f', '-', '-t', '{full_image_name}', '.']
  env:
  - 'DOCKER_BUILDKIT=1'
images:
- '{full_image_name}'
"""
    
    try:
        # Submit build with inline config and Dockerfile
        cmd = [
            "gcloud", "builds", "submit",
            "--project", project_id,
            "--config", "-",  # Read cloudbuild.yaml from stdin
            build_context
        ]
        
        # Combine cloudbuild.yaml and Dockerfile
        combined_input = f"{cloudbuild_config}\n---DOCKERFILE---\n{dockerfile_content}"
        
        result = subprocess.run(
            cmd,
            input=combined_input,
            text=True,
            capture_output=True,
            check=True,
            cwd=build_context
        )
        
        logger.info(f"✅ Cloud Build completed successfully")
        logger.debug(f"Build output: {result.stdout}")
        return True
        
    except subprocess.CalledProcessError as e:
        error_msg = f"Cloud Build failed with exit code {e.returncode}"
        if e.stderr:
            error_msg += f"\nError output: {e.stderr}"
        
        logger.error(error_msg)
        raise DockerBuildError(error_msg)


def check_docker_available() -> bool:
    """
    Check if Docker is available and running.
    
    Returns:
        True if Docker is available
    """
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            check=True,
            timeout=10
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_gcloud_available() -> bool:
    """
    Check if gcloud CLI is available and authenticated.
    
    Returns:
        True if gcloud is available and authenticated
    """
    try:
        # Check if gcloud is installed
        result = subprocess.run(
            ["gcloud", "version"],
            capture_output=True,
            check=True,
            timeout=10
        )
        
        # Check if authenticated
        result = subprocess.run(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            capture_output=True,
            check=True,
            timeout=10
        )
        
        return bool(result.stdout.strip())
        
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False
