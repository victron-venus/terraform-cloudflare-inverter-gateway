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
`5.24.0-openssf.1`, and the original Apache-2.0 license is retained with the output.

## Build and qualify

Install an official Go 1.27.2 archive after checking its publisher SHA-256.
The Python source downloader requires OpenSSL 3 and applies security level 3
(with any stronger existing policy preserved), hostname/trust verification and
TLS 1.2 or newer. This rejects RSA keys below 3072 bits throughout the chain;
GitHub's ECDSA chain is supported. Only HTTPS redirects between github.com and
codeload.github.com are accepted. The verified Go subprocesses use
`GODEBUG=fips140=on`, including module and scanner downloads. Custom trust stores
or proxies need separate qualification. Pass
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
Each build stage has a one-hour timeout. An interrupted or timed-out stage stops
its entire compiler process group and cannot produce completed provenance.

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

## Recommended local execution profile

For a new independent deployment, export the reviewed repository into a new
private workspace. Remove the commented `cloud {}` example from that copy and
remove its copied `.terraform.lock.hcl` so the disclosed derivative receives its
own lock digest. The module's explicit provider origins and version constraint
support OpenTofu 1.13.1 directly. Configure only resources assigned to this new
state; do not target resources already managed by another deployment.

Run the wrapper from the reviewed original checkout for every command:

```sh
python3 scripts/run_secure_profile.py --tofu /VERIFIED/tofu \
  --provider-dir /PRIVATE/cloudflare-provider --platform linux_arm64 \
  --local-provider-archive /VERIFIED/terraform-provider-local_2.9.1_linux_arm64.zip \
  --directory /NEW/PRIVATE/WORKSPACE init
python3 scripts/run_secure_profile.py --tofu /VERIFIED/tofu \
  --provider-dir /PRIVATE/cloudflare-provider --platform linux_arm64 \
  --local-provider-archive /VERIFIED/terraform-provider-local_2.9.1_linux_arm64.zip \
  --directory /NEW/PRIVATE/WORKSPACE plan -var-file=local.secrets.tfvars -out=reviewed.tfplan
# Only after reviewing the exact plan and approving its intended changes:
python3 scripts/run_secure_profile.py --tofu /VERIFIED/tofu \
  --provider-dir /PRIVATE/cloudflare-provider --platform linux_arm64 \
  --local-provider-archive /VERIFIED/terraform-provider-local_2.9.1_linux_arm64.zip \
  --directory /NEW/PRIVATE/WORKSPACE apply reviewed.tfplan
```

The wrapper checks the exact official engine hash/version, derivative manifest
and binary hash, and locked official local-provider ZIP on each invocation. It
uses a filesystem-only mirror with no fallback to the old Cloudflare binary,
forces FIPS TLS, retains only explicit variable/authentication inputs, and
rejects cloud/remote-backend declarations or cached remote configuration. The
provider IPC retains AutoMTLS; child processes use umask 0077 so Unix sockets
and newly created state remain private even under a permissive caller umask. Only recorded engine platforms are accepted.

This is an explicit local deployment option. It does not upgrade existing state,
change the original repository lock, or replace providers in HCP remote workers.
Existing deployments need a separately reviewed state/provider migration and
acceptance plan. Do not remove state or `.terraform` directories as an automatic
migration step. Live apply has not been performed by this qualification.

## Validate this repository with the derivative

After a completed build, verify the derivative against this repository's actual
schema and all four mocked plan tests using verified OpenTofu 1.13.1:

```sh
python3 scripts/check_secure_provider.py \
  --engine /absolute/path/to/tofu \
  --provider-dir /absolute/path/to/new-provider-build \
  --local-provider-archive /absolute/path/to/terraform-provider-local_2.9.1_linux_amd64.zip \
  --platform linux_amd64
```

The helper verifies derivative provenance and binary digest, checks the official
local-provider archive against the existing repository lock, then builds a
filesystem-only mirror in a disposable directory. Only that copy's provider
locks change. OpenTofu's unsupported `override_during` syntax is removed while
preserving all policy assertions. It runs format/init/validate/test with the
strict TLS environment, without credentials, backend initialization, live API
calls or apply. The original files and state are untouched.

These build and validation helpers are local operator tools. Their explicit
`--go`, `--engine`, `--provider-dir` and `--output` filesystem arguments are under
the caller's authority; there is no HTTP endpoint, chatbot/LLM tool integration
or service accepting untrusted path requests. Do not expose them through such an
interface without a separate authorization and path-confinement design.
