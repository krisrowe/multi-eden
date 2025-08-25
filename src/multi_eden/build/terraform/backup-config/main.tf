# Configuration Backup Module
# This module completely mirrors the local {repo}/config/ to GCS configuration bucket
# Creates an exact copy of all files and folders from local config directory to GCS

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

# Read project ID from .config-project file
data "local_file" "project_id" {
  filename = "${path.module}/../../.config-project"
}

# Get project details and discover bucket from labels
data "google_project" "current" {
  project_id = trimspace(data.local_file.project_id.content)
}

locals {
  project_id   = trimspace(data.local_file.project_id.content)
  config_bucket = "gs://${data.google_project.current.labels["multi-env-sdk-config-bucket"]}"
  bucket_name   = data.google_project.current.labels["multi-env-sdk-config-bucket"]
  repo_root     = "${path.module}/../.."
}

# Ensure GCS bucket exists with versioning enabled
resource "google_storage_bucket" "config_bucket" {
  name          = local.bucket_name
  project       = local.project_id
  location      = "US"  # You can make this configurable
  force_destroy = false

  versioning {
    enabled = true
  }

  lifecycle {
    ignore_changes = [
      location,
      storage_class,
      labels,
      website,
      cors,
      lifecycle_rule,
      retention_policy,
      encryption
    ]
  }
}

# Complete bucket sync from local config directory (smart timestamp-based)
resource "null_resource" "mirror_local_to_gcs" {
  depends_on = [google_storage_bucket.config_bucket]
  
  triggers = {
    bucket = local.config_bucket
    # Force refresh every time to ensure we get latest changes
    timestamp = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "🔧 Mirroring local config directory to GCS bucket..."
      echo "📁 Source: ${local.repo_root}/config/"
      echo "☁️  Destination: ${local.config_bucket}"
      
      # Ensure config directory exists
      if [ ! -d "${local.repo_root}/config" ]; then
        echo "❌ Local config directory not found: ${local.repo_root}/config"
        exit 1
      fi
      
      # Use gsutil rsync for smart timestamp-based syncing
      # -r: recursive
      # No flags needed - uses smart timestamp comparison by default
      echo "🔄 Starting smart sync (only updates changed files)..."
      gsutil -m rsync -r "${local.repo_root}/config/" "${local.config_bucket}"
      
      if [ $? -eq 0 ]; then
        echo "✅ Smart sync completed successfully!"
        echo "📊 Only files with different timestamps/sizes were updated"
      else
        echo "❌ Sync failed"
        exit 1
      fi
    EOT
  }
}

# Outputs
output "config_bucket" {
  description = "Configuration bucket being used"
  value       = local.config_bucket
}

output "project_id" {
  description = "GCP Project ID being used"
  value       = local.project_id
}

output "local_config_path" {
  description = "Local path where configuration was mirrored from"
  value       = "${local.repo_root}/config"
}

output "mirror_status" {
  description = "Configuration mirror status"
  value = {
    bucket_mirrored = null_resource.mirror_local_to_gcs.id != null
    local_path      = "${local.repo_root}/config"
    gcs_destination = local.config_bucket
    versioning      = google_storage_bucket.config_bucket.versioning[0].enabled
  }
}
