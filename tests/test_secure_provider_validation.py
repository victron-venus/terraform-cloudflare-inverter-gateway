"""Reject mismatched derivative provenance and unverified local-provider archives."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "secure_validation", SCRIPTS / "check_secure_provider.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecureProviderValidationTests(unittest.TestCase):
    def test_changed_binary_or_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = root / "build"
            provider.mkdir()
            (root / "security/provider").mkdir(parents=True)
            manifest = {
                "source_commit": "reviewed",
                "source_sha256": "archive",
                "go_version": "go1.27.2",
                "build_version": "5.24.0-openssf.1",
                "module_files": {},
                "binary_name": "provider",
            }
            (root / "security/provider/manifest.json").write_text(json.dumps(manifest))
            (provider / "provider").write_bytes(b"reviewed binary")
            provenance = {
                **manifest,
                "platform": "linux_arm64",
                "binary_sha256": hashlib.sha256(b"reviewed binary").hexdigest(),
            }
            record = provider / "provenance.json"
            record.write_text(json.dumps(provenance))
            expected, executable = MODULE.verified_derivative(
                root, provider, "linux_arm64"
            )
            self.assertEqual(expected, manifest)
            self.assertEqual(executable, provider / "provider")
            for key, value in (
                ("source_commit", "different"),
                ("platform", "darwin_arm64"),
                ("binary_sha256", "mismatch"),
            ):
                with self.subTest(key=key):
                    record.write_text(json.dumps({**provenance, key: value}))
                    with self.assertRaises(ValueError):
                        MODULE.verified_derivative(root, provider, "linux_arm64")

    def test_only_locked_local_archive_is_installed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "local.zip"
            name = "terraform-provider-local_v2.9.1_x5"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(name, b"synthetic executable")
                bundle.writestr("../outside", b"ignored")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            (root / ".terraform.lock.hcl").write_text(
                'provider "registry.terraform.io/hashicorp/local" {\n version = "2.9.1"\n hashes = ["zh:'
                + digest
                + '"]\n}\n'
            )
            mirror = root / "mirror"
            MODULE.install_local_provider(root, archive, mirror, "linux_arm64")
            target = (
                mirror
                / "registry.terraform.io/hashicorp/local/2.9.1/linux_arm64"
                / name
            )
            self.assertEqual(target.read_bytes(), b"synthetic executable")
            self.assertFalse((root / "outside").exists())
            archive.write_bytes(b"untrusted archive")
            with self.assertRaises(ValueError):
                MODULE.install_local_provider(root, archive, mirror, "linux_arm64")


if __name__ == "__main__":
    unittest.main()
