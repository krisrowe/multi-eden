terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project                     = var.project_id
  region                      = var.region
  user_project_override       = true
  billing_project             = var.project_id
}

# Read app configuration
data "local_file" "app_config" {
  filename = "${var.config_root}/app.yaml"
}

locals {
  app_config = yamldecode(data.local_file.app_config.content)
  app_id = local.app_config.id
}

# Data source for environment-specific secrets file
data "local_file" "environment_secrets" {
  filename = "${var.config_root}/secrets/${var.environment}/secrets.json"
  
  # Validate that the file exists and contains valid JSON
  lifecycle {
    precondition {
      condition     = fileexists("${var.config_root}/secrets/${var.environment}/secrets.json")
      error_message = "Environment secrets file not found: ${var.config_root}/secrets/${var.environment}/secrets.json. Please ensure it exists before deploying."
    }
  }
}

# Data source for environment-specific providers configuration
data "local_file" "environment_providers" {
  filename = "${var.config_root}/settings/${var.environment}/providers.json"
  
  # Validate that the file exists and contains valid JSON
  lifecycle {
    precondition {
      condition     = fileexists("${var.config_root}/settings/${var.environment}/providers.json")
      error_message = "Environment providers file not found: ${var.config_root}/settings/${var.environment}/providers.json. Please ensure it exists before deploying."
    }
  }
}

# Create/update the environment secrets in Secret Manager
resource "google_secret_manager_secret" "environment_secrets" {
  secret_id = "${local.app_id}-environment-secrets"
  project   = var.project_id
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "environment_secrets" {
  secret      = google_secret_manager_secret.environment_secrets.id
  secret_data = data.local_file.environment_secrets.content
}

# Create/update the environment providers configuration in Secret Manager
resource "google_secret_manager_secret" "environment_providers" {
  secret_id = "${local.app_id}-environment-providers"
  project   = var.project_id
  
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "environment_providers" {
  secret      = google_secret_manager_secret.environment_providers.id
  secret_data = data.local_file.environment_providers.content
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "firestore.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "firebase.googleapis.com",
    "identitytoolkit.googleapis.com"
  ])
  
  project = var.project_id
  service = each.value
  
  disable_dependent_services = false
  disable_on_destroy         = false
}

# Firestore Database - configured to match existing database
# Uses lifecycle rule to prevent recreation on repeated deployments
resource "google_firestore_database" "database" {
  provider = google-beta
  
  project                           = var.project_id
  name                              = "(default)"
  location_id                       = "us-central1"
  type                              = "FIRESTORE_NATIVE"
  concurrency_mode                  = "PESSIMISTIC"
  app_engine_integration_mode       = "DISABLED"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state           = "DELETE_PROTECTION_DISABLED"
  deletion_policy                   = "ABANDON"
  
  depends_on = [google_project_service.apis]
}

# Docker images are built and pushed manually via 'make build-and-deploy'
# This ensures we only build when explicitly requested, not on every terraform apply

# Service Account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "${local.app_id}-api"
  display_name = "${local.app_id} API Service Account"
  description  = "Service account for ${local.app_id} Cloud Run service"
}

# IAM roles for Cloud Run service account
resource "google_project_iam_member" "cloud_run_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloud_run_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Cloud Run v2 Service (supports volume mounts)
resource "google_cloud_run_v2_service" "api" {
  name     = "${local.app_id}-api"
  location = var.region
  
  template {
    service_account = google_service_account.cloud_run_sa.email
    
    volumes {
      name = "environment-secrets-vol"
      secret {
        secret = google_secret_manager_secret.environment_secrets.secret_id
        items {
          version = "latest"
          path = "secrets.json"
        }
      }
    }
    
    volumes {
      name = "environment-providers-vol"
      secret {
        secret = google_secret_manager_secret.environment_providers.secret_id
        items {
          version = "latest"
          path = "providers.json"
        }
      }
    }
    
    containers {
      image = var.full_image_name
      
      command = ["python", "-m", "core.api", "--config-env=static"]
      
      ports {
        container_port = 8080
      }
      
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.database.name
      }
      
      env {
        name  = "CORS_ORIGINS"
        value = "https://${var.project_id}.web.app,https://${var.project_id}.firebaseapp.com"
      }
      
      env {
        name  = "FIREBASE_PROJECT_ID"
        value = var.project_id
      }
      
      env {
        name  = "REQUIRE_FIREBASE_AUTH"
        value = "true"
      }
      
      env {
        name  = "CONFIG_ENV"
        value = "static"
      }
            
     
      volume_mounts {
        name = "environment-secrets-vol"
        mount_path = "/app/config/secrets/static"
      }
      
      volume_mounts {
        name = "environment-providers-vol"
        mount_path = "/app/config/settings/static"
      }
      
      resources {
        limits = {
          cpu    = "1000m"
          memory = "512Mi"
        }
      }
    }
    
    scaling {
      min_instance_count = 0  # Allow scaling to zero to save costs when not in use
      max_instance_count = 1  # Cap at 1 instance to prevent runaway scaling costs
    }
    
    annotations = {
      "run.googleapis.com/cpu-throttling" = "false"
      # Cost protection: Cap at 1 instance max, allow scaling to zero
      "autoscaling.knative.dev/maxScale" = "1"
      "autoscaling.knative.dev/minScale" = "0"
    }
  }
  
  traffic {
    percent = 100
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
  }
  
  depends_on = [
    google_project_service.apis,
    google_service_account.cloud_run_sa,
    google_firestore_database.database,
    google_secret_manager_secret_version.environment_secrets,
    google_secret_manager_secret_version.environment_providers
  ]
}

# Allow unauthenticated access to Cloud Run (for public API)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Firebase project configuration
resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id
  
  depends_on = [google_project_service.apis]
}

# Firebase Hosting site
resource "google_firebase_hosting_site" "default" {
  provider = google-beta
  project  = var.project_id
  site_id  = var.project_id
  
  depends_on = [google_firebase_project.default]
}

# Firebase Web App for authentication
resource "google_firebase_web_app" "default" {
  provider     = google-beta
  project      = var.project_id
  display_name = "${local.app_id} Web App"
  
  depends_on = [google_firebase_project.default]
}

# Data source to get Firebase Web App configuration including API key
data "google_firebase_web_app_config" "default" {
  provider   = google-beta
  project    = var.project_id
  web_app_id = google_firebase_web_app.default.app_id
  
  depends_on = [google_firebase_web_app.default]
}

# Enable Firebase Authentication
resource "google_identity_platform_config" "auth" {
  provider = google-beta
  project  = var.project_id
  
  # Configure sign-in methods
  sign_in {
    allow_duplicate_emails = false
    
    # Disable email/password authentication
    email {
      enabled           = false
      password_required = false
    }
    
    # Disable anonymous authentication
    anonymous {
      enabled = false
    }
  }
  
  depends_on = [google_firebase_project.default]
}

# Note: Google Sign-In is automatically available in Firebase Authentication
# You'll need to configure the OAuth client in the Firebase Console:
# 1. Go to Firebase Console > Authentication > Sign-in method
# 2. Enable Google provider
# 3. Add your domain to authorized domains

# Build and deploy frontend to Firebase Hosting
resource "null_resource" "deploy_frontend" {
  # Trigger redeployment when Cloud Run URL changes, Firebase config changes, or frontend code changes
  triggers = {
    cloud_run_url = google_cloud_run_v2_service.api.uri
    firebase_config = data.google_firebase_web_app_config.default.api_key
    environment = var.environment
    # Trigger on frontend code changes by using git commit hash
    frontend_code_hash = substr(sha256(join("", [
      for f in fileset("${path.module}/../../frontend/src", "**/*"): 
      filesha256("${path.module}/../../frontend/src/${f}")
    ])), 0, 8)
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      echo "🔧 Building frontend for Firebase Hosting..."
      
      # Get the Cloud Run URL
      API_URL="${google_cloud_run_v2_service.api.uri}"
      
      # Get Firebase configuration
      FIREBASE_API_KEY="${data.google_firebase_web_app_config.default.api_key}"
      FIREBASE_AUTH_DOMAIN="${var.project_id}.firebaseapp.com"
      FIREBASE_PROJECT_ID="${var.project_id}"
      
      # Navigate to frontend directory
      cd "${path.module}/../../../frontend"
      
      # Install dependencies if needed
      if [ ! -d "node_modules" ]; then
        echo "📦 Installing frontend dependencies..."
        npm install
      fi
      
      # Build frontend with environment variables
      echo "🏗️ Building frontend with API_URL=$API_URL"
      VITE_API_URL="$API_URL" \
      VITE_FIREBASE_API_KEY="$FIREBASE_API_KEY" \
      VITE_FIREBASE_AUTH_DOMAIN="$FIREBASE_AUTH_DOMAIN" \
      VITE_FIREBASE_PROJECT_ID="$FIREBASE_PROJECT_ID" \
      npm run build
      
      # Deploy to Firebase Hosting
      echo "🚀 Deploying to Firebase Hosting..."
      firebase deploy --only hosting --project "${var.project_id}"
      
      echo "✅ Frontend deployed to Firebase Hosting!"
    EOT
  }

  depends_on = [
    google_cloud_run_v2_service.api,
    google_firebase_hosting_site.default,
    data.google_firebase_web_app_config.default
  ]
}
