"""Protect the boundary between synthetic validation and operator credentials."""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "terraform_validation", Path(__file__).parents[1] / "scripts/validate-terraform.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TerraformIsolationTests(unittest.TestCase):
    def test_operator_options_and_credentials_are_removed(self):
        private = {
            "TF_VAR_key_xyz": "private",
            "TF_TOKEN_example": "private",
            "TF_CLI_ARGS_plan": "-destroy",
            "TF_REATTACH_PROVIDERS": "{}",
            "CLOUDFLARE_API_TOKEN": "private",
            "CF_API_KEY": "private",
            "TF_WORKSPACE": "production",
            "TF_DISABLE_PLUGIN_TLS": "1",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, private),
        ):
            env = MODULE.isolated_environment(Path(directory))
            self.assertFalse(set(private) & set(env))
            self.assertEqual(Path(env["TF_CLI_CONFIG_FILE"]).read_text(), "")
            self.assertEqual(env["TF_INPUT"], "0")

    def test_source_copy_rejects_state_private_variables_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            stage = Path(directory) / "stage"
            root.mkdir()
            stage.mkdir()
            names = [
                "main.tf",
                "terraform.tfstate",
                "auto.tfvars",
                "x.tfvars.json",
                ".terraform/provider",
            ]
            for name in names:
                file = root / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("synthetic")
            (root / "linked.tf").symlink_to(root / "auto.tfvars")
            result = type(
                "Output", (), {"stdout": "\0".join(names + ["linked.tf"]).encode()}
            )()
            with patch.object(MODULE.subprocess, "run", return_value=result):
                MODULE.stage_sources(root, stage)
            self.assertEqual([p.name for p in stage.iterdir()], ["main.tf"])
