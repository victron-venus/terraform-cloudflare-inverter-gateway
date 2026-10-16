# Reproducible provider security patch

The official Cloudflare 5.24.0 and 5.28.0 executables were built with Go 1.25.8.
The [dependency review](dependency-security.md) records older client-side
vulnerabilities in that runtime. The optional build below preserves the 5.24.0
provider source and updates its compiler and Go dependency graph. It is a
**project-maintained derivative**, not an official Cloudflare release.

`security/provider/manifest.json` pins the original upstream commit and archive
SHA-256, the exact replacement `go.mod`/`go.sum` hashes, Go 1.27.2, and the scanner
version. The direct updates are x/net 0.60.0, x/text 0.42.0, x/crypto 0.57.0 and
gRPC 1.83.2; their required transitive updates are visible in the module files.
No provider resource implementation is patched. The internal version string is
`5.24.0-openssf.1`, and the original MPL-2.0 license is retained with the output.

## Build and qualify

Install an official Go 1.27.2 archive after checking its publisher SHA-256. Pass
the actual executable, not an assumption about `GOTOOLCHAIN` selection:

```sh
python3 scripts/build_secure_provider.py \
  --go /absolute/path/to/go/bin/go \
  --platform linux_amd64 \
  --output /absolute/path/to/new-provider-build
```

The new directory must not already exist. The command downloads pinned public
source and verified Go modules, runs `govulncheck`, runs upstream non-acceptance
unit tests, then builds and inspects the executable. It rejects archive links and
path traversal, removes inherited cloud credentials and compiler settings, and
records logs, dependency files, the upstream license and `provenance.json`.
Acceptance tests requiring a real Cloudflare account are excluded. No Terraform
command, provider installation, infrastructure change, or state access occurs.

The source scan is a call-graph analysis, not a claim that every behavior is
tested. A nonzero scanner result or unit-test failure prevents a completed
provenance record. Scanner results may change when the public advisory database
changes even with identical source. The build does not promise bit-for-bit
reproducibility across different host toolchains; its inputs and output checksum
are recorded so that the result can be independently inspected.

Before selecting the derivative, run all eight real transport calibrations with
the intended qualified engine on Linux:

```sh
TLS_TEST_TERRAFORM=/absolute/path/to/terraform-or-tofu \
TLS_TEST_PROVIDER_DIR=/absolute/path/to/new-provider-build \
TLS_TEST_PLATFORM=linux_amd64 python3 scripts/test_tls_profile.py
```

Use the prerequisites and [strict TLS settings](TLS_PROFILE.md). Both the module
downloader and the actual provider must accept RSA-2048, accept RSA-2047 in the
ordinary calibration, and reject RSA-2047 in strict mode before HTTP or
Authorization reaches the fixture. This test uses synthetic credentials and
never applies infrastructure. Engine and provider advisories must still be
reviewed independently; a key-length test cannot establish their absence.

## Explicit local selection

The build intentionally does not change `.terraform.lock.hcl`, `.terraformrc`,
operator state or the module's default registry provider. After reviewing a
successful build's provenance and transport results, a local operator can create
a separate, private CLI configuration:

```hcl
provider_installation {
  dev_overrides {
    "registry.terraform.io/cloudflare/cloudflare" = "/absolute/path/to/new-provider-build"
  }
  direct {}
}
```

Select it explicitly with `TF_CLI_CONFIG_FILE=/absolute/path/to/that-config` and
`GODEBUG=fips140=on` for the intended process. Development overrides deliberately
bypass the registry package checksums during provider execution: review the
recorded source and binary SHA-256 instead. Initialization may still download
the official registry package; the explicit override selects the disclosed local
executable for subsequent provider operations. Terraform warns about this
override, as expected. Do not remove that warning or portray the binary as a
publisher-signed registry artifact. Never use an unrelated shared override file.

Normal review and deployment acceptance remain required before any real apply.
Requalify compiler/dependency updates, and prefer an equivalent fixed official
provider once it is available and has passed the same checks.
