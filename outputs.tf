output "access_application_id" {
  description = "Access application ID"
  value       = cloudflare_zero_trust_access_application.gateway.id
}

output "access_application_aud" {
  description = "AUD tag for tunnel JWT enforce / origin validation"
  value       = cloudflare_zero_trust_access_application.gateway.aud
}

output "service_token_client_id" {
  description = "CF-Access-Client-Id"
  value       = cloudflare_zero_trust_access_service_token.desktop.client_id
}

output "service_token_secrets_file" {
  description = "Path to gitignored JSON with client secret + optional gateway bearer"
  value       = local_sensitive_file.service_token.filename
  sensitive   = true
}

output "curl_example" {
  description = "Non-secret shape of an authenticated request (fill secrets from local.generated…)"
  value       = <<-EOT
    curl -fsS "https://${var.gateway_public_hostname}/health" \
      -H "CF-Access-Client-Id: $(jq -r .cloudflare_access.cf_access_client_id ${var.secrets_output_path})" \
      -H "CF-Access-Client-Secret: $(jq -r .cloudflare_access.cf_access_client_secret ${var.secrets_output_path})"
  EOT
}
