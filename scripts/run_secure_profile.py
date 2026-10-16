#!/usr/bin/env python3
"""Run a verified derivative in an explicitly chosen local-state workspace."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from check_secure_provider import install_local_provider, verified_derivative


def reject_remote_backend(workspace):
    """Fail closed for cloud/backend declarations, even if commented ambiguously."""
    for source in [*workspace.glob("*.tf"), *workspace.glob("*.tf.json")]:
        text = source.read_text()
        if re.search(r'\b(?:cloud|backend)\s*(?:"[^"]*")?\s*\{', text) or (
            source.suffix == ".json" and re.search(r'"(?:cloud|backend)"\s*:', text)
        ):
            raise ValueError(
                "This profile requires a separate local-state workspace without cloud/backend blocks"
            )
    cached = workspace / ".terraform/terraform.tfstate"
    if cached.exists() and json.loads(cached.read_text()).get("backend", {}).get(
        "type"
    ) not in (None, "local"):
        raise ValueError(
            "Existing workspace has a remote backend; no automatic state migration is allowed"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tofu", type=Path, required=True)
    parser.add_argument("--provider-dir", type=Path, required=True)
    parser.add_argument("--local-provider-archive", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument(
        "--platform",
        choices=("linux_amd64", "linux_arm64", "darwin_amd64", "darwin_arm64"),
        required=True,
    )
    parser.add_argument("command", choices=("init", "validate", "plan", "apply"))
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    workspace = args.directory.resolve(strict=True)
    reject_remote_backend(workspace)
    expected, provider = verified_derivative(
        root, args.provider_dir.resolve(strict=True), args.platform
    )
    tofu = args.tofu.resolve(strict=True)
    tool_hashes = json.loads(
        (root / "security/provider/opentofu-binaries.json").read_text()
    )
    if hashlib.sha256(tofu.read_bytes()).hexdigest() != tool_hashes.get(args.platform):
        raise ValueError(
            "OpenTofu binary is not the qualified official1.13.1 build for this platform"
        )
    if args.command == "init" and args.arguments:
        raise ValueError("Additional init options are not supported")
    with tempfile.TemporaryDirectory(prefix="verified-local-provider-") as directory:
        temporary = Path(directory)
        mirror = (
            temporary
            / "mirror"
            / expected["provider_address"]
            / expected["upstream_version"]
            / args.platform
        )
        mirror.mkdir(parents=True)
        shutil.copyfile(provider, mirror / provider.name)
        (mirror / provider.name).chmod(0o755)
        install_local_provider(
            root,
            args.local_provider_archive.resolve(strict=True),
            temporary / "mirror",
            args.platform,
        )
        config = temporary / "mirror.tfrc"
        config.write_text(
            "provider_installation {\n filesystem_mirror {\n path = "
            + json.dumps(str(temporary / "mirror"))
            + "\n }\n}\n"
        )
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.startswith("TF_VAR_")
            or key
            in (
                "PATH",
                "CLOUDFLARE_API_TOKEN",
                "CLOUDFLARE_API_KEY",
                "CLOUDFLARE_EMAIL",
                "SSL_CERT_FILE",
                "SSL_CERT_DIR",
            )
        }
        environment.update(
            HOME=str(temporary),
            TF_CLI_CONFIG_FILE=str(config),
            TF_INPUT="1",
            CHECKPOINT_DISABLE="1",
            GODEBUG="fips140=on",
        )
        metadata = json.loads(
            subprocess.check_output(
                [str(tofu), "version", "-json"], env=environment, text=True, umask=0o077
            )
        )
        if metadata.get("terraform_version") != "1.13.1":
            raise ValueError(
                "This profile requires the verified OpenTofu1.13.1 executable"
            )
        # No registry fallback exists. Re-init recreates temporary provider symlinks.
        subprocess.run(
            [str(tofu), "init", "-backend=false", "-input=false"],
            cwd=workspace,
            env=environment,
            check=True,
            umask=0o077,
        )
        if args.command != "init":
            subprocess.run(
                [str(tofu), args.command, *args.arguments],
                cwd=workspace,
                env=environment,
                check=True,
                umask=0o077,
            )


if __name__ == "__main__":
    main()
