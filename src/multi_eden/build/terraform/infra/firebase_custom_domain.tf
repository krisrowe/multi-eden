# Custom domain configuration for Firebase Hosting
# This will automatically provision SSL certificates
# Domain configuration is read from environment secrets file

locals {
  environment_config = jsondecode(data.local_file.environment_secrets.content)
  
  # Extract domain configuration from secrets (optional)
  custom_domains = try(local.environment_config.firebase.custom_domains, [])
  primary_domain = length(local.custom_domains) > 0 ? local.custom_domains[0] : ""
}

# Firebase Hosting custom domains (create for each domain in config)
resource "google_firebase_hosting_custom_domain" "domains" {
  provider = google-beta
  for_each = toset(local.custom_domains)
  
  project       = var.project_id
  site_id       = google_firebase_hosting_site.default.site_id
  custom_domain = each.value
  
  # Wait for the site to be ready
  depends_on = [google_project_service.apis, google_firebase_hosting_site.default]
}

# Output DNS configuration instructions for domain managers
output "dns_configuration_instructions" {
  description = "Complete DNS setup instructions for your domain manager"
  value = length(local.custom_domains) > 0 ? {
    message = "🌐 CONFIGURE THESE DNS RECORDS IN YOUR DOMAIN MANAGER:"
    domains = {
      for domain in local.custom_domains : domain => {
        domain = domain
        instructions = {
          message = "Add these DNS records for ${domain}:"
          records = [
            for record in google_firebase_hosting_custom_domain.domains[domain].required_dns_updates : {
              type = record.type
              name = record.type == "A" ? (domain == local.primary_domain ? "@" : "www") : record.domain_name
              value = join(", ", record.records)
              ttl = "Auto or 300 seconds"
              instructions = "Configure ${record.type} Record in your DNS provider"
            }
          ]
        }
      }
    }
    dns_setup_steps = [
      "1. Log into your domain provider's DNS management console",
      "2. Add the DNS records shown above for each domain",
      "3. Wait 15-60 minutes for DNS propagation",
      "4. Firebase will automatically provision SSL certificates",
      "5. Check certificate status with: terraform output ssl_certificate_status"
    ]
  } : {
    message = "No custom domains configured. Add domains to firebase.custom_domains in your secrets file."
    domains = {}
    dns_setup_steps = []
  }
}

# Output the raw DNS records for reference
output "firebase_dns_records_raw" {
  description = "Raw DNS records from Firebase (for debugging)"
  value = length(local.custom_domains) > 0 ? {
    for domain in local.custom_domains : domain => google_firebase_hosting_custom_domain.domains[domain].required_dns_updates
  } : null
}

# Output the certificate status for all domains
output "ssl_certificate_status" {
  description = "SSL certificate provisioning status - check this after DNS setup"
  value = length(local.custom_domains) > 0 ? {
    message = "🔒 SSL CERTIFICATE STATUS:"
    domains = {
      for domain in local.custom_domains : domain => {
        domain = domain
        certificate_type = google_firebase_hosting_custom_domain.domains[domain].certificate.type
        state = google_firebase_hosting_custom_domain.domains[domain].certificate.state
        status_message = google_firebase_hosting_custom_domain.domains[domain].certificate.state == "ACTIVE" ? "✅ SSL Certificate Active - Domain is ready!" : "⏳ SSL Certificate Pending - Configure DNS records above and wait for propagation"
      }
    }
  } : null
}
