# Write Access service-token credentials next to this module (gitignored).
# Never commit local.generated.* or local.secrets.tfvars.

resource "local_sensitive_file" "service_token" {
  filename = "${path.module}/${var.secrets_output_path}"
  file_permission = "0600"

  content = jsonencode({
    cloudflare_access = {
      team_name                 = var.team_name
      application_aud           = cloudflare_zero_trust_access_application.gateway.aud
      application_id            = cloudflare_zero_trust_access_application.gateway.id
      gateway_public_hostname   = var.gateway_public_hostname
      cf_access_client_id       = cloudflare_zero_trust_access_service_token.desktop.client_id
      cf_access_client_secret   = cloudflare_zero_trust_access_service_token.desktop.client_secret
    }
    inverter_gateway = {
      # Optional companion secret for desktop remote profile
      api_bearer_token = var.gateway_api_token
      base_url         = "https://${var.gateway_public_hostname}"
    }
    request_headers = {
      "CF-Access-Client-Id"     = cloudflare_zero_trust_access_service_token.desktop.client_id
      "CF-Access-Client-Secret" = cloudflare_zero_trust_access_service_token.desktop.client_secret
      "Authorization"           = var.gateway_api_token != "" ? "Bearer ${var.gateway_api_token}" : ""
    }
  })
}
