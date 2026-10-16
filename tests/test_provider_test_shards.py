"""Full inventory coverage and fail-closed CI receipt aggregation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from test_secure_provider import MODULE as BUILD
from provider_test_shards import partition, reconcile, write_receipt


class ProviderShardTests(unittest.TestCase):
    def make_receipts(self, root):
        packages = ["fixture", "fixture/a", "fixture/b", "fixture/c", "fixture/d"]
        context = {"source": "pinned", "compiler": "go1.27.2", "commit": "a" * 40}
        for index in range(3):
            log = root / "test.log"
            log.write_text(
                "".join(
                    f"ok\t{name}\t0.001s\n" for name in partition(packages, index, 3)
                )
            )
            write_receipt(root, context, packages, index, 3, log)
        return context, packages

    def test_exact_union_with_no_test_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context, packages = self.make_receipts(root)
            summary = reconcile(root, context, packages, 3)
            self.assertEqual(summary["packages"], len(packages))
            self.assertEqual(len(summary["shards"]), 3)

    def test_missing_extra_failed_cross_input_and_duplicate_assignment_rejected(self):
        for mutation in (
            "missing",
            "extra",
            "failed",
            "skipped",
            "context",
            "inventory",
            "duplicate",
            "log",
        ):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                context, packages = self.make_receipts(root)
                path = root / "shard-1.json"
                receipt = json.loads(path.read_text())
                if mutation == "missing":
                    path.unlink()
                elif mutation == "extra":
                    shutil.copyfile(path, root / "shard-8.json")
                elif mutation == "log":
                    (root / "shard-1.log").write_text("ok\tfixture/a\t0.001s\n")
                else:
                    if mutation in ("failed", "skipped"):
                        receipt["result"] = mutation
                    elif mutation == "context":
                        receipt["context"]["compiler"] = "go1.26.1"
                    elif mutation == "inventory":
                        receipt["inventory"] = packages[:-1]
                    elif mutation == "duplicate":
                        receipt["packages"] = partition(packages, 0, 3)
                    path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):
                    reconcile(root, context, packages, 3)

    def test_empty_duplicate_and_option_like_inventory_rejected(self):
        for packages in ([], ["a", "a"], ["-run=Safe"], ["a/../b"], ["b", "a"]):
            with self.subTest(packages=packages), self.assertRaises(ValueError):
                partition(packages, 0, 2)
        with self.assertRaises(ValueError):
            partition(["a"], 0, 2)

    def test_success_receipt_requires_every_package_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "test.log"
            log.write_text("ok\tfixture/a\t0.001s\n")
            with self.assertRaises(ValueError):
                write_receipt(root, {}, ["fixture/a", "fixture/b"], 0, 1, log)
            self.assertFalse((root / "shard-0.json").exists())

    def test_real_go_shards_cover_all_packages_and_preserve_test_filter(self):
        go = shutil.which("go")
        if not go:
            self.skipTest("Go required for real package execution")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "go.mod").write_text("module fixture\n\ngo 1.23\n")
            (root / "root.go").write_text("package fixture\n")
            for index in range(6):
                package = root / f"p{index}"
                package.mkdir()
                (package / "unit_test.go").write_text(
                    'package sample\nimport("testing";"os")\n'
                    'func TestAccount(t *testing.T) { if err := os.WriteFile("ran", []byte("yes"),0600); err != nil { t.Fatal(err) } }\n'
                    'func TestAccNetwork(t *testing.T) { t.Fatal("acceptance must stay excluded") }\n'
                )
            environment = {
                **os.environ,
                "GOWORK": "off",
                "GOENV": "off",
                "GOTOOLCHAIN": "local",
                "CGO_ENABLED": "0",
                "GOMAXPROCS": "2",
            }
            packages = sorted(
                subprocess.check_output(
                    [go, "list", "./..."], cwd=root, env=environment, text=True
                ).splitlines()
            )
            self.assertEqual(len(packages), 7)
            receipts = root / "receipts"
            receipts.mkdir()
            for index in range(3):
                selected = partition(packages, index, 3)
                result = subprocess.run(
                    BUILD.unit_test_command(go, selected),
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                log = receipts / "current.log"
                log.write_text(result.stdout + result.stderr)
                write_receipt(receipts, {"fixture": True}, packages, index, 3, log)
            summary = reconcile(receipts, {"fixture": True}, packages, 3)
            self.assertEqual(summary["packages"], 7)
            for index in range(6):
                self.assertEqual((root / f"p{index}" / "ran").read_text(), "yes")

    def test_workflow_requires_all_shards_before_production_and_transport(self):
        workflow = yaml.safe_load(
            (Path(__file__).parents[1] / ".github/workflows/validate.yml").read_text()
        )
        shards = workflow["jobs"]["provider_unit_tests"]
        final = workflow["jobs"]["validate"]
        self.assertEqual(shards["strategy"]["matrix"]["shard"], list(range(8)))
        self.assertFalse(shards["strategy"]["fail-fast"])
        self.assertEqual(final["needs"], "provider_unit_tests")
        guard = final["steps"][0]
        self.assertEqual(
            guard["env"]["UNIT_RESULT"], "${{ needs.provider_unit_tests.result }}"
        )
        for result in ("success", "failure", "cancelled", "skipped", ""):
            actual = subprocess.run(
                ["bash", "-c", guard["run"]],
                env={**os.environ, "UNIT_RESULT": result},
                check=False,
            )
            self.assertEqual(actual.returncode == 0, result == "success")
        final_command = next(
            step["run"]
            for step in final["steps"]
            if step.get("name")
            == "Build and qualify the disclosed provider security patch"
        )
        self.assertIn("--test-receipts", final_command)
        self.assertIn("--test-shards 8", final_command)
        self.assertEqual(final_command.count("scripts/test_tls_profile.py"), 3)
        self.assertIn("scripts/check_secure_provider.py", final_command)


if __name__ == "__main__":
    unittest.main()
