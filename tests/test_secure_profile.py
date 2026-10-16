"""Local deployment profile rejects remote state and changed provider provenance."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

SPEC = importlib.util.spec_from_file_location(
    "secure_profile", Path(__file__).parents[1] / "scripts/run_secure_profile.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecureProfileTests(unittest.TestCase):
    def test_rejects_hcp_and_remote_backends_in_hcl_or_json(self):
        for name, content in [
            ("main.tf", 'terraform { cloud { organization="example" } }'),
            ("main.tf", 'terraform { backend "s3" {} }'),
            ("main.tf.json", '{"terraform":{"backend":{"http":{}}}}'),
        ]:
            with (
                self.subTest(content=content),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                (root / name).write_text(content)
                with self.assertRaisesRegex(ValueError, "local-state"):
                    MODULE.reject_remote_backend(root)

    def test_rejects_cached_remote_state_without_revealing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".terraform").mkdir()
            (root / ".terraform/terraform.tfstate").write_text(
                json.dumps(
                    {"backend": {"type": "cloud", "config": {"secret": "synthetic"}}}
                )
            )
            with self.assertRaisesRegex(ValueError, "remote backend") as error:
                MODULE.reject_remote_backend(root)
            self.assertNotIn("synthetic", str(error.exception))

    def test_local_workspace_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.tf").write_text('terraform { required_version = ">=1.13.1" }')
            MODULE.reject_remote_backend(root)
