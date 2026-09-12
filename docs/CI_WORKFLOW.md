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

Install Terraform 1.15.7. Checks copy the current tracked/non-ignored source into a temporary directory, materialize redacted compose fixtures where applicable, and run `terraform fmt -check`, `init -backend=false`, and `validate`. Provider installation requires registry network access. Local state and `.tfvars` are not copied; no plan or apply runs.

## Coverage limits

- Validation-only policy: no synthetic beta/RC artifacts or tag-triggered stable releases.
- Terraform fmt/validate use disposable source copies with backend disabled; no plan, apply, remote-state or live-provider checks. Portainer uses redacted compose fixtures. Inventory and archived monolith are excluded.
