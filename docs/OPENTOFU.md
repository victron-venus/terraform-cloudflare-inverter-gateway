# FLOSS development and validation

Official OpenTofu **1.13.1** (MPL-2.0), the Cloudflare 5.24.0/local 2.9.0 providers,
Python, Git and actionlint provide a tested FLOSS source-development route:

```sh
TOFU_BIN=/absolute/path/to/tofu python3 scripts/check_opentofu.py
```

Install the normal Python validation dependencies in a virtual environment first.
The helper verifies the engine version, creates an isolated temporary source copy,
removes the Terraform-only `override_during = plan` keyword from that copy and
formats the adapted HCL. The same four positive/negative plan tests and all their
assertions then run; none are skipped. The original source is unchanged. Explicit
provider source addresses retain Cloudflare's registry origin. OpenTofu rewrites
HashiCorp's local-provider lock entry to its own registry while preserving version
2.9.0; its publisher checksums differ. This happens only in the temporary copy.

The helper clears ambient credentials/options, uses an empty CLI configuration
and temporary HOME, and excludes state, private tfvars and symlinks from its source
copy. The tests mock both providers and never apply, access a backend, or manage a
live resource. Provider downloads still require network access. The October 2026
Darwin ARM64 run passed all 14 Python tests and all 4 mock plans; Linux CI repeats
this route. The strict TLS regression also passed all 8 cases using the actual
Linux ARM64 OpenTofu binary and unchanged Cloudflare provider.

This is a supported source-validation route, not a production-state migration.
The ordinary Terraform 1.16.6 workflow remains supported. A real engine/state
migration requires an independent compatibility and recovery review.
