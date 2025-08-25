output "cloud_run_url" {
  description = "URL of the deployed Cloud Run service"
  value       = google_cloud_run_v2_service.api.uri
}

output "cloud_run_service_account_email" {
  description = "Email of the Cloud Run service account"
  value       = google_service_account.cloud_run_sa.email
}

output "firestore_database_name" {
  description = "Name of the Firestore database"
  value       = google_firestore_database.database.name
}

output "firebase_hosting_url" {
  description = "URL of the Firebase Hosting site"
  value       = "https://${google_firebase_hosting_site.default.site_id}.web.app"
}

output "firebase_web_api_key" {
  description = "Firebase Web API key for authentication"
  value       = data.google_firebase_web_app_config.default.api_key
  sensitive   = true
}

output "project_id" {
  description = "GCP Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "current_image_tag" {
  description = "Current image tag deployed to Cloud Run"
  value       = regex(":([^:]+)$", var.full_image_name)[0]
}
