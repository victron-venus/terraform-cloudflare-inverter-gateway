# Dependency security review — 2026-10-16

The GitHub advisory, Dependabot and secret-scanning APIs contained no open
repository findings. That does not establish the security of downloaded tool
binaries. A separate `govulncheck -mode binary` scan of official executables found:

- Cloudflare provider5.24.0, built with Go1.25.8: 50 vulnerability records with
  symbols present, across the Go standard library and three modules.
- Current upstream provider5.28.0: the same50 records; its runtime is also
  Go1.25.8. Merely updating the provider version does not resolve this finding.
- Terraform1.16.5, built with Go1.26.8: 13 records, including standard-library
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
