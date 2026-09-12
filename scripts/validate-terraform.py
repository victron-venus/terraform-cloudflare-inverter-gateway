#!/usr/bin/env python3
"""Format/validate disposable source copies. Never plan/apply or read state."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
policy = json.loads((root / ".release-policy.json").read_text())
if not shutil.which("terraform"):
    raise SystemExit("Install Terraform 1.15.7 before running scripts/ci.sh")
files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
with tempfile.TemporaryDirectory(prefix="terraform-ci-") as temporary:
    stage = Path(temporary) / "source"
    stage.mkdir()
    for name in set(files):
        source = root / name
        if not name or not source.is_file() or source.is_symlink() or ".terraform" in source.parts or ".tfstate" in source.name or source.suffix == ".tfvars":
            continue
        target = stage / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for fixture in stage.glob("deployments/*/compose.redacted.yml"):
        shutil.copyfile(fixture, fixture.with_name("compose.yml"))
    env = {key: value for key, value in os.environ.items() if not key.startswith(("TF_VAR_", "TF_TOKEN_", "TF_CLI_ARGS"))}
    env.update(TF_IN_AUTOMATION="1", TF_INPUT="0", TF_CLI_CONFIG_FILE=str(Path(temporary) / "empty.tfrc"))
    Path(env["TF_CLI_CONFIG_FILE"]).write_text("")
    cache = Path(temporary) / "provider-cache"
    cache.mkdir()
    env["TF_PLUGIN_CACHE_DIR"] = str(cache)
    for index, relative in enumerate(policy["terraform_roots"]):
        env["TF_DATA_DIR"] = str(Path(temporary) / f"terraform-data-{index}")
        directory = stage / relative
        if not directory.resolve().is_relative_to(stage.resolve()) or not directory.is_dir():
            raise SystemExit(f"Invalid Terraform root: {relative}")
        print(f"Validating Terraform root: {relative}", flush=True)
        subprocess.run(["terraform", "fmt", "-check", "-recursive"], cwd=directory, env=env, check=True)
        subprocess.run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], cwd=directory, env=env, check=True)
        subprocess.run(["terraform", "validate", "-no-color"], cwd=directory, env=env, check=True)
print("Terraform format/schema passed; no plan, apply, backend, state or live-resource checks performed.")
