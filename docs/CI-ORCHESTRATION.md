# CI orchestration

Quality gate owns pull request and merge queue validation. The release pipeline
owns default branch and nightly checks for applications; validation-only projects
run those events through Quality gate. Callable validators do not launch duplicate
runs. Superseded PR runs are cancelled, and validation jobs have explicit timeouts.

The required CI configuration contracts check CodeQL pin compatibility, validation
triggers, timeouts, and complete gate dependencies. Dependency Review, where present,
blocks the same gate for pull requests and reports other events as not applicable.
CodeQL action updates are grouped where Dependabot Actions updates are configured.

Auto-merge retains the check-waiting mode because the conditional Gitar review
check does not appear on every PR. It waits for all observed checks, including Gitar,
without making absent conditional checks a permanent merge blocker. BOT_PAT remains
the merger token; approval token policies are unchanged. The gate and external
security checks retain strict branch protection and verified source GitHub Apps.

## Documentation-only changes

The `change_scope` section in `.release-policy.json` opts into the existing
[shared classifier](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/CHANGE_SCOPE.md).
Quality gate compares the complete PR diff, pushed range, or merge-group range
before starting validation. Ordinary Markdown/reStructuredText documentation
skips provider validation, including all 16 unit-test shards, provider builds and
TLS checks. Workflow validation and dependency review also skip on that path.
The required CodeQL analyses, CI configuration contracts and final **CI gate**
still run; SonarCloud remains independently required by repository rules.

Any source, workflow, dependency, test, asset or file-mode change requests full
validation. Missing history, invalid revisions and other uncertainty also request
the full path. The gate rejects failed checks, missing results and skips without
a successful `documentation-only` classification. It never treats skipped
provider tests as new provider qualification evidence.

Scheduled and manually dispatched checks retain full validation selection. The
existing nightly selector may reuse recent, complete same-commit provider
qualification for a fresh vulnerability scan. Callable release/qualification
workflows can pass `force-full: true`. The nightly slot remains `37 2 * * *` UTC.

The generated gate and classifier were adopted from toolkit commit
`04d1a895fac608e5c972e49b127a1a792d7ad725`; the release engine was not upgraded.
Keep this policy when regenerating CI. The lightweight workflow-contract job
tests the actual gate's successful and rejected outcomes on both paths and
classifies real Git fixtures, so documentation routing cannot silently disappear.
