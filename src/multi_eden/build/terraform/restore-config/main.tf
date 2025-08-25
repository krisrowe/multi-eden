# Configuration Restore Module
# This module completely mirrors the GCS configuration bucket to local {repo}/config/
# Creates an exact copy of all files and folders from GCS to local config directory

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
  repo_root     = "${path.module}/../.."
}

# Variables
variable "environment" {
  description = "Environment to restore configuration for (dev, prod, staging)"
  type        = string
  
  validation {
    condition     = contains(["dev", "prod", "staging"], var.environment)
    error_message = "Environment must be one of: dev, prod, staging."
  }
}

# Complete bucket sync to local config directory (smart timestamp-based)
resource "null_resource" "mirror_gcs_to_local" {
  triggers = {
    bucket = local.config_bucket
    # Force refresh every time to ensure we get latest changes
    timestamp = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "🔧 Mirroring GCS bucket to local config directory..."
      echo "☁️  Source: ${local.config_bucket}"
      echo "📁 Destination: ${local.repo_root}/config/"
      
      # Ensure config directory exists
      mkdir -p "${local.repo_root}/config"
      
      # Use gsutil rsync for smart timestamp-based syncing
      # -r: recursive
      # No flags needed - uses smart timestamp comparison by default
      echo "🔄 Starting smart sync (only updates changed files)..."
      gsutil -m rsync -r "${local.config_bucket}" "${local.repo_root}/config/"
      
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

output "environment" {
  description = "Environment being restored"
  value       = var.environment
}

output "local_config_path" {
  description = "Local path where configuration was mirrored"
  value       = "${local.repo_root}/config"
}

output "mirror_status" {
  description = "Configuration mirror status"
  value = {
    bucket_mirrored = null_resource.mirror_gcs_to_local.id != null
    local_path      = "${local.repo_root}/config"
    gcs_source      = local.config_bucket
  }
}
