#!/usr/bin/env python3
"""Qualify the disclosed provider against disposable source and mocked plans."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from check_opentofu import stage_source


def verified_derivative(root, provider, platform):
    """Require exact reviewed inputs and the recorded binary digest."""
    expected = json.loads((root / "security/provider/manifest.json").read_text())
    provenance = json.loads((provider / "provenance.json").read_text())
    for key in (
        "source_commit",
        "source_sha256",
        "go_version",
        "build_version",
        "module_files",
    ):
        if provenance.get(key) != expected[key]:
            raise ValueError(
                "Provider provenance differs from reviewed manifest: " + key
            )
    if provenance.get("platform") != platform:
        raise ValueError("Provider platform differs from requested platform")
    executable = provider / expected["binary_name"]
    if hashlib.sha256(executable.read_bytes()).hexdigest() != provenance.get(
        "binary_sha256"
    ):
        raise ValueError("Provider binary digest differs from build provenance")
    return expected, executable


def install_local_provider(root, archive, mirror, platform):
    """Extract only the locked official local-provider executable, without paths."""
    lock = (root / ".terraform.lock.hcl").read_text()
    section = re.search(
        r'provider "registry\.terraform\.io/hashicorp/local" \{(.*?)\n\}',
        lock,
        re.DOTALL,
    )
    if not section or not re.search(r'version\s*=\s*"2\.9\.0"', section.group(1)):
        raise ValueError("Expected locked local provider 2.9.0")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if '"zh:' + digest + '"' not in section.group(1):
        raise ValueError("Local-provider archive does not match the original lock")
    with zipfile.ZipFile(archive) as bundle:
        names = [
            n
            for n in bundle.namelist()
            if n.startswith("terraform-provider-local_v2.9.0") and "/" not in n
        ]
        if len(names) != 1:
            raise ValueError("Expected one local-provider executable")
        target = (
            mirror / "registry.terraform.io/hashicorp/local/2.9.0" / platform / names[0]
        )
        target.parent.mkdir(parents=True)
        target.write_bytes(bundle.read(names[0]))
        target.chmod(0o755)


def qualify(args):
    """Use only explicit binaries, temporary locks and a filesystem-only mirror."""
    root = Path(__file__).resolve().parents[1]
    engine = args.engine.resolve(strict=True)
    expected, executable = verified_derivative(
        root, args.provider_dir.resolve(strict=True), args.platform
    )
    with tempfile.TemporaryDirectory(prefix="secure-provider-validation-") as directory:
        temporary = Path(directory)
        stage = temporary / "source"
        stage.mkdir()
        # OpenTofu's syntax translation only removes override_during; assertions remain.
        stage_source(root, stage)
        for lock in stage.rglob(".terraform.lock.hcl"):
            lock.unlink()
        mirror = temporary / "mirror"
        destination = (
            mirror
            / expected["provider_address"]
            / expected["upstream_version"]
            / args.platform
        )
        destination.mkdir(parents=True)
        shutil.copyfile(executable, destination / executable.name)
        (destination / executable.name).chmod(0o755)
        install_local_provider(
            root,
            args.local_provider_archive.resolve(strict=True),
            mirror,
            args.platform,
        )
        config = temporary / "mirror.tfrc"
        config.write_text(
            "provider_installation {\n filesystem_mirror {\n path = "
            + json.dumps(str(mirror))
            + "\n }\n}\n"
        )
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(temporary),
            "TF_CLI_CONFIG_FILE": str(config),
            "TF_INPUT": "0",
            "TF_IN_AUTOMATION": "1",
            "CHECKPOINT_DISABLE": "1",
            "GODEBUG": "fips140=on",
        }
        version = json.loads(
            subprocess.check_output(
                [str(engine), "version", "-json"], env=environment, text=True
            )
        )
        if version.get("terraform_version") != "1.13.1":
            raise ValueError(
                "This compatibility qualification requires OpenTofu 1.13.1"
            )
        commands = (
            ["fmt", "-recursive"],
            ["init", "-backend=false", "-input=false", "-no-color"],
            ["validate", "-no-color"],
            ["test", "-test-directory=tests/terraform", "-no-color"],
        )
        for command in commands:
            subprocess.run(
                [str(engine), *command], cwd=stage, env=environment, check=True
            )
    print(
        "Derivative schema and four mocked plans passed; no original state, locks or resources changed."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--engine", type=Path, required=True, help="Verified OpenTofu 1.13.1"
    )
    parser.add_argument("--provider-dir", type=Path, required=True)
    parser.add_argument("--local-provider-archive", type=Path, required=True)
    parser.add_argument(
        "--platform",
        choices=("linux_amd64", "linux_arm64", "darwin_amd64", "darwin_arm64"),
        required=True,
    )
    qualify(parser.parse_args())


if __name__ == "__main__":
    main()
