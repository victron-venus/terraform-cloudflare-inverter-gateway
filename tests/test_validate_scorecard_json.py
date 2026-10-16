"""Regression tests for the pinned action's full-JSON completeness contract."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "validate_scorecard_json",
    Path(__file__).resolve().parents[1] / "scripts/validate_scorecard_json.py",
)
if SPEC is None or SPEC.loader is None:
    MODULE_LOAD_ERROR = "Cannot load the Scorecard guard test module"
    raise RuntimeError(MODULE_LOAD_ERROR)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)
REPO = "owner/project"
SHA = "a" * 40


def complete() -> dict[str, Any]:
    """Build a complete result, including checks excluded by the SARIF policy."""
    return {
        "repo": {"name": f"github.com/{REPO}", "commit": SHA},
        "scorecard": guard.VERSION.copy(),
        "checks": [
            {"name": name, "score": 10}
            for name in sorted(guard.CHECKS)
        ],
    }


class ScorecardJSONTests(unittest.TestCase):
    """Preserve findings while rejecting incomplete or unrelated scans."""

    def test_complete_clean_and_failing_checks_pass(self) -> None:
        for score in (0, 4, 10):
            result = complete()
            result["checks"][0]["score"] = score
            guard.validate(result, REPO, SHA)

    def test_actual_v56_report_is_preserved(self) -> None:
        fixture = Path(__file__).parent / "fixtures/scorecard-v5.6.0.json"
        result = json.loads(fixture.read_text())
        original = copy.deepcopy(result)
        guard.validate(result, REPO, SHA)
        self.assertEqual(result, original)

    def test_upstream_not_applicable_results_are_preserved(self) -> None:
        for name, reason in guard.NOT_APPLICABLE.items():
            with self.subTest(name=name):
                result = complete()
                check = next(c for c in result["checks"] if c["name"] == name)
                check.update(score=-1, reason=reason)
                guard.validate(result, REPO, SHA)

    def test_runtime_errors_and_other_inconclusive_results_fail(self) -> None:
        for name, reason in guard.NOT_APPLICABLE.items():
            changes = [
                {"reason": "internal error: " + reason},
                {"reason": reason.upper()},
                {"reason": None},
                {"error": "API failed"},
                {"score": -1.0},
            ]
            for change in changes:
                with self.subTest(name=name, change=change):
                    result = complete()
                    check = next(c for c in result["checks"] if c["name"] == name)
                    check.update(score=-1, reason=reason)
                    check.update(change)
                    with self.assertRaises((TypeError, ValueError)):
                        guard.validate(result, REPO, SHA)

    def test_not_applicable_reasons_cannot_be_used_by_other_checks(self) -> None:
        for name in guard.CHECKS:
            for allowed_name, reason in guard.NOT_APPLICABLE.items():
                if name == allowed_name:
                    continue
                with self.subTest(name=name, reason=reason):
                    result = complete()
                    check = next(c for c in result["checks"] if c["name"] == name)
                    check.update(score=-1, reason=reason)
                    with self.assertRaises((TypeError, ValueError)):
                        guard.validate(result, REPO, SHA)

    def test_invalid_or_incomplete_checks_fail(self) -> None:
        for name in guard.CHECKS:
            for score in (-1, -2, 11, True, "10", None):
                with self.subTest(name=name, score=score):
                    result = complete()
                    check = next(c for c in result["checks"] if c["name"] == name)
                    check["score"] = score
                    with self.assertRaises((TypeError, ValueError)):
                        guard.validate(result, REPO, SHA)

    def test_explicit_error_cannot_be_masked_by_valid_score(self) -> None:
        result = complete()
        result["checks"][0]["error"] = "API failed"
        with self.assertRaises(ValueError):
            guard.validate(result, REPO, SHA)

    def test_missing_duplicate_unknown_and_malformed_checks_fail(self) -> None:
        original = complete()
        cases = [
            None,
            [],
            original["checks"][1:],
            original["checks"] * 2,
            [{"name": "unknown", "score": 10}],
            [None],
            [{"name": [], "score": 10}],
        ]
        for checks in cases:
            with self.subTest(checks=checks):
                result = copy.deepcopy(original)
                result["checks"] = checks
                with self.assertRaises((TypeError, ValueError)):
                    guard.validate(result, REPO, SHA)

    def test_repository_commit_and_version_are_bound_to_the_run(self) -> None:
        for field, value in (
            ("repo", {"name": "github.com/other/repo", "commit": SHA}),
            ("repo", {"name": f"github.com/{REPO}", "commit": "b" * 40}),
            ("scorecard", {"version": "v9.0.0", "commit": "b" * 40}),
            ("scorecard", {"version": guard.VERSION["version"], "commit": "b" * 40}),
        ):
            with self.subTest(field=field, value=value):
                result = complete()
                result[field] = value
                with self.assertRaises((TypeError, ValueError)):
                    guard.validate(result, REPO, SHA)

    def test_missing_run_identity_and_invalid_root_fail(self) -> None:
        for result, repo, sha in (
            (complete(), "", SHA),
            (complete(), REPO, ""),
            ([], REPO, SHA),
        ):
            with self.assertRaises((TypeError, ValueError)):
                guard.validate(result, repo, sha)

    def test_failed_guard_removes_stale_sarif(self) -> None:
        for content in (None, "{invalid", "{}", json.dumps({"checks": []})):
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                if content is not None:
                    (root / "results.json").write_text(content)
                (root / "results.sarif").write_text("stale")
                with (
                    patch.object(guard, "ROOT", root),
                    patch.dict(
                        "os.environ", {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": SHA}
                    ),
                    self.assertRaises((OSError, TypeError, ValueError)),
                ):
                    guard.main()
                self.assertFalse((root / "results.sarif").exists())

    def test_successful_guard_preserves_original_sarif(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "results.json").write_text(json.dumps(complete()))
            (root / "results.sarif").write_text("original report")
            with (
                patch.object(guard, "ROOT", root),
                patch.dict(
                    "os.environ", {"GITHUB_REPOSITORY": REPO, "GITHUB_SHA": SHA}
                ),
            ):
                guard.main()
            self.assertEqual((root / "results.sarif").read_text(), "original report")


if __name__ == "__main__":
    unittest.main()
