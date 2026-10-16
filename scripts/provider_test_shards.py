"""Partition and reconcile the complete pinned provider Go package inventory."""

import hashlib
import json
import re


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def checked_inventory(packages):
    """Reject ambiguous or option-like package names before invoking Go."""
    if (
        not packages
        or packages != sorted(set(packages))
        or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", p) for p in packages)
        or any(".." in p for p in packages)
    ):
        raise ValueError("Expected a nonempty sorted unique Go package inventory")
    return packages


def partition(packages, index, count):
    checked_inventory(packages)
    if not 1 <= count <= len(packages) or not 0 <= index < count:
        raise ValueError("Invalid or empty provider test shard")
    # Root/migration packages are adjacent alphabetically and have very different
    # link costs. Stable hash ordering avoids systematically grouping that shape.
    ordered = sorted(
        packages, key=lambda package: hashlib.sha256(package.encode()).hexdigest()
    )
    return sorted(ordered[index::count])


def completed_packages(log):
    """Go prints one final result for each explicitly selected package."""
    results = []
    for line in log.splitlines():
        match = re.match(r"^(?:ok|\?)\s+(\S+)\s+", line)
        if match:
            results.append(match.group(1))
    return results


def write_receipt(directory, context, packages, index, count, log):
    selected = partition(packages, index, count)
    text = log.read_text()
    if sorted(completed_packages(text)) != selected:
        raise ValueError("Successful Go output does not cover every shard package")
    receipt_log = directory / f"shard-{index}.log"
    receipt_log.write_bytes(log.read_bytes())
    receipt = {
        "schema": 1,
        "context": context,
        "inventory": packages,
        "inventory_sha256": fingerprint(packages),
        "index": index,
        "count": count,
        "packages": selected,
        "result": "success",
        "log_sha256": hashlib.sha256(receipt_log.read_bytes()).hexdigest(),
    }
    (directory / f"shard-{index}.json").write_text(json.dumps(receipt, indent=2) + "\n")


def reconcile(directory, context, packages, count):
    """Require every shard, exact inputs, successful logs and a complete union."""
    checked_inventory(packages)
    partition(packages, 0, count)
    expected = {f"shard-{i}.json" for i in range(count)}
    if {p.name for p in directory.glob("shard-*.json")} != expected:
        raise ValueError("Missing or unexpected provider shard receipts")
    union = []
    accepted = []
    for index in range(count):
        path = directory / f"shard-{index}.json"
        receipt = json.loads(path.read_text())
        selected = partition(packages, index, count)
        if any(
            (
                receipt.get("schema") != 1,
                receipt.get("context") != context,
                receipt.get("inventory") != packages,
                receipt.get("inventory_sha256") != fingerprint(packages),
                receipt.get("index") != index,
                receipt.get("count") != count,
                receipt.get("packages") != selected,
                receipt.get("result") != "success",
            )
        ):
            raise ValueError(
                f"Provider shard {index} has mismatched or unsuccessful inputs"
            )
        log = directory / f"shard-{index}.log"
        if (
            hashlib.sha256(log.read_bytes()).hexdigest() != receipt.get("log_sha256")
            or sorted(completed_packages(log.read_text())) != selected
        ):
            raise ValueError(f"Provider shard {index} log is incomplete or altered")
        union.extend(selected)
        accepted.append(
            {
                "index": index,
                "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "log_sha256": receipt["log_sha256"],
            }
        )
    if sorted(union) != packages or len(union) != len(set(union)):
        raise ValueError(
            "Provider shards do not cover the complete inventory exactly once"
        )
    return {
        "inventory_sha256": fingerprint(packages),
        "packages": len(packages),
        "shards": accepted,
    }
