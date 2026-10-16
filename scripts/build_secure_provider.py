#!/usr/bin/env python3
"""Build a disclosed provider patch; never install it, mutate locks or run Terraform."""

import argparse
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def digest(path):
    """Return the integrity digest for a local artifact."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_context():
    """Require a verified TLS chain with the strict OpenSSL 3 key policy."""
    if ssl.OPENSSL_VERSION_INFO[0] < 3:
        raise RuntimeError("Source downloads require OpenSSL 3 or newer")
    context = ssl.create_default_context()
    context.minimum_version = max(context.minimum_version, ssl.TLSVersion.TLSv1_2)
    level = max(3, context.security_level)
    ciphers = ":".join(
        item["name"] for item in context.get_ciphers() if item["protocol"] != "TLSv1.3"
    )
    context.set_ciphers(f"{ciphers}:@SECLEVEL={level}")
    if context.security_level < 3:
        raise RuntimeError("Unable to enforce the strict certificate key policy")
    return context


def validate_source_url(url):
    """Keep the unauthenticated pinned archive request on verified GitHub HTTPS."""
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"github.com", "codeload.github.com"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Source downloads and redirects must use GitHub HTTPS")


class HTTPSOnlyRedirect(urllib.request.HTTPRedirectHandler):
    """Reject downgrade and off-origin redirects before a new request is sent."""

    def redirect_request(self, request, fp, code, msg, headers, newurl):
        validate_source_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def download_source(url, destination):
    """Use the same strict policy for the original request and every redirect."""
    validate_source_url(url)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=source_context()), HTTPSOnlyRedirect()
    )
    with opener.open(url, timeout=60) as response:
        destination.write_bytes(response.read())


def extract_source(archive, destination):
    """Accept only regular files/directories below the extraction root."""
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Source archive escapes extraction root")
            if not (member.isfile() or member.isdir()):
                raise ValueError("Source archive contains links or special files")
        bundle.extractall(destination, filter="data")


def clean_environment(root, go):
    """Exclude cloud credentials, operator Go configuration and Terraform options."""
    return {
        "PATH": str(go.parent) + os.pathsep + os.environ.get("PATH", ""),
        "HOME": str(root),
        "TMPDIR": str(root / "tmp"),
        "GOTOOLCHAIN": "local",
        "GOENV": "off",
        "GOPROXY": "https://proxy.golang.org",
        "GOSUMDB": "sum.golang.org",
        "GOPATH": str(root / "gopath"),
        "GOCACHE": str(root / "cache"),
        "GOBIN": str(root / "bin"),
        "CGO_ENABLED": "0",
        "GOTELEMETRY": "off",
        "GOMAXPROCS": "2",
        "GODEBUG": "fips140=on",
    }


def run(command, source, environment, log):
    """Retain the complete result and stop on a failed qualification stage."""
    print("Running:", " ".join(map(str, command)), flush=True)
    with log.open("w", encoding="utf-8") as stream:
        subprocess.run(
            list(map(str, command)),
            cwd=source,
            env=environment,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=True,
        )


def main():
    """Build and qualify a pinned, explicitly labelled derivative provider."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--go", required=True, type=Path, help="Verified Go 1.27.2 executable"
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="New artifact directory"
    )
    parser.add_argument(
        "--platform",
        choices=("linux_amd64", "linux_arm64", "darwin_amd64", "darwin_arm64"),
        required=True,
    )
    args = parser.parse_args()
    go = args.go.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(
            "Output must be a new directory; existing artifacts are never overwritten"
        )
    pinned = Path(__file__).resolve().parents[1] / "security/provider"
    manifest = json.loads((pinned / "manifest.json").read_text())
    for name, expected in manifest["module_files"].items():
        if digest(pinned / name) != expected:
            raise SystemExit(f"Pinned module-file checksum mismatch: {name}")
    with tempfile.TemporaryDirectory(prefix="secure-provider-") as temporary:
        temporary = Path(temporary)
        (temporary / "tmp").mkdir()
        environment = clean_environment(temporary, go)
        actual = subprocess.check_output(
            [str(go), "env", "GOVERSION"], cwd=temporary, env=environment, text=True
        ).strip()
        if actual != manifest["go_version"]:
            raise SystemExit(
                f"Expected {manifest['go_version']}, found {actual}; do not infer compiler version from GOTOOLCHAIN"
            )
        output.mkdir(parents=True)
        archive = temporary / "source.tar.gz"
        download_source(manifest["source_url"], archive)
        if digest(archive) != manifest["source_sha256"]:
            raise SystemExit("Upstream source checksum mismatch")
        extract_source(archive, temporary)
        source = temporary / manifest["source_root"]
        for name in manifest["module_files"]:
            shutil.copyfile(pinned / name, source / name)
            shutil.copyfile(pinned / name, output / name)
        shutil.copyfile(source / "LICENSE", output / "UPSTREAM-LICENSE")
        run([go, "mod", "download"], source, environment, output / "download.log")
        run([go, "mod", "verify"], source, environment, output / "modules.log")
        run(
            [
                go,
                "install",
                "golang.org/x/vuln/cmd/govulncheck@" + manifest["govulncheck_version"],
            ],
            source,
            environment,
            output / "scanner-install.log",
        )
        run(
            [temporary / "bin/govulncheck", "-show", "traces", "."],
            source,
            environment,
            output / "source-vulnerabilities.log",
        )
        run(
            [go, "test", "-p", "2", "-short", "-skip", "^TestAcc", "./..."],
            source,
            environment,
            output / "unit-tests.log",
        )
        binary = output / manifest["binary_name"]
        platform_os, platform_arch = args.platform.split("_")
        target_environment = {
            **environment,
            "GOOS": platform_os,
            "GOARCH": platform_arch,
        }
        run(
            [
                go,
                "build",
                "-p",
                "2",
                "-mod=readonly",
                "-trimpath",
                "-buildvcs=false",
                "-ldflags=-s -w -X main.version=" + manifest["build_version"],
                "-o",
                binary,
                ".",
            ],
            source,
            target_environment,
            output / "build.log",
        )
        run(
            [go, "version", "-m", binary],
            source,
            environment,
            output / "binary-metadata.log",
        )
        metadata = (output / "binary-metadata.log").read_text()
        if manifest["go_version"] not in metadata.splitlines()[0]:
            raise SystemExit("Built executable does not report the qualified compiler")
        for name, expected in manifest["module_files"].items():
            if digest(source / name) != expected:
                raise SystemExit(
                    f"Build unexpectedly changed pinned dependencies: {name}"
                )
        provenance = {
            **manifest,
            "platform": args.platform,
            "actual_go_version": actual,
            "binary_sha256": digest(binary),
            "qualification": "source scan and non-acceptance unit tests passed; transport calibration still required",
        }
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        f"Built disclosed derivative in {output}; not installed. Run the real TLS tests before use."
    )


if __name__ == "__main__":
    main()
