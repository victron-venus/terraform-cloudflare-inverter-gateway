"""Exercise the shared classifier and this repository's required gate policy."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("change_scope", ROOT / "scripts/change_scope.py")
SCOPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCOPE)


class ScopeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.workflow = yaml.load(
            (ROOT / ".github/workflows/quality-gate.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.jobs = self.workflow["jobs"]

    def results(self, docs):
        results = {
            name: {"result": "success"}
            for name in self.jobs if name != "gate"
        }
        results["scope"]["outputs"] = {
            "run": "false" if docs else "true",
            "reason": "documentation-only" if docs else "non-documentation-change",
        }
        if docs:
            for name in ("check-0", "check-2", "check-3"):
                results[name]["result"] = "skipped"
        return results

    def gate_passes(self, results):
        command = self.jobs["gate"]["steps"][-1]["run"]
        prefix, suffix = "python3 - <<'PY'\n", "PY\n"
        self.assertTrue(command.startswith(prefix) and command.endswith(suffix))
        result = subprocess.run(
            [sys.executable, "-c", command[len(prefix):-len(suffix)]],
            env={**os.environ, "RESULTS": json.dumps(results)},
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0

    def test_policy_keeps_required_security_and_existing_schedule(self):
        policy = json.loads((ROOT / ".release-policy.json").read_text())
        self.assertEqual(policy["change_scope"], {
            "documentation_paths": ["GOVERNANCE.md"], "required_paths": [],
            "always_validate_workflows": ["codeql.yml"],
        })
        classifier = next(s for s in self.jobs["scope"]["steps"] if s.get("id") == "scope")
        self.assertEqual(json.loads(classifier["env"]["DOCUMENTATION_PATHS"]), ["GOVERNANCE.md"])
        self.assertEqual(json.loads(classifier["env"]["REQUIRED_PATHS"]), [])
        self.assertEqual(self.workflow["on"]["schedule"], [{"cron": "37 2 * * *"}])
        self.assertEqual(self.workflow["on"]["pull_request"], {})
        self.assertEqual(self.workflow["on"]["merge_group"], {})
        self.assertNotIn("if", self.jobs["check-1"])
        self.assertNotIn("if", self.jobs["workflow-contracts"])
        self.assertEqual(self.jobs["gate"]["if"], "${{ always() }}")
        for name in ("check-0", "check-2", "check-3"):
            self.assertEqual(self.jobs[name]["if"], "${{ needs.scope.outputs.run == 'true' }}")
            self.assertEqual(self.jobs[name]["needs"], ["scope", "workflow-contracts"])
        checkout = next(s for s in self.jobs["scope"]["steps"] if "checkout@" in s.get("uses", ""))
        self.assertEqual(checkout["with"]["fetch-depth"], "0")
        self.assertEqual(checkout["with"]["persist-credentials"], "false")

    def test_gate_accepts_only_complete_full_and_documentation_runs(self):
        for docs in (False, True):
            with self.subTest(docs=docs):
                self.assertTrue(self.gate_passes(self.results(docs)))

    def test_gate_rejects_every_missing_or_failed_job(self):
        for docs in (False, True):
            baseline = self.results(docs)
            for name in baseline:
                with self.subTest(docs=docs, job=name):
                    missing = copy.deepcopy(baseline)
                    del missing[name]
                    self.assertFalse(self.gate_passes(missing))
                    for status in ("failure", "cancelled"):
                        failed = copy.deepcopy(baseline)
                        failed[name]["result"] = status
                        self.assertFalse(self.gate_passes(failed))

    def test_gate_rejects_security_skips_and_unproven_documentation(self):
        for name in ("scope", "check-1", "workflow-contracts"):
            bad = self.results(True)
            bad[name]["result"] = "skipped"
            self.assertFalse(self.gate_passes(bad))
        for outputs in ({}, {"run": "false"}, {"run": "false", "reason": "git-error"}):
            bad = self.results(True)
            bad["scope"]["outputs"] = outputs
            self.assertFalse(self.gate_passes(bad))
        bad = self.results(False)
        bad["check-0"]["result"] = "skipped"
        self.assertFalse(self.gate_passes(bad))

    def test_real_git_docs_range_and_cumulative_code_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null",
                     "-C", directory, *args], stderr=subprocess.PIPE, text=True, timeout=10,
                ).strip()

            def commit():
                git("add", "--all")
                git("commit", "-m", "Scope fixture")
                return git("rev-parse", "HEAD")

            git("init", "--initial-branch=main")
            git("config", "user.name", "Scope fixture")
            git("config", "user.email", "scope@example.invalid")
            (root / "docs").mkdir()
            (root / "docs/CI-ORCHESTRATION.md").write_text("Original documentation\n")
            (root / "main.tf").write_text("# Terraform input\n")
            base = commit()
            (root / "docs/CI-ORCHESTRATION.md").write_text("Updated documentation\n")
            docs_head = commit()
            events = {
                "pull_request": {"pull_request": {"base": {"sha": base}, "head": {"sha": docs_head}}},
                "push": {"before": base, "after": docs_head},
                "merge_group": {"merge_group": {"base_sha": base, "head_sha": docs_head}},
            }
            for event, payload in events.items():
                self.assertEqual(SCOPE.classify(root, event, payload), {
                    "run": False, "reason": "documentation-only",
                })
                self.assertTrue(SCOPE.classify(root, event, payload, force=True)["run"])
            for event in ("schedule", "workflow_dispatch", "workflow_call"):
                self.assertTrue(SCOPE.classify(root, event, {})["run"])
            (root / "main.tf").write_text("# Changed Terraform input\n")
            commit()
            (root / "docs/CI-ORCHESTRATION.md").write_text("Another documentation update\n")
            head = commit()
            payload = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
            self.assertTrue(SCOPE.classify(root, "pull_request", payload)["run"])
            payload["pull_request"]["base"]["sha"] = "f" * 40
            self.assertTrue(SCOPE.classify(root, "pull_request", payload)["run"])

            (root / "GOVERNANCE.md").write_text("Original governance documentation\n")
            governance_base = commit()
            (root / "GOVERNANCE.md").write_text("Updated governance documentation\n")
            governance_head = commit()
            allowed = ("GOVERNANCE.md",)
            governance_events = {
                "pull_request": {"pull_request": {
                    "base": {"sha": governance_base}, "head": {"sha": governance_head},
                }},
                "push": {"before": governance_base, "after": governance_head},
                "merge_group": {"merge_group": {
                    "base_sha": governance_base, "head_sha": governance_head,
                }},
            }
            for event, payload in governance_events.items():
                with self.subTest(governance_event=event):
                    self.assertTrue(SCOPE.classify(root, event, payload)["run"])
                    self.assertEqual(SCOPE.classify(root, event, payload, allowed), {
                        "run": False, "reason": "documentation-only",
                    })
                    self.assertTrue(SCOPE.classify(root, event, payload, allowed, force=True)["run"])
                    self.assertTrue(SCOPE.classify(
                        root, event, payload, allowed, required_paths=allowed,
                    )["run"])
            (root / "main.tf").write_text("# Code change after governance update\n")
            mixed_head = commit()
            mixed = {"pull_request": {
                "base": {"sha": governance_base}, "head": {"sha": mixed_head},
            }}
            self.assertTrue(SCOPE.classify(root, "pull_request", mixed, allowed)["run"])


if __name__ == "__main__":
    unittest.main()
