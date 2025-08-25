variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "registry_project_id" {
  description = "GCP Project ID for Container Registry"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "full_image_name" {
  description = "Full Docker image name including registry, project, image name, and tag"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "config_root" {
  description = "Root path to configuration files (relative to Terraform working directory)"
  type        = string
  default     = "."
}


