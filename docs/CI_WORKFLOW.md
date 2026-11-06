# CI and release policy

This repository has a validation-only policy. The `Quality gate` workflow runs
on pull requests, merge queue entries, the default branch, and a staggered
nightly UTC schedule. The change classifier selects the required validation
workflows. Missing, failed, cancelled or unexpectedly skipped checks fail
`CI gate`; only a proven documentation-only change may skip build checks.

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

## Documentation-only changes

The explicit `change_scope` policy in `.release-policy.json` compares the complete
Git change set. Ordinary documentation, including `GOVERNANCE.md`, can use the
fast path on PRs, merge-queue entries and default-branch pushes. It skips the
16 provider-test shards and their other build validators while retaining the
change classifier, CI configuration contracts, CodeQL and the required `CI gate`.

Code, tests, workflow files, dependencies, unknown paths and an incomplete or
unproven change set keep full validation. Scheduled and manually dispatched
checks also remain full. This repository is validation-only: no Terraform apply,
version allocation or application release is performed by this optimization.

Follow the [shared CI Toolkit regeneration guide](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/CHANGE_SCOPE.md#regenerate-documentation-scope-safely)
from this repository's root. It defines the supported pinned generator, required
clean-checkout checks, and scope-only update and verification commands.

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
