"""Select each explicitly supplied TLS fixture provider without a version duplicate."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml


ROOT = Path(__file__).resolve().parents[1]
with patch.dict(os.environ, {
    "TLS_TEST_TERRAFORM": "/unused/terraform",
    "TLS_TEST_PROVIDER_DIR": "/unused/provider",
    "TLS_TEST_PLATFORM": "linux_amd64",
}):
    SPEC = importlib.util.spec_from_file_location(
        "tls_fixture_identity", ROOT / "scripts/test_tls_profile.py"
    )
    FIXTURE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(FIXTURE)


class TLSProviderIdentityTests(unittest.TestCase):
    def test_official_and_derivative_binary_versions_are_independent(self):
        for name, expected in (
            ("terraform-provider-cloudflare_v5.28.1_x5", "5.28.1"),
            ("terraform-provider-cloudflare_v5.24.0", "5.24.0"),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_bytes(b"synthetic executable identity only")
                (root / "LICENSE.txt").write_text("synthetic license fixture")
                self.assertEqual(FIXTURE.selected_provider_version(root), expected)

    def test_missing_ambiguous_directory_or_malformed_binary_is_rejected(self):
        for names in ((), ("terraform-provider-cloudflare_v5.28.1_x5", "terraform-provider-cloudflare_v5.24.0"), ("terraform-provider-cloudflare_v5.28.1_x5_extra",), ("terraform-provider-cloudflare_v５.28.1",)):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for name in names:
                    (root / name).write_bytes(b"fixture")
                with self.assertRaises(ValueError):
                    FIXTURE.selected_provider_version(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "terraform-provider-cloudflare_v5.28.1").mkdir()
            with self.assertRaises(ValueError):
                FIXTURE.selected_provider_version(root)

    def test_workflow_compilers_match_the_reviewed_provider_manifest(self):
        manifest = json.loads((ROOT / "security/provider/manifest.json").read_text())
        workflow = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())
        versions = [
            step["with"]["go-version"]
            for job in workflow["jobs"].values()
            for step in job.get("steps", [])
            if step.get("uses", "").startswith("actions/setup-go@")
        ]
        self.assertEqual(len(versions), 3)
        self.assertEqual(set(versions), {manifest["go_version"].removeprefix("go")})
