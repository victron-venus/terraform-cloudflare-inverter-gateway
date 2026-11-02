#!/usr/bin/env python3
"""Reuse only recent, complete same-commit qualification; otherwise run every shard."""

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from build_secure_provider import unit_test_command
from provider_test_shards import checked_inventory, reconcile

ROOT = Path(__file__).resolve().parents[1]
MAX_AGE = timedelta(days=7)
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
WORKFLOW = ".github/workflows/quality-gate.yml"


def github(endpoint, binary=False):
    """Use gh's authenticated redirect handling without printing credentials."""
    result = subprocess.run(
        ["gh", "api", "--hostname", "github.com", endpoint],
        capture_output=True, check=True, timeout=60,
    )
    return result.stdout if binary else json.loads(result.stdout)


def pages(endpoint, field):
    """Bound pagination; incomplete or ambiguous evidence is never reused."""
    values = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, 21):
        data = github(f"{endpoint}{separator}per_page=100&page={page}")
        batch = data[field]
        values.extend(batch)
        if len(batch) < 100:
            return values
    raise ValueError("Qualification evidence exceeds pagination bound")


def trusted_run(run, repository, sha, now):
    """Require fresh same-repository default-branch push/manual qualification."""
    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    return (
        run["status"] == "completed" and run["conclusion"] == "success"
        and run["event"] in {"push", "workflow_dispatch"}
        and run["head_sha"] == sha and run["head_branch"] == "main"
        and run["repository"]["full_name"] == repository
        and run["head_repository"]["full_name"] == repository
        and run["path"].split("@")[0] == WORKFLOW
        and timedelta(0) <= now - created <= MAX_AGE
    )


def complete_jobs(jobs):
    """A skipped, duplicated or missing shard cannot authorize reuse."""
    names = [f"check-0 / Provider unit tests / shard {i}" for i in range(16)]
    names += ["check-0 / Repository validation", "CI gate"]
    counts = Counter(job["name"] for job in jobs)
    return all(
        counts[name] == 1 and any(
            job["name"] == name and job["status"] == "completed"
            and job["conclusion"] == "success" for job in jobs
        ) for name in names
    )


def archive_files(artifact, run, repository):
    """Verify the immutable artifact bytes and read bounded regular members only."""
    owner = artifact["workflow_run"]
    if (
        artifact["expired"] or not 0 < artifact["size_in_bytes"] <= MAX_ARCHIVE
        or owner["id"] != run["id"] or owner["head_sha"] != run["head_sha"]
        or owner["head_branch"] != "main"
        or owner["repository_id"] != run["repository"]["id"]
        or owner["head_repository_id"] != run["repository"]["id"]
    ):
        raise ValueError("Artifact does not belong to the trusted qualification")
    digest = artifact.get("digest", "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Artifact has no integrity digest")
    content = github(
        f"repos/{repository}/actions/artifacts/{artifact['id']}/zip", binary=True,
    )
    if len(content) > MAX_ARCHIVE or "sha256:" + hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Qualification artifact digest mismatch")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.infolist()
        if (
            len(members) > 100 or len({m.filename for m in members}) != len(members)
            or sum(m.file_size for m in members) > MAX_EXPANDED
            or any(m.is_dir() or "/" in m.filename or "\\" in m.filename
                   or m.filename in {".", ".."}
                   or ((m.external_attr >> 16) & 0o170000) not in {0, 0o100000}
                   for m in members)
        ):
            raise ValueError("Ambiguous or unsafe qualification archive")
        return {m.filename: archive.read(m) for m in members}


def verify_receipts(artifacts, run, repository, root=ROOT):
    """Reconcile hashed logs against current pinned source and script inputs."""
    expected = {"cloudflare-provider-qualification"}
    expected.update(f"provider-unit-receipt-{i}" for i in range(16))
    selected = [a for a in artifacts if a["name"] in expected]
    if Counter(a["name"] for a in selected) != Counter(expected):
        raise ValueError("Missing or ambiguous qualification artifacts")
    records = {a["name"]: archive_files(a, run, repository) for a in selected}
    final = records["cloudflare-provider-qualification"]
    manifest = json.loads((root / "security/provider/manifest.json").read_text())
    provenance = json.loads(final["provenance.json"])
    if (
        any(provenance.get(k) != value for k, value in manifest.items())
        or provenance.get("qualification_id") != run["head_sha"]
        or provenance.get("platform") != "linux_amd64"
        or provenance.get("actual_go_version") != manifest["go_version"]
        or not re.fullmatch(r"[0-9a-f]{64}", provenance.get("binary_sha256", ""))
    ):
        raise ValueError("Qualification manifest or toolchain changed")
    for name, digest in manifest["module_files"].items():
        if (
            hashlib.sha256((root / "security/provider" / name).read_bytes()).hexdigest() != digest
            or hashlib.sha256(final[name]).hexdigest() != digest
        ):
            raise ValueError("Qualified module inputs changed")
    packages = checked_inventory(sorted(final["packages.log"].decode().splitlines()))
    context = {
        "qualification_id": run["head_sha"], "manifest": manifest,
        "actual_go_version": manifest["go_version"],
        "test_platform": "linux_amd64", "target_platform": "linux_amd64",
        "scripts": {name: hashlib.sha256((root / "scripts" / name).read_bytes()).hexdigest()
                    for name in ("build_secure_provider.py", "provider_test_shards.py")},
        "test_command": unit_test_command("go", ["<packages>"]),
    }
    with tempfile.TemporaryDirectory(prefix="provider-receipts-") as temporary:
        directory = Path(temporary)
        for index in range(16):
            for suffix in ("json", "log"):
                name = f"shard-{index}.{suffix}"
                (directory / name).write_bytes(records[f"provider-unit-receipt-{index}"][name])
        summary = reconcile(directory, context, packages, 16)
    if summary != json.loads(final["unit-shards.json"]) or summary != provenance["unit_test_shards"]:
        raise ValueError("Final qualification disagrees with the shard receipts")
    return summary


def select(repository, sha, event, now=None):
    """API errors and absent/old evidence conservatively select full validation."""
    fallback = {"mode": "full", "reason": "Full qualification required", "source_sha": sha}
    if event != "schedule":
        return fallback
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected an exact GitHub repository and source commit")
    now = now or datetime.now(timezone.utc)
    try:
        runs = []
        for trigger in ("push", "workflow_dispatch"):
            runs.extend(pages(
                f"repos/{repository}/actions/workflows/quality-gate.yml/runs"
                f"?head_sha={sha}&status=success&event={trigger}", "workflow_runs",
            ))
        candidates = sorted((r for r in runs if trusted_run(r, repository, sha, now)),
                            key=lambda r: r["id"], reverse=True)
        if not candidates:
            return fallback
        run = candidates[0]
        jobs = pages(f"repos/{repository}/actions/runs/{run['id']}/jobs?filter=latest", "jobs")
        if not complete_jobs(jobs):
            return fallback
        artifacts = pages(f"repos/{repository}/actions/runs/{run['id']}/artifacts", "artifacts")
        summary = verify_receipts(artifacts, run, repository)
        return {
            "mode": "scan", "reason": "Recent exact-source full qualification verified",
            "source_sha": sha, "qualified_run_id": run["id"],
            "qualified_at": run["created_at"], "max_age_days": MAX_AGE.days,
            "inventory_sha256": summary["inventory_sha256"],
        }
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile):
        return {**fallback, "reason": "Qualification evidence unavailable or invalid"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = select(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_SHA"],
                    os.environ["GITHUB_EVENT_NAME"])
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(f"mode={result['mode']}\n")
    print(result["reason"])


if __name__ == "__main__":
    main()
