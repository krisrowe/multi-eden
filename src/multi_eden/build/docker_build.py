"""
Docker Build Management

Handles Docker builds using in-memory Dockerfile generation to avoid
file pollution and cleanup issues.
"""

import subprocess
import logging
import os
import tempfile
import shutil
from pathlib import Path
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
    project_id: Optional[str] = None,
    dockerignore_content: Optional[str] = None
) -> bool:
    """
    Build Docker image using temporary directory with Dockerfile and .dockerignore.
    
    Args:
        dockerfile_content: Dockerfile content as string
        image_name: Name of the Docker image
        tag: Tag for the image
        build_context: Source directory to copy (default: current directory)
        project_id: GCP project ID (for GCR images)
        dockerignore_content: .dockerignore content (optional)
        
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
    logger.debug(f"Source context: {build_context}")
    
    # Create temporary directory for clean build
    with tempfile.TemporaryDirectory(prefix="multi-eden-build-") as temp_dir:
        temp_path = Path(temp_dir)
        logger.debug(f"Using temporary build directory: {temp_dir}")
        
        try:
            # 1. Create Dockerfile in temp directory
            dockerfile_path = temp_path / "Dockerfile"
            dockerfile_path.write_text(dockerfile_content, encoding='utf-8')
            logger.debug("Created Dockerfile in temp directory")
            
            # 2. Create .dockerignore in temp directory
            if dockerignore_content:
                dockerignore_path = temp_path / ".dockerignore"
                dockerignore_path.write_text(dockerignore_content, encoding='utf-8')
                logger.debug("Created .dockerignore in temp directory")
            
            # 3. Copy source files to temp directory
            source_path = Path(build_context).resolve()
            _copy_source_files(source_path, temp_path, dockerignore_content)
            
            # 4. Run docker build with temp directory as context
            cmd = [
                "docker", "build",
                "-t", full_image_name,
                str(temp_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
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
        
        except Exception as e:
            error_msg = f"Build preparation failed: {e}"
            logger.error(error_msg)
            raise DockerBuildError(error_msg)
    
    # Temp directory automatically cleaned up here


def _copy_source_files(source_path: Path, dest_path: Path, dockerignore_content: Optional[str] = None):
    """
    Copy source files to destination, respecting .dockerignore patterns.
    
    Args:
        source_path: Source directory to copy from
        dest_path: Destination directory to copy to
        dockerignore_content: .dockerignore content for filtering
    """
    import fnmatch
    
    # Parse .dockerignore patterns
    ignore_patterns = []
    if dockerignore_content:
        for line in dockerignore_content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                ignore_patterns.append(line)
    
    def should_ignore(file_path: Path, relative_path: str) -> bool:
        """Check if file should be ignored based on .dockerignore patterns."""
        for pattern in ignore_patterns:
            # Handle directory patterns
            if pattern.endswith('/'):
                if file_path.is_dir() and (fnmatch.fnmatch(relative_path + '/', pattern) or 
                                         fnmatch.fnmatch(relative_path, pattern.rstrip('/'))):
                    return True
            else:
                if fnmatch.fnmatch(relative_path, pattern):
                    return True
                # Also check if any parent directory matches
                parts = Path(relative_path).parts
                for i in range(len(parts)):
                    if fnmatch.fnmatch('/'.join(parts[:i+1]), pattern):
                        return True
        return False
    
    # Copy files recursively
    for root, dirs, files in os.walk(source_path):
        root_path = Path(root)
        relative_root = root_path.relative_to(source_path)
        
        # Skip if root directory should be ignored
        if relative_root != Path('.') and should_ignore(root_path, str(relative_root)):
            dirs.clear()  # Don't recurse into ignored directories
            continue
        
        # Create destination directory
        dest_dir = dest_path / relative_root
        dest_dir.mkdir(parents=True, exist_ok=True)
        
        # Filter and remove ignored directories from dirs list
        dirs[:] = [d for d in dirs if not should_ignore(root_path / d, str(relative_root / d))]
        
        # Copy files
        for file in files:
            file_path = root_path / file
            relative_file = relative_root / file
            
            if not should_ignore(file_path, str(relative_file)):
                dest_file = dest_path / relative_file
                shutil.copy2(file_path, dest_file)
                logger.debug(f"Copied: {relative_file}")
            else:
                logger.debug(f"Ignored: {relative_file}")


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
