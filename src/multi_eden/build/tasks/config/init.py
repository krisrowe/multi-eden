"""
Multi-Environment SDK Deployment Module

Generic, reusable deployment and infrastructure functions.
No project-specific code - completely domain-agnostic.
"""

import subprocess
from pathlib import Path
from invoke import task





class ConfigInitError(Exception):
    """Base exception for configuration initialization errors."""
    pass

class InvalidProjectIdError(ConfigInitError):
    """Raised when project_id is invalid or missing."""
    pass

class InvalidAppIdError(ConfigInitError):
    """Raised when app_id is invalid or missing."""
    pass

class MultipleConfigBucketsError(ConfigInitError):
    """Raised when project has multiple config buckets."""
    pass

class BucketNameConflictError(ConfigInitError):
    """Raised when requested bucket name conflicts with existing config bucket."""
    pass

class BucketCreationError(ConfigInitError):
    """Raised when bucket creation fails."""
    pass

class LabelApplicationError(ConfigInitError):
    """Raised when applying labels to bucket fails."""
    pass

class AppYamlMismatchError(ConfigInitError):
    """Raised when existing app.yaml has different app_id."""
    pass

class AppYamlCreationError(ConfigInitError):
    """Raised when app.yaml creation/upload fails."""
    pass


@task
def init_config(ctx, project_id: str = None, app_id: str = None, bucket_name: str = None) -> None:
    """
    Ensures a GCS bucket exists with proper labels for configuration storage.
    Also creates/verifies app.yaml file with the app_id.

    Args:
        project_id: GCP Project ID (required).
        app_id: Application ID to store in app.yaml (required).
        bucket_name: Optional GCS bucket name.

    Raises:
        InvalidProjectIdError: When project_id is empty or invalid
        InvalidAppIdError: When app_id is empty or invalid
        MultipleConfigBucketsError: When project has multiple config buckets
        BucketNameConflictError: When bucket name conflicts with existing config bucket
        BucketCreationError: When bucket creation fails
        LabelApplicationError: When applying labels fails
        AppYamlMismatchError: When existing app.yaml has different app_id
        AppYamlCreationError: When app.yaml creation/upload fails
    """
    from multi_eden.internal import gcp
    import subprocess
    
    if not project_id:
        raise InvalidProjectIdError("Must specify a project id.")
    
    if not app_id:
        raise InvalidAppIdError("Must specify an app id.")

    # --- EARLY VALIDATION: Check .config-project file BEFORE any cloud operations ---
    try:
        print(f"    📝 Validating .config-project file...")
        
        # Get the current working directory (where user ran the command)
        cwd = Path.cwd()
        config_project_file = cwd / ".config-project"
        
        # Check if .config-project already exists
        if config_project_file.exists():
            existing_project_id = config_project_file.read_text().strip()
            
            if existing_project_id and existing_project_id != "":
                # File exists with non-blank content
                if existing_project_id != project_id:
                    print(f"    ❌ ERROR: .config-project file already exists with different project ID!")
                    print(f"    📁 File location: {config_project_file}")
                    print(f"    📋 Current project ID: {existing_project_id}")
                    print(f"    🎯 Requested project ID: {project_id}")
                    print(f"    💡 The config project is the MASTER project for ALL environments in this application solution.")
                    print(f"    💡 Changing it will affect backup/restore operations for ALL environments.")
                    print(f"    💡 If you intend to change the config project, you must:")
                    print(f"       1. Delete the existing file: rm {config_project_file}")
                    print(f"       2. Or manually update it: echo '{project_id}' > {config_project_file}")
                    print(f"       3. Then re-run this command")
                    raise BucketNameConflictError(
                        f"Cannot change config project from '{existing_project_id}' to '{project_id}'. "
                        f"Config project is the master project for all environments. "
                        f"Manually update or delete {config_project_file} if this change is intentional."
                    )
                else:
                    print(f"    ✅ .config-project file already exists with correct project ID: {existing_project_id}")
            else:
                # File exists but is empty/null - safe to overwrite later
                print(f"    ℹ️  .config-project file exists but is empty - will update after successful completion")
        else:
            # File doesn't exist - will create after successful completion
            print(f"    ℹ️  .config-project file doesn't exist - will create after successful completion")
            
    except Exception as e:
        print(f"    ❌ Error validating .config-project file: {e}")
        raise e

    print(f"    🚀 Ensuring configuration bucket for project: {project_id}")

    # Determine target bucket name once
    target_bucket_name = bucket_name if bucket_name else f"{app_id}-config"

    # Import shared constants
    try:
        from .constants import CONFIG_BUCKET_LABEL_KEY, CONFIG_BUCKET_LABEL_VALUE
    except ImportError:
        from constants import CONFIG_BUCKET_LABEL_KEY, CONFIG_BUCKET_LABEL_VALUE

    # --- Pre-flight Check ---
    # Check if there are any config buckets in the project with the config label
    existing_config_buckets = gcp.find_config_buckets_by_label(project_id, CONFIG_BUCKET_LABEL_KEY, CONFIG_BUCKET_LABEL_VALUE)
    
    if len(existing_config_buckets) > 1:
        print(f"    ❌ Error: Project has multiple config buckets: {existing_config_buckets}")
        print(f"    💡 Only one config bucket per project is allowed. Please remove extra buckets or their config labels.")
        raise MultipleConfigBucketsError(f"Project has multiple config buckets: {existing_config_buckets}")
    elif len(existing_config_buckets) == 1:
        existing_config_bucket = existing_config_buckets[0]
        print(f"    ℹ️ Found existing config bucket: {existing_config_bucket}")
        
        # The target bucket MUST match the existing labeled bucket
        if target_bucket_name != existing_config_bucket:
            print(f"    ❌ Error: Project already has config bucket '{existing_config_bucket}', cannot use '{target_bucket_name}'.")
            if bucket_name:
                print(f"    💡 Either use the existing bucket or remove its config label first.")
            else:
                print(f"    💡 The app_id '{app_id}' would create bucket '{target_bucket_name}', but config bucket '{existing_config_bucket}' already exists.")
            raise BucketNameConflictError(f"Project already has config bucket '{existing_config_bucket}', cannot use '{target_bucket_name}'")
        
        print(f"    👍 Using existing config bucket: {target_bucket_name}")
        # Still need to verify app.yaml file
        skip_bucket_creation = True
    else:
        # No existing config bucket found
        print(f"    📝 Creating new bucket: {target_bucket_name}")
        skip_bucket_creation = False
    # --- End of Pre-flight Check ---

    # Create bucket if it doesn't exist (unless we found an existing one)
    if not skip_bucket_creation:
        try:
            print(f"    🪣 Creating bucket '{target_bucket_name}' if it doesn't exist...")
            result = subprocess.run([
                "gsutil", "mb", "-p", project_id, f"gs://{target_bucket_name}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ Created bucket: {target_bucket_name}")
            elif "already exists" in result.stderr.lower():
                print(f"    ℹ️ Bucket already exists: {target_bucket_name}")
            else:
                print(f"    ❌ Failed to create bucket: {result.stderr}")
                raise BucketCreationError(f"Failed to create bucket: {result.stderr}")
        except Exception as e:
            print(f"    ❌ Error creating bucket: {e}")
            raise BucketCreationError(f"Error creating bucket: {e}")

        # Apply label to the bucket
        try:
            print(f"    🏷️ Applying config label to bucket...")
            result = subprocess.run([
                "gsutil", "label", "ch", 
                f"-l", f"{CONFIG_BUCKET_LABEL_KEY}:{CONFIG_BUCKET_LABEL_VALUE}",
                f"gs://{target_bucket_name}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ Applied labels to bucket: {target_bucket_name}")
            else:
                print(f"    ❌ Failed to apply labels: {result.stderr}")
                raise LabelApplicationError(f"Failed to apply labels: {result.stderr}")
        except Exception as e:
            print(f"    ❌ Error applying labels: {e}")
            raise LabelApplicationError(f"Error applying labels: {e}")

        # Enable versioning on the bucket
        try:
            print(f"    🔄 Enabling versioning on bucket...")
            result = subprocess.run([
                "gsutil", "versioning", "set", "on", f"gs://{target_bucket_name}"
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"    ✅ Enabled versioning on bucket: {target_bucket_name}")
            else:
                print(f"    ❌ Failed to enable versioning: {result.stderr}")
                raise LabelApplicationError(f"Failed to enable versioning: {result.stderr}")
        except Exception as e:
            print(f"    ❌ Error enabling versioning: {e}")
            raise LabelApplicationError(f"Error enabling versioning: {e}")
    else:
        # For existing buckets, ensure versioning is enabled
        try:
            print(f"    🔄 Checking versioning on existing bucket...")
            versioning_result = subprocess.run([
                "gsutil", "versioning", "get", f"gs://{target_bucket_name}"
            ], capture_output=True, text=True)
            
            if versioning_result.returncode == 0:
                versioning_status = versioning_result.stdout.strip()
                if "Enabled" in versioning_status:
                    print(f"    ✅ Versioning already enabled on bucket: {target_bucket_name}")
                else:
                    print(f"    🔄 Enabling versioning on existing bucket...")
                    enable_result = subprocess.run([
                        "gsutil", "versioning", "set", "on", f"gs://{target_bucket_name}"
                    ], capture_output=True, text=True)
                    
                    if enable_result.returncode == 0:
                        print(f"    ✅ Enabled versioning on existing bucket: {target_bucket_name}")
                    else:
                        print(f"    ❌ Failed to enable versioning: {enable_result.stderr}")
                        raise LabelApplicationError(f"Failed to enable versioning: {enable_result.stderr}")
            else:
                print(f"    ❌ Failed to check versioning: {versioning_result.stderr}")
                raise LabelApplicationError(f"Failed to check versioning: {versioning_result.stderr}")
        except Exception as e:
            print(f"    ❌ Error checking/enabling versioning: {e}")
            raise LabelApplicationError(f"Error checking/enabling versioning: {e}")

    # Check/create app.yaml file with app_id
    try:
        print(f"    📝 Checking/creating app.yaml file...")
        
        # Check if app.yaml already exists
        check_result = subprocess.run([
            "gsutil", "cat", f"gs://{target_bucket_name}/app.yaml"
        ], capture_output=True, text=True)
        
        if check_result.returncode == 0:
            # File exists, verify app_id matches
            existing_content = check_result.stdout.strip()
            expected_content = f"id: {app_id}"
            if existing_content != expected_content:
                print(f"    ❌ Error: Existing app.yaml has different app_id")
                print(f"    ❌ Expected: {expected_content}")
                print(f"    ❌ Found: {existing_content}")
                raise AppYamlMismatchError(f"Existing app.yaml has different app_id. Expected: {expected_content}, Found: {existing_content}")
            print(f"    ✅ Verified existing app.yaml matches app_id: {app_id}")
        else:
            # File doesn't exist, create it
            app_yaml_content = f"id: {app_id}\n"
            
            # Create temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp_file:
                temp_file.write(app_yaml_content)
                temp_file_path = temp_file.name
            
            try:
                # Upload to bucket
                upload_result = subprocess.run([
                    "gsutil", "cp", temp_file_path, f"gs://{target_bucket_name}/app.yaml"
                ], capture_output=True, text=True)
                
                if upload_result.returncode == 0:
                    print(f"    ✅ Created app.yaml with app_id: {app_id}")
                else:
                    print(f"    ❌ Failed to upload app.yaml: {upload_result.stderr}")
                    raise AppYamlCreationError(f"Failed to upload app.yaml: {upload_result.stderr}")
            finally:
                # Clean up temp file
                import os
                os.unlink(temp_file_path)
                
    except Exception as e:
        print(f"    ❌ Error handling app.yaml: {e}")
        raise AppYamlCreationError(f"Error handling app.yaml: {e}")

    # --- Final Step: Create/Validate .config-project file ---
    try:
        print(f"    📝 Managing .config-project file...")
        
        # Get the current working directory (where user ran the command)
        cwd = Path.cwd()
        config_project_file = cwd / ".config-project"
        
        # Check if .config-project already exists
        if config_project_file.exists():
            existing_project_id = config_project_file.read_text().strip()
            
            if existing_project_id and existing_project_id != "":
                # File exists with non-blank content
                if existing_project_id != project_id:
                    print(f"    ⚠️  WARNING: .config-project file already exists with different project ID!")
                    print(f"    📁 File location: {config_project_file}")
                    print(f"    📋 Current project ID: {existing_project_id}")
                    print(f"    🎯 Requested project ID: {project_id}")
                    print(f"    💡 The config project is the MASTER project for ALL environments in this application solution.")
                    print(f"    💡 Changing it will affect backup/restore operations for ALL environments.")
                    print(f"    💡 If you intend to change the config project, you must:")
                    print(f"       1. Delete the existing file: rm {config_project_file}")
                    print(f"       2. Or manually update it: echo '{project_id}' > {config_project_file}")
                    print(f"       3. Then re-run this command")
                    raise BucketNameConflictError(
                        f"Cannot change config project from '{existing_project_id}' to '{project_id}'. "
                        f"Config project is the master project for all environments. "
                        f"Manually update or delete {config_project_file} if this change is intentional."
                    )
                else:
                    print(f"    ✅ .config-project file already exists with correct project ID: {existing_project_id}")
            else:
                # File exists but is empty/null - safe to overwrite
                print(f"    📝 .config-project file exists but is empty - updating with project ID: {project_id}")
                config_project_file.write_text(project_id)
                print(f"    ✅ Updated .config-project file with project ID: {project_id}")
        else:
            # File doesn't exist - create it
            print(f"    📝 Creating .config-project file with project ID: {project_id}")
            config_project_file.write_text(project_id)
            print(f"    ✅ Created .config-project file with project ID: {project_id}")
            
    except Exception as e:
        print(f"    ❌ Error managing .config-project file: {e}")
        raise e

    print(f"    ✅ Configuration bucket ready: {target_bucket_name}")
    print(f"    ✅ .config-project file ready: {Path.cwd() / '.config-project'}")


# The wrapper function was removed - the @task decorated init_config above handles everything

