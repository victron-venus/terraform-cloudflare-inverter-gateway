# --- Cloudflare auth (matches rules_lists; typically from TF_VAR_* in bashrc) ---

variable "account_xyz" {
  description = "Cloudflare Account ID."
  type        = string
}

variable "email_xyz" {
  description = "Cloudflare Email"
  type        = string
}

variable "key_xyz" {
  description = "Cloudflare Key (Global API Key)"
  type        = string
  sensitive   = true
}

# --- Access application ---

variable "gateway_public_hostname" {
  description = "Public hostname for the Victron / inverter-gateway Access app"
  type        = string
}

variable "access_app_name" {
  description = "Access application display name"
  type        = string
  default     = "victron"
}

variable "access_session_duration" {
  description = "Access session duration (e.g. 24h)"
  type        = string
  default     = "24h"
}

variable "team_name" {
  description = "Zero Trust team name (subdomain of *.cloudflareaccess.com), e.g. alvit"
  type        = string
}

variable "allow_emails" {
  description = "Emails allowed by the browser Allow policy"
  type        = list(string)
}

variable "allow_policy_name" {
  description = "Name of the reusable Allow policy (match dashboard if importing)"
  type        = string
  default     = "victron"
}

variable "service_token_name" {
  description = "Name for the Access service token (desktop / automation)"
  type        = string
  default     = "inverter-desktop"
}

variable "service_token_duration" {
  description = "Service token lifetime. Use forever for non-expiring."
  type        = string
  default     = "forever"
}

variable "secrets_output_path" {
  description = "Gitignored path where client_id/client_secret JSON is written"
  type        = string
  default     = "local.generated.service-token.json"
}

variable "manage_tunnel_config" {
  description = "If true, manage tunnel ingress JWT enforce for the gateway hostname. Requires tunnel_id — review plan carefully (can replace other ingresses)."
  type        = bool
  default     = false
}

variable "tunnel_id" {
  description = "Cloudflare Tunnel ID (required when manage_tunnel_config=true)"
  type        = string
  default     = ""
}

variable "tunnel_origin_service" {
  description = "Origin URL cloudflared proxies to (Synology loopback)"
  type        = string
  default     = "http://127.0.0.1:9150"
}

variable "gateway_api_token" {
  description = "Optional: inverter-gateway bearer token to store beside Access secrets for desktop"
  type        = string
  sensitive   = true
  default     = ""
}
