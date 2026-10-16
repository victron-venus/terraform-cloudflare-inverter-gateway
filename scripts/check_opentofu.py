#!/usr/bin/env python3
"""Validate a temporary OpenTofu compatibility copy; never read state or apply."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def adapt_source(name, text):
    """Translate version/provider identity and mock syntax, never policy assertions."""
    if name.endswith((".tf", ".hcl", ".fixture", ".py")):
        for provider in ("cloudflare/cloudflare", "hashicorp/local"):
            text = text.replace(f'"{provider}"', f'"registry.terraform.io/{provider}"')
        if name.endswith(".tftest.hcl"):
            # OpenTofu uses its own plan mocking semantics and rejects this Terraform keyword.
            text = re.sub(
                r"^\s*override_during\s*=\s*plan\s*\n", "", text, flags=re.MULTILINE
            )
    return text


def main():
    """Run the existing complete source/policy gate using a verified FLOSS tool."""
    root = Path(__file__).resolve().parents[1]
    binary = shutil.which(os.environ.get("TOFU_BIN", "tofu"))
    if not binary:
        raise SystemExit(
            "Install OpenTofu 1.13.1 or set TOFU_BIN to its executable path"
        )
    binary = str(Path(binary).resolve())
    with tempfile.TemporaryDirectory(prefix="opentofu-validation-") as temporary:
        temporary = Path(temporary)
        stage = temporary / "source"
        stage.mkdir()
        configuration = temporary / "empty.tfrc"
        configuration.write_text("", encoding="utf-8")
        tool_dir = temporary / "bin"
        tool_dir.mkdir()
        # Existing entry points invoke terraform; this alias is confined to this subprocess.
        (tool_dir / "terraform").symlink_to(binary)
        environment = {
            "PATH": str(tool_dir) + os.pathsep + os.environ.get("PATH", ""),
            "HOME": str(temporary),
            "TF_CLI_CONFIG_FILE": str(configuration),
            "TF_INPUT": "0",
            "TF_IN_AUTOMATION": "1",
            "CHECKPOINT_DISABLE": "1",
            "GODEBUG": "fips140=on",
        }
        version = subprocess.run(
            [binary, "version", "-json"],
            cwd=temporary,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        metadata = json.loads(version.stdout)
        if metadata.get("terraform_version") != "1.13.1":
            raise SystemExit("This compatibility profile requires OpenTofu 1.13.1")
        names = (
            subprocess.check_output(
                ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                cwd=root,
            )
            .decode()
            .split("\0")
        )
        for name in set(names):
            source = root / name
            if not name or not source.is_file() or source.is_symlink():
                continue
            if ".terraform" in source.parts or ".tfstate" in source.name:
                continue
            if name.endswith((".tfvars", ".tfvars.json")):
                continue
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                text = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                shutil.copyfile(source, target)
            else:
                target.write_text(adapt_source(name, text), encoding="utf-8")
        # Removing Terraform-only attributes changes alignment in copied HCL.
        subprocess.run(
            [binary, "fmt", "-recursive"], cwd=stage, env=environment, check=True
        )
        subprocess.run(["git", "init", "-q"], cwd=stage, env=environment, check=True)
        subprocess.run(["git", "add", "."], cwd=stage, env=environment, check=True)
        if (stage / "scripts/ci.sh").exists():
            commands = [["bash", "scripts/ci.sh"]]
        else:
            commands = [
                ["terraform", "fmt", "-check", "-recursive"],
                [
                    "terraform",
                    "init",
                    "-backend=false",
                    "-input=false",
                    "-lockfile=readonly",
                ],
                ["terraform", "validate", "-no-color"],
                ["bash", "scripts/test-public-security.sh"],
                ["tflint", "--config=" + str(stage / ".tflint.hcl"), "--recursive"],
            ]
        for command in commands:
            subprocess.run(command, cwd=stage, env=environment, check=True)
    print(
        "OpenTofu compatibility checks passed; no original files, state or live resources changed."
    )


if __name__ == "__main__":
    main()
