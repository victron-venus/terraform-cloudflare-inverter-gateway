# Source change history

## 2026-10-16

### Changes

- Validate the Scorecard5.6 report contract without ignoring runtime errors.
- Exercise allowlist, service-token binding, tunnel JWT/catch-all and sensitive
  output behavior using four isolated mock plans. Reject empty/wildcard allowlists.
- Add a verified strict TLS profile and a FLOSS OpenTofu validation route.
- Document ownership, confidential conduct reporting and the current recovery gap.

### Upgrade

Source deliveries use the full immutable Git commit SHA; record it before an
update. Existing empty or wildcard allowlists now fail validation. Review an
explicit list of addresses. This source change does not migrate or apply state.

### Security

Mock plans and TLS fixtures use synthetic data only. Strict TLS is a documented
opt-in execution profile and may reject old endpoint certificates. Protect state
and generated credential files. No known vulnerability identifier is assigned.

## Previous source baseline — 2026-10-16

The preceding default-branch source provides a Cloudflare Access application,
email and service-token policies, a private local credential output, and optional
managed-tunnel ingress. Its validation-only workflow performs source/schema
checks. It does not distribute binary releases or apply infrastructure in CI.
