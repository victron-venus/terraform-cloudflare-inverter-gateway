# Dependency security review — 2026-10-16

The GitHub advisory, Dependabot and secret-scanning APIs contained no open
repository findings. That does not establish the security of downloaded tool
binaries. A separate `govulncheck -mode binary` scan of official executables found:

- Cloudflare provider 5.24.0, built with Go 1.25.8: 50 vulnerability records with
  symbols present, across the Go standard library and three modules.
- Current upstream provider 5.28.0: the same 50 records; its runtime is also
  Go 1.25.8. Merely updating the provider version does not resolve this finding.
- Terraform 1.16.5/1.16.6, built with Go 1.26.8: 13 records, including standard-library
  issues and the legacy OpenPGP module advisory.

A binary scan identifies included symbols, not a source call graph proving every
exploit is reachable through this module. Some reports describe server-only or
unrelated functionality. However, TLS/X.509, HTTP client and provider dependency
findings cannot all be dismissed just because the module configures Cloudflare.
For example [GO-2026-4870](https://pkg.go.dev/vuln/GO-2026-4870) concerns TLS
KeyUpdate handling, [GO-2026-4947](https://pkg.go.dev/vuln/GO-2026-4947) concerns
certificate-chain building and [GO-2026-4918](https://pkg.go.dev/vuln/GO-2026-4918)
concerns the HTTP/2 transport. The local key-length calibration does not test or
fix these defects.

The three client findings above were published on 2026-04-07, 2026-04-07
and 2026-05-07 respectively, more than 60 days before this review. They are
concrete reasons to replace the old provider runtime. In contrast, server-only
findings and optional protocol paths need their own applicability analysis;
the total binary count is not a count of exploitable module behaviors.

A disclosed [source-build profile](SECURE_PROVIDER.md) replaces the provider's
compiler and dependencies without silently changing operator state or locks.
Its qualification is separate from the official-binary assessment, and the
Terraform/OpenTofu engine still requires its own advisory review.

The project therefore does not claim completed vulnerability-remediation
criteria or a Passing badge from this change. It preserves the known provider
lock rather than silently substituting a locally modified binary. Review a
patched official build, or a transparently maintained/reproducible alternative,
then repeat dependency scanning, mock-plan compatibility and TLS calibration.
A source-level applicability review may narrow specific reports but must record
why the vulnerable behavior is unreachable; an empty GitHub alerts page is not
that evidence.

Until qualification is complete, keep the execution environment trusted, use
verified HTTPS endpoints and private credentials/state, and do not treat the
[strict TLS profile](TLS_PROFILE.md) as a complete vulnerability assessment.
CI still enforces the source checks, policy tests, static configuration analysis
and real transport calibration introduced by this change.
