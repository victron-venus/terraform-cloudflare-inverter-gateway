# Optional: enforce Access JWT at cloudflared for the gateway hostname.
# Disabled by default — enabling manages tunnel config and must include a catch-all
# rule; merge carefully with existing hass/other ingresses before apply.

locals {
  manage_tunnel = var.manage_tunnel_config && var.tunnel_id != ""
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "gateway" {
  count = local.manage_tunnel ? 1 : 0

  account_id = var.account_xyz
  tunnel_id  = var.tunnel_id

  config = {
    ingress = [
      {
        hostname = var.gateway_public_hostname
        path     = null
        service  = var.tunnel_origin_service
        origin_request = {
          access = {
            required  = true
            team_name = var.team_name
            aud_tag   = [cloudflare_zero_trust_access_application.gateway.aud]
          }
        }
      },
      # REQUIRED catch-all — if you enable manage_tunnel_config, expand this list
      # to include every other public hostname (e.g. hass) already on the tunnel.
      {
        service = "http_status:404"
      }
    ]
  }
}
