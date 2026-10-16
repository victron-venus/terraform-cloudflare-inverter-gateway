# Plan-only synthetic provider evaluation. Never authenticate or apply resources.
mock_provider "cloudflare" {
  override_during = plan
}
mock_provider "local" {
  override_during = plan
}

variables {
  account_xyz             = "00000000000000000000000000000000"
  email_xyz               = "owner@example.invalid"
  key_xyz                 = "0000000000000000000000000000000000000"
  gateway_public_hostname = "gateway.example.invalid"
  team_name               = "test-team"
  allow_emails            = ["first@example.invalid", "second@example.invalid"]
  gateway_api_token       = "synthetic-token-not-a-credential"
}

override_resource {
  override_during = plan
  target          = cloudflare_zero_trust_access_service_token.desktop
  values = {
    id            = "synthetic-service-token-id"
    client_id     = "synthetic-client-id"
    client_secret = "synthetic-client-secret"
  }
}

override_resource {
  override_during = plan
  target          = cloudflare_zero_trust_access_policy.allow_email
  values          = { id = "synthetic-email-policy-id" }
}

override_resource {
  override_during = plan
  target          = cloudflare_zero_trust_access_policy.service_auth_desktop
  values          = { id = "synthetic-token-policy-id" }
}

override_resource {
  override_during = plan
  target          = cloudflare_zero_trust_access_application.gateway
  values          = { id = "synthetic-application-id", aud = "synthetic-audience" }
}

run "explicit_access_and_private_output" {
  command = plan
  assert {
    condition     = cloudflare_zero_trust_access_policy.allow_email.decision == "allow" && toset([for rule in cloudflare_zero_trust_access_policy.allow_email.include : rule.email.email]) == toset(var.allow_emails)
    error_message = "Browser access must be limited to the explicit email allowlist."
  }
  assert {
    condition     = cloudflare_zero_trust_access_policy.service_auth_desktop.decision == "non_identity" && tolist(cloudflare_zero_trust_access_policy.service_auth_desktop.include)[0].service_token.token_id == "synthetic-service-token-id"
    error_message = "Service authentication must be tied to the created token."
  }
  assert {
    condition     = length(cloudflare_zero_trust_access_application.gateway.policies) == 2 && cloudflare_zero_trust_access_application.gateway.policies[0].id == "synthetic-email-policy-id" && cloudflare_zero_trust_access_application.gateway.policies[1].id == "synthetic-token-policy-id"
    error_message = "The application must attach exactly the two intended access policies."
  }
  assert {
    condition     = cloudflare_zero_trust_access_application.gateway.domain == var.gateway_public_hostname && cloudflare_zero_trust_access_application.gateway.auto_redirect_to_identity == false
    error_message = "Application routing must retain the configured hostname and explicit authentication flow."
  }
  assert {
    condition     = length(cloudflare_zero_trust_tunnel_cloudflared_config.gateway) == 0
    error_message = "Default plans must not replace existing tunnel ingress."
  }
  assert {
    condition     = local_sensitive_file.service_token.file_permission == "0600" && endswith(local_sensitive_file.service_token.filename, "/local.generated.service-token.json")
    error_message = "Local credential output must have a private file mode and the expected destination."
  }
  assert {
    condition     = jsondecode(nonsensitive(local_sensitive_file.service_token.content)).cloudflare_access.cf_access_client_secret == "synthetic-client-secret" && jsondecode(nonsensitive(local_sensitive_file.service_token.content)).inverter_gateway.base_url == "https://gateway.example.invalid"
    error_message = "Credential output must bind the generated token and HTTPS application URL."
  }
}

run "managed_tunnel_is_authenticated_and_has_catchall" {
  command = plan
  variables {
    manage_tunnel_config = true
    tunnel_id            = "00000000-0000-0000-0000-000000000001"
  }
  assert {
    condition     = length(cloudflare_zero_trust_tunnel_cloudflared_config.gateway) == 1 && length(cloudflare_zero_trust_tunnel_cloudflared_config.gateway[0].config.ingress) == 2
    error_message = "Explicit tunnel management must create the host route and catch-all only."
  }
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared_config.gateway[0].config.ingress[0].origin_request.access.required == true && cloudflare_zero_trust_tunnel_cloudflared_config.gateway[0].config.ingress[0].origin_request.access.aud_tag[0] == "synthetic-audience"
    error_message = "The origin must enforce the intended application audience."
  }
  assert {
    condition     = cloudflare_zero_trust_tunnel_cloudflared_config.gateway[0].config.ingress[1].service == "http_status:404"
    error_message = "Unmatched hostnames must receive a deny-style 404 catch-all."
  }
}

run "reject_empty_allowlist" {
  command = plan
  variables { allow_emails = [] }
  expect_failures = [var.allow_emails]
}

run "reject_wildcard_allowlist" {
  command = plan
  variables { allow_emails = ["*@example.invalid"] }
  expect_failures = [var.allow_emails]
}
