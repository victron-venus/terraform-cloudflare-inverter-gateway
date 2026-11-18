# Documentation

The reusable Cloudflare Zero Trust Access module for the `inverter-gateway`
hostname behind Cloudflare Tunnel, plus the CI policy, validation profiles and
dependency evidence around it.

## CI policy

- [CI and release operations](release-workflow.md) — `.release-policy.json` as source of truth, the required `CI gate` status and the validation-only policy.
- [CI and release policy](CI_WORKFLOW.md) — the events that run the Quality gate and which validation workflows the change classifier selects.
- [CI orchestration](CI-ORCHESTRATION.md) — how the Quality gate and release pipeline divide pull-request, merge-queue, default-branch and nightly events.

## Toolchain and transport

- [FLOSS development and validation](OPENTOFU.md) — the OpenTofu 1.13.1, provider, Python and actionlint versions that make up the tested FLOSS route.
- [Reproducible provider security patch](SECURE_PROVIDER.md) — the optional build that keeps Cloudflare provider 5.24.0 source and updates its compiler and dependency graph.
- [Complete local-execution TLS profile](TLS_PROFILE.md) — the key-length policy applied to local tool transport.
- [Release helper TLS profile](release-tls-profile.md) — the verified `gh` TLS profile used by release helpers.

## Security evidence

- [Dependency security review — 2026-10-16](dependency-security.md) — advisory, Dependabot and secret-scanning results plus the `govulncheck` findings in downloaded tool binaries.
- [OpenSSF Best Practices evidence](openssf-evidence.md) — the source index used when reviewing against the OpenSSF Passing criteria.

## Direction

- [Roadmap through October 2027](roadmap.md) — the stated priorities for compatibility, documented interfaces, failure handling and reproducible validation.
