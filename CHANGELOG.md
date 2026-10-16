# Source change history

## 2026-10-16

### Changes

- Validate the Scorecard 5.6 report contract without ignoring runtime errors.
- Exercise allowlist, service-token binding, tunnel JWT/catch-all and sensitive
  output behavior using four isolated mock plans. Reject empty/wildcard allowlists.
- Add a verified strict TLS profile and a FLOSS OpenTofu validation route.
- Document ownership, confidential conduct reporting and the current recovery gap.
- Update the official local provider to 2.9.1 and provide a disclosed Cloudflare
  provider build with Go 1.27.2 and updated security dependencies.
- Add a verified local-state execution wrapper that pins the engine and provider,
  excludes remote backends and preserves private IPC/state permissions.

### Upgrade

Source deliveries use the full immutable Git commit SHA; record it before an
update. Existing empty or wildcard allowlists now fail validation. Review an
explicit list of addresses. This source change does not migrate or apply state.

### Security

Mock plans and TLS fixtures use synthetic data only. Strict TLS is a documented
opt-in execution profile and may reject old endpoint certificates. Protect state
and generated credential files. No new application vulnerability identifier is
assigned. The disclosed provider build updates dependencies affected by
CVE-2026-32283 (TLS KeyUpdate handling), CVE-2026-32280 (certificate-chain
building) and CVE-2026-33814 (HTTP/2 transport). The
[dependency review](docs/dependency-security.md) links the upstream advisories
and distinguishes older official Cloudflare binaries from the disclosed build
and bounded engine/local-provider profiles. Select the new profile only after
all documented qualification steps pass; this source update does not replace
an existing deployment's provider or state automatically. Recent
engine advisories remain tracked; no claim covers arbitrary engine features or
an existing deployment that has not selected the verified profile.

## Previous source baseline — 2026-10-16

The preceding default-branch source provides a Cloudflare Access application,
email and service-token policies, a private local credential output, and optional
managed-tunnel ingress. Its validation-only workflow performs source/schema
checks. It does not distribute binary releases or apply infrastructure in CI.
