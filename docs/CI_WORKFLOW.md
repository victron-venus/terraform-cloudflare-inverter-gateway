# CI and release policy

This repository has a validation-only policy. The `Quality gate` workflow runs
on pull requests, merge queue entries, the default branch, and a staggered
nightly UTC schedule. Every configured validation workflow must finish
successfully; a skipped or failed workflow does not pass `CI gate`.

Install actionlint 1.7.12 (and Node.js when JavaScript sources are present).
Run the same local checks:

```sh
python3 -m pip install PyYAML==6.0.3
bash scripts/ci.sh
```

Request or inspect CI from a local checkout:

```sh
gh workflow run quality-gate.yml
gh run list --workflow quality-gate.yml
```

No beta, RC or stable application release is synthesized from configuration or
reference source. Disabled legacy publisher entry points only explain this
migration. Their exact previous contents remain in `docs/legacy-workflows/`.
Production deployment, where provided, requires manual dispatch from the default
branch and the `production` environment; validation never deploys resources.

Install Terraform 1.16.6. Checks copy the current tracked/non-ignored source into a temporary directory, materialize redacted compose fixtures where applicable, and run `terraform fmt -check`, `init -backend=false`, `validate`, and `test`. Provider installation requires registry network access. Local state and `.tfvars` are not copied. Plan-only tests use mocked Cloudflare/local providers with synthetic values; no apply or live-resource operation runs.

## Coverage limits

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- Terraform format/schema validation and plan-only mock-provider policy tests use disposable source copies; no apply, remote-state or live-resource checks.

Before local checks, install the pinned synthetic TLS test dependencies in a
virtual environment:

```sh
python3 -m pip install --require-hashes --only-binary=:all: -r requirements-security-tests.txt
```

The source-download regression uses only synthetic certificate chains and
MemoryBIO; it verifies trusted strong TLS1.2/1.3 handshakes, weak keys at each
chain position, hostname/trust failures and HTTPS redirect restrictions.
