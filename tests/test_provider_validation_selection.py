"""Recent complete receipts may save scheduled compilation, never qualification."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from test_secure_provider import MODULE as BUILD
from provider_test_shards import partition, reconcile, write_receipt
import select_provider_validation as SELECT

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
SHA = "a" * 40
REPO = "fixture/provider"


def run_fixture():
    return {"id": 123, "status": "completed", "conclusion": "success",
            "event": "push", "head_sha": SHA, "head_branch": "main",
            "repository": {"id": 7, "full_name": REPO},
            "head_repository": {"id": 7, "full_name": REPO},
            "path": SELECT.WORKFLOW, "created_at": "2026-11-01T00:00:00Z"}


def jobs_fixture():
    names = [f"check-0 / Provider unit tests / shard {i}" for i in range(16)]
    names += ["check-0 / Repository validation", "CI gate"]
    return [{"name": name, "status": "completed", "conclusion": "success"} for name in names]


def archive_fixture(entries):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for name, data in entries:
            archive.writestr(name, data)
    body = content.getvalue()
    metadata = {"id": 456, "expired": False, "size_in_bytes": len(body),
                "digest": "sha256:" + hashlib.sha256(body).hexdigest(),
                "workflow_run": {"id": 123, "head_sha": SHA, "head_branch": "main",
                                 "repository_id": 7, "head_repository_id": 7}}
    return metadata, body


class SelectionTests(unittest.TestCase):
    def test_trusted_run_requires_exact_source_repository_event_age_and_workflow(self):
        self.assertTrue(SELECT.trusted_run(run_fixture(), REPO, SHA, NOW))
        mutations = [("head_sha", "b" * 40), ("head_branch", "feature"),
                     ("event", "pull_request"), ("event", "schedule"),
                     ("conclusion", "failure"), ("status", "in_progress"),
                     ("path", ".github/workflows/other.yml"),
                     ("repository", {"full_name": "outside/fork"}),
                     ("head_repository", {"full_name": "outside/fork"}),
                     ("created_at", (NOW - timedelta(days=7, seconds=1)).isoformat()),
                     ("created_at", (NOW + timedelta(seconds=1)).isoformat())]
        for key, value in mutations:
            run = run_fixture()
            run[key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(SELECT.trusted_run(run, REPO, SHA, NOW))

    def test_complete_jobs_rejects_missing_duplicate_skipped_cancelled_and_incomplete(self):
        self.assertTrue(SELECT.complete_jobs(jobs_fixture()))
        for change in ("missing", "duplicate", "skipped", "cancelled", "failure", "in_progress"):
            jobs = jobs_fixture()
            if change == "missing":
                jobs.pop()
            elif change == "duplicate":
                jobs.append(deepcopy(jobs[0]))
            elif change == "in_progress":
                jobs[0]["status"] = change
            else:
                jobs[0]["conclusion"] = change
            with self.subTest(change=change):
                self.assertFalse(SELECT.complete_jobs(jobs))

    def test_non_schedule_always_requires_full_without_network(self):
        with patch.object(SELECT, "github") as api:
            for event in ("push", "pull_request", "workflow_dispatch", "merge_group"):
                self.assertEqual(SELECT.select(REPO, SHA, event, NOW)["mode"], "full")
            api.assert_not_called()

    def test_valid_schedule_reuses_but_missing_or_api_failure_runs_full(self):
        def pages(endpoint, field):
            if field == "workflow_runs":
                return [run_fixture()] if "event=push" in endpoint else []
            return jobs_fixture() if field == "jobs" else ["fixture"]
        with patch.object(SELECT, "pages", side_effect=pages), patch.object(
            SELECT, "verify_receipts", return_value={"inventory_sha256": "c" * 64}
        ):
            result = SELECT.select(REPO, SHA, "schedule", NOW)
            self.assertEqual(result["mode"], "scan")
            self.assertEqual(result["qualified_run_id"], 123)
            self.assertEqual(result["max_age_days"], 7)
        for error in (OSError(), ValueError(), KeyError(), subprocess.TimeoutExpired("gh", 60)):
            with patch.object(SELECT, "pages", side_effect=error):
                self.assertEqual(SELECT.select(REPO, SHA, "schedule", NOW)["mode"], "full")
        with patch.object(SELECT, "pages", return_value=[]):
            self.assertEqual(SELECT.select(REPO, SHA, "schedule", NOW)["mode"], "full")

    def test_invalid_receipts_never_fall_back_to_an_older_success(self):
        def pages(endpoint, field):
            if field == "workflow_runs":
                return [run_fixture()] if "event=push" in endpoint else []
            return jobs_fixture() if field == "jobs" else []
        with patch.object(SELECT, "pages", side_effect=pages), patch.object(
            SELECT, "verify_receipts", side_effect=ValueError("changed receipt")
        ):
            self.assertEqual(SELECT.select(REPO, SHA, "schedule", NOW)["mode"], "full")

    def test_artifact_digest_ownership_expiration_and_member_safety(self):
        metadata, body = archive_fixture([("receipt.json", b"{}")])
        with patch.object(SELECT, "github", return_value=body):
            self.assertEqual(SELECT.archive_files(metadata, run_fixture(), REPO), {"receipt.json": b"{}"})
            for key, value in (("expired", True), ("size_in_bytes", SELECT.MAX_ARCHIVE + 1),
                               ("digest", "sha256:" + "0" * 64)):
                broken = {**metadata, key: value}
                with self.subTest(key=key), self.assertRaises(ValueError):
                    SELECT.archive_files(broken, run_fixture(), REPO)
            for key in ("id", "head_sha", "head_branch", "repository_id", "head_repository_id"):
                broken = deepcopy(metadata)
                broken["workflow_run"][key] = "outside"
                with self.subTest(key=key), self.assertRaises(ValueError):
                    SELECT.archive_files(broken, run_fixture(), REPO)
        link = zipfile.ZipInfo("link")
        link.create_system = 3
        link.external_attr = 0o120777 << 16
        for entries in ([('../escape', b'x')], [('nested/file', b'x')], [('..', b'x')],
                        [('file', b'x'), ('file', b'y')], [(link, b'target')]):
            metadata, body = archive_fixture(entries)
            with patch.object(SELECT, "github", return_value=body), self.assertRaises(ValueError):
                SELECT.archive_files(metadata, run_fixture(), REPO)

    def test_real_receipt_reconciliation_and_tampered_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin = root / "security/provider"
            pin.mkdir(parents=True)
            scripts = root / "scripts"
            scripts.mkdir()
            for name in ("go.mod", "go.sum"):
                (pin / name).write_text("pinned " + name)
            manifest = {"go_version": "go1.27.3", "source_sha256": "d" * 64,
                        "module_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pin.iterdir()}}
            (pin / "manifest.json").write_text(json.dumps(manifest))
            for name in ("build_secure_provider.py", "provider_test_shards.py"):
                (scripts / name).write_text("fixture " + name)
            context = {"qualification_id": SHA, "manifest": manifest,
                       "actual_go_version": manifest["go_version"],
                       "test_platform": "linux_amd64", "target_platform": "linux_amd64",
                       "scripts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in scripts.iterdir()},
                       "test_command": BUILD.unit_test_command("go", ["<packages>"])}
            packages = ["fixture"] + [f"fixture/p{i:02}" for i in range(16)]
            receipts = root / "receipts"
            receipts.mkdir()
            records = {}
            for index in range(16):
                log = receipts / "test.log"
                log.write_text("".join(f"ok\t{name}\t0.001s\n" for name in partition(packages, index, 16)))
                write_receipt(receipts, context, packages, index, 16, log)
                records[f"provider-unit-receipt-{index}"] = {
                    f"shard-{index}.{suffix}": (receipts / f"shard-{index}.{suffix}").read_bytes()
                    for suffix in ("json", "log")}
            summary = reconcile(receipts, context, packages, 16)
            provenance = {**manifest, "qualification_id": SHA, "platform": "linux_amd64",
                          "actual_go_version": manifest["go_version"], "binary_sha256": "e" * 64,
                          "unit_test_shards": summary}
            records["cloudflare-provider-qualification"] = {
                "provenance.json": json.dumps(provenance).encode(),
                "unit-shards.json": json.dumps(summary).encode(),
                "packages.log": "\n".join(packages).encode(),
                **{name: (pin / name).read_bytes() for name in ("go.mod", "go.sum")}}
            artifacts = [{"name": name} for name in records]
            with patch.object(SELECT, "archive_files", side_effect=lambda artifact, *_: records[artifact["name"]]):
                self.assertEqual(SELECT.verify_receipts(artifacts, run_fixture(), REPO, root), summary)
                for changed in (artifacts[:-1], artifacts + [artifacts[0]]):
                    with self.assertRaises(ValueError):
                        SELECT.verify_receipts(changed, run_fixture(), REPO, root)
                original = records["provider-unit-receipt-0"]["shard-0.log"]
                records["provider-unit-receipt-0"]["shard-0.log"] = b"tampered"
                with self.assertRaises(ValueError):
                    SELECT.verify_receipts(artifacts, run_fixture(), REPO, root)
                records["provider-unit-receipt-0"]["shard-0.log"] = original
                (scripts / "build_secure_provider.py").write_text("changed builder")
                with self.assertRaises(ValueError):
                    SELECT.verify_receipts(artifacts, run_fixture(), REPO, root)


if __name__ == "__main__":
    unittest.main()
