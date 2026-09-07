# terraform-cloudflare-inverter-gateway

Terraform for Cloudflare **Zero Trust Access** in front of [`inverter-gateway`](https://github.com/victron-venus/inverter-gateway) (public hostname `victron.2560801.xyz` behind Cloudflare Tunnel).

Manages:

- Self-hosted Access application for the public hostname
- Allow policy (email)
- Access **Service Token** + non-identity policy (for [`inverter-desktop`](https://github.com/victron-venus/inverter-desktop) / automation)
- Writes `client_id` / `client_secret` (and optional gateway bearer) to a **gitignored** `local.generated.service-token.json` via `local_sensitive_file`

Optional (off by default): tunnel ingress with **Enforce Access JWT** (`origin_request.access`).

> Relocated from [`open-ott-play/foss-cloudflare-infrastructure`](https://github.com/open-ott-play/foss-cloudflare-infrastructure).

## Secrets layout

| File | In git? | Purpose |
|------|---------|---------|
| `local.secrets.tfvars.example` | yes | Fake template for users |
| `local.secrets.tfvars` | **no** | Real account id, API token, emails, hostname |
| `local.generated.service-token.json` | **no** | Written by apply — desktop reads this |

```bash
cp local.secrets.tfvars.example local.secrets.tfvars
# edit local.secrets.tfvars
terraform init
terraform plan  -var-file=local.secrets.tfvars
terraform apply -var-file=local.secrets.tfvars
```

Auth matches `rules_lists`: Global API Key via bashrc (auto-picked by Terraform):

```bash
export TF_VAR_account_xyz=...
export TF_VAR_email_xyz=...
export TF_VAR_key_xyz=...
```

Or set `account_xyz` / `email_xyz` / `key_xyz` in `local.secrets.tfvars` (never commit).

## Existing dashboard resources

If you already created the Access app / email policy in the UI (as with `victron.2560801.xyz`), **import** them instead of recreating — see `import.example.sh`. Then let Terraform create the Service Token (or import that too).

## Tunnel JWT enforce

Dashboard path: Tunnel → Public hostname → **Enforce Access JWT** → select this app.

In Terraform the same thing is `cloudflare_zero_trust_tunnel_cloudflared_config` with:

```hcl
origin_request = {
  access = {
    required  = true
    team_name = var.team_name
    aud_tag   = [cloudflare_zero_trust_access_application.gateway.aud]
  }
}
```

**Warning:** enabling `manage_tunnel_config` replaces the tunnel’s ingress list for that resource. Include every hostname (hass, etc.) in `tunnel.tf` before apply, or keep JWT enforce in the dashboard only.

## Desktop headers

```http
CF-Access-Client-Id: <client_id>
CF-Access-Client-Secret: <client_secret>
Authorization: Bearer <GATEWAY_API_TOKEN>
```

## Running locally / Terraform Cloud

**Currently local by default.** The optional `cloud {}` block in `versions.tf` is commented out, so `terraform init` uses local state.

If you later enable HCP Terraform by uncommenting that block (org/workspace of your choosing; placeholder name `terraform-cloudflare-inverter-gateway`), detach again for local runs as follows:

1. Comment out the entire `cloud { ... }` block in `versions.tf` again.
2. `rm -rf .terraform`
3. `terraform init` (local state)
4. Provide variables locally (`local.secrets.tfvars` / `TF_VAR_*`) — TFC workspace variables are **not** used when detached.

Optional: while still attached, `terraform state pull > terraform.tfstate` before detaching, then confirm with `terraform state list`. Keep state files **gitignored**.

Do not apply from both TFC and local against the same resources without coordinating state. Never commit credentials, secrets tfvars, or state files.

## Repo provisioning

GitHub repository is created under [`victron-venus`](https://github.com/victron-venus) and tracked by [`terraform-github-victron`](https://github.com/victron-venus/terraform-github-victron).
