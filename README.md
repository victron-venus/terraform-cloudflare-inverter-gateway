# terraform-cloudflare-inverter-gateway

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15581/badge)](https://www.bestpractices.dev/projects/15581)

Terraform for Cloudflare **Zero Trust Access** in front of [`inverter-gateway`](https://github.com/victron-venus/inverter-gateway) behind Cloudflare Tunnel.

Manages:

- Self-hosted Access application for the public hostname
- Allow policy (email)
- Access **Service Token** + non-identity policy (for [`inverter-desktop`](https://github.com/victron-venus/inverter-desktop) / automation)
- Writes `client_id` / `client_secret` (and optional gateway bearer) to a **gitignored** `local.generated.service-token.json` via `local_sensitive_file`

Optional (off by default): tunnel ingress with **Enforce Access JWT** (`origin_request.access`).

> This repository provides a reusable gateway module and local secret-file
> generation. Manage live hostnames and existing Access resources through one
> reviewed Terraform state; import existing resources before applying changes.
> Deployment-specific ownership, state and credentials belong outside public
> documentation.

<!-- ci-release-process:start -->
## CI and deployment

See [CI and deployment workflow](docs/release-workflow.md) for required checks and local commands. This repository uses validation-only policy; application release channels do not apply.
<!-- ci-release-process:end -->

## Secrets layout

| File | In git? | Purpose |
|------|---------|---------|
| `local.secrets.tfvars.example` | yes | Fake template for users |
| `local.secrets.tfvars` | **no** | Real account id, API token, emails, hostname |
| `local.generated.service-token.json` | **no** | Written by apply — desktop reads this |

```bash
cp local.secrets.tfvars.example local.secrets.tfvars
# edit local.secrets.tfvars
# use the verified local execution profile linked below
```

For new deployments, use the [verified local execution profile](docs/SECURE_PROVIDER.md#recommended-local-execution-profile), which selects the disclosed provider security build and checks its provenance on every command. The official provider binary retains older runtime vulnerabilities; direct unqualified `terraform` commands do not select the corrected profile. Existing state/provider migrations require a separate review.

Auth matches `rules_lists`: Global API Key via bashrc (auto-picked by Terraform):

```bash
export TF_VAR_account_xyz=...
export TF_VAR_email_xyz=...
export TF_VAR_key_xyz=...
```

Or set `account_xyz` / `email_xyz` / `key_xyz` in `local.secrets.tfvars` (never commit).

## Existing dashboard resources

If you already created the Access app / email policy in the UI (as with your existing public hostname), **import** them instead of recreating — see `import.example.sh`. Then let Terraform create the Service Token (or import that too).

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

The verified local profile rejects active or commented cloud/backend blocks;
remove the example block only in the new private deployment copy. HCP remote
workers do not inherit a local provider build or environment. Migrating an
existing HCP deployment requires an explicit state backup, ownership and access
review, planned migration, and verification. This documentation does not perform
that migration. Do not apply the same resources from independent states.
Never commit credentials, private variables or state files.

## Repo provisioning

GitHub repository is created under [`victron-venus`](https://github.com/victron-venus) and tracked by [`terraform-github-victron`](https://github.com/4alvit/terraform-github-victron).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for reports, development checks and pull requests,
[SECURITY.md](SECURITY.md) for private vulnerability reporting and deployment trust boundaries,
and the [OpenSSF evidence index](docs/openssf-evidence.md) for assessment references and remaining verification.

## Development and security evidence

Run `bash scripts/ci.sh` for syntax/schema validation and isolated mock policy tests.
The [OpenTofu route](docs/OPENTOFU.md) supports FLOSS development, and the
[strict TLS profile](docs/TLS_PROFILE.md) specifies verified engine/provider settings.
See [source changes](CHANGELOG.md), [governance](GOVERNANCE.md),
[conduct](CODE_OF_CONDUCT.md) and the [roadmap](docs/roadmap.md).

The [disclosed provider security patch](docs/SECURE_PROVIDER.md) provides
a pinned source build and qualification path while official provider binaries
retain the runtime findings documented in the dependency review.
