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

## Qualified engine scope

A completed `go list -deps .` audit of exact Terraform 1.16.6 source
[7b8f1669b95119ac6021e05c9d10eae7cf75f60b](https://github.com/hashicorp/terraform/tree/7b8f1669b95119ac6021e05c9d10eae7cf75f60b)
contains 1,778 packages. The legacy `golang.org/x/crypto/openpgp` package affected
by [GO-2026-5932](https://pkg.go.dev/vuln/GO-2026-5932) is absent: provider and
release signature verification use maintained ProtonMail OpenPGP. The binary's
other twelve records were published October 8. The sole critical record,
[GO-2026-6612](https://pkg.go.dev/vuln/GO-2026-6612), requires an HTTP/2 server
processing attacker streams. The qualified local-backend init/validate/plan
profile uses outbound HTTPS and private provider RPC with AutoMTLS; no public
HTTP/2 server is exposed. Do not set `TF_DISABLE_PLUGIN_TLS`, invoke login or use
unreviewed remote backends/custom providers as part of this assessment.

The remaining recent noncritical findings stay tracked; reassess before
December 7, 2026, or immediately for a new critical finding or profile/version
change. This scoped assessment found no applicable critical or 60-day-old
medium/higher engine vulnerability on October 16; it does not assert the official
binary is advisory-free or qualify the old Cloudflare provider. Resolving the
source dependency graph using Go 1.27.2 did not rebuild or upgrade the official
Terraform binary, whose runtime remains Go 1.26.8.

OpenTofu 1.13.1 is a separately tested FLOSS compatibility profile, with
1,808 command dependencies: no legacy OpenPGP or affected sumdb client/tlog;
only independent sumdb/dirhash is imported. Its additional gRPC advisory
[GO-2026-6443](https://pkg.go.dev/vuln/GO-2026-6443) is noncritical and was
published September 15. Reassess that record before November 14, 2026.
The same local-backend/AutoMTLS boundary applies; arbitrary engine features
are outside this evidence.

## Unchanged local file provider

The official local provider 2.9.0 also embeds Go 1.25.8. This module only uses
`local_sensitive_file`, whose source performs owner-authorized file operations
and compatibility checksums; it does not use the provider's command/actions,
HTTP clients or document parsers. It does not call the `os.Root` APIs involved in
the related root-escape advisories. The qualified Linux/Darwin wrapper enforces
umask 0077 and retains AutoMTLS: provider RPC uses an owner-only Unix socket,
not a public network server. See [local provider source](https://github.com/hashicorp/terraform-provider-local/tree/3561e410f9fe1769a419c23adb8f1a9b89929b66)
and [go-plugin listener](https://github.com/hashicorp/go-plugin/blob/v1.7.0/server.go#L578).
Its 50 binary advisory matches are retained as dependency evidence; no relevant
public input, hostile socket peer or affected `os.Root` operation was identified
in this bounded profile. Windows, shared sockets, arbitrary local commands,
untrusted paths and altered resource definitions require a new assessment.
MD5/SHA1 compatibility outputs are not used as authentication/integrity proofs.
