# Complete local-execution TLS profile

The [dependency security review](dependency-security.md) records unresolved
official-tool vulnerability findings. Successful key-length calibration does not
remediate them or establish Passing readiness.

The maintained module delegates network operations to Terraform/OpenTofu and the
Cloudflare provider; it does not implement cryptographic primitives. The verified
profile uses official Terraform **1.16.5** (Go **1.26.8**) or OpenTofu **1.13.1**
(Go **1.27.1**) with the locked Cloudflare provider **5.24.0** (Go **1.25.8**).
Verify authenticated publisher checksums and inspect each actual executable with
`go version -m /absolute/path/to/binary`. Do not assume a similarly named custom
or older binary enforces the same policy.

Prefix every process in this profile with `GODEBUG=fips140=on`, including init
and separately reviewed infrastructure operations. Provider subprocesses inherit
it. Keep normal HTTPS endpoints, certificate and hostname verification; do not
set `CLOUDFLARE_BASE_URL` to plaintext or bypass verification. Preserve the locked
provider versions and repeat qualification after an upgrade. Custom proxies and
trust anchors require equivalent verification. The Go TLS policy filters the
complete verified certificate chain to RSA keys of at least 2048 significant
bits and supported modern elliptic keys, TLS1.2 or newer, and ephemeral key
exchange. It can reject peers accepted by ordinary defaults. This runtime mode
is not a claim that the project has FIPS certification.

Use local execution; the checked-in module has no active remote backend. If an
operator adds HCP remote state, use Local execution mode for this profile. Remote
runners do not inherit a workstation's environment and require their own verified
binaries and settings. No qualification operation reads operator state or applies
this module.

The Cloudflare provider's Go standard-library cryptography and the local provider
are FLOSS. Terraform's own current BSL license is not described as FLOSS; the
[OpenTofu profile](OPENTOFU.md) supplies a tested MPL-2.0 development route.
Cloudflare issues service credentials; this module writes them to a sensitive
0600 file and also retains them in Terraform state. Protect the state/backend and
parent directory. The optional gateway bearer is an operator credential: generate
at least 32 independent OS-random bytes. There is no human-password verifier
store. The global Cloudflare API key remains broad authority; a module input does
not make it a narrowly scoped credential.

The generated client base URL is HTTPS. In managed-tunnel mode Access JWT is
required with the application's audience, followed by a catch-all 404 rule. The
Cloudflare tunnel and the local HTTP origin are separate deployed services; use a
loopback origin or an appropriately secured private network. The module cannot
establish that a remote host actually enforces this policy without a separate
deployment check.

## Real, isolated transport regression

`scripts/test_tls_profile.py` starts a loopback HTTPS fixture and runs the real
module downloader and Cloudflare provider with synthetic credentials, disposable
configuration and a filesystem provider mirror. It never applies or contacts a
production API. All eight cases passed on Linux ARM64 for each engine:

- RSA-2048 succeeds with ordinary and strict settings.
- RSA-2047 succeeds in the ordinary calibration, proving the fixture is usable.
- The strict downloader and provider reject RSA-2047 before any HTTP request or
  synthetic Authorization header reaches the fixture.

Run with `cryptography==50.0.2` installed and explicit paths:

```sh
TLS_TEST_TERRAFORM=/absolute/path/to/terraform-or-tofu \
TLS_TEST_PROVIDER_DIR=/absolute/path/to/extracted-cloudflare-provider \
TLS_TEST_PLATFORM=linux_amd64 python3 scripts/test_tls_profile.py
```

The CI job repeats these checks on Linux AMD64. The optional GitHub helper has a
separate [verified GitHub CLI TLS profile](release-tls-profile.md).

Primary sources: [Go FIPS runtime mode](https://go.dev/doc/security/fips140),
[Go1.25.8 TLS filters](https://github.com/golang/go/blob/go1.25.8/src/crypto/tls/defaults_fips140.go),
[Cloudflare5.24 provider](https://github.com/cloudflare/terraform-provider-cloudflare/tree/v5.24.0).
