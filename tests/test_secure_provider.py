"""Security boundaries of the opt-in provider build, without network access."""

import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "secure_provider", Path(__file__).parents[1] / "scripts/build_secure_provider.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecureProviderBuildTests(unittest.TestCase):
    def test_real_go_filter_preserves_account_and_access_unit_tests(self):
        go = shutil.which("go")
        if not go:
            self.skipTest("Go is required for the actual provider test-filter regression")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "go.mod").write_text("module filterfixture\n\ngo 1.23\n")
            fixture = [
                'package filterfixture',
                'import ("os"; "testing")',
            ]
            names = ["TestAccount", "TestAccess", "TestAccidental"]
            for name in names:
                fixture.append(
                    f'func {name}(t *testing.T) {{ '
                    f'if err := os.WriteFile("{name}", []byte("ran"), 0600); '
                    'err != nil { t.Fatal(err) } }'
                )
            for name in ["TestAcc", "TestAccCloudflare", "TestAcc_Basic"]:
                fixture.append(f'func {name}(t *testing.T) {{ t.Fatal("acceptance selected") }}')
            (root / "filter_test.go").write_text("\n".join(fixture) + "\n")
            environment = {
                **os.environ, "GOWORK": "off", "GOENV": "off",
                "GOTOOLCHAIN": "local", "CGO_ENABLED": "0", "GOMAXPROCS": "2",
            }
            result = subprocess.run(
                MODULE.unit_test_command(go), cwd=root, env=environment,
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in names:
                self.assertEqual((root / name).read_text(), "ran")

    def test_stage_output_is_retained_and_failure_still_propagates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with self.assertRaises(subprocess.CalledProcessError):
                    MODULE.run(
                        [sys.executable, "-c", "print('fixture diagnostic'); raise SystemExit(7)"],
                        root, dict(os.environ), root / "stage.log", timeout=5,
                    )
            self.assertEqual((root / "stage.log").read_text(), "fixture diagnostic\n")
            self.assertIn("fixture diagnostic", output.getvalue())

    def test_timeout_stops_child_even_if_driver_exits_on_term(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "heartbeat"
            child = (
                "import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                f"p=pathlib.Path({str(marker)!r}); "
                "exec('while True:\\n p.write_text(str(time.monotonic()))\\n time.sleep(0.02)')"
            )
            driver = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(60)"
            )
            with self.assertRaisesRegex(SystemExit, "Build stage exceeded"):
                MODULE.run(
                    [sys.executable, "-c", driver], root, dict(os.environ),
                    root / "stage.log", timeout=1,
                )
            self.assertTrue(marker.exists(), "Synthetic child must run before timeout")
            stopped = marker.read_text()
            time.sleep(0.1)
            self.assertEqual(marker.read_text(), stopped)

    def test_archive_cannot_escape_or_create_links(self):
        for name, kind in [
            ("../escape", tarfile.REGTYPE),
            ("/escape", tarfile.REGTYPE),
            ("source/link", tarfile.SYMTYPE),
            ("source/link", tarfile.LNKTYPE),
        ]:
            with (
                self.subTest(name=name, kind=kind),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                archive = root / "source.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    entry = tarfile.TarInfo(name)
                    entry.type = kind
                    entry.linkname = "/outside"
                    bundle.addfile(entry)
                with self.assertRaises(ValueError):
                    MODULE.extract_source(archive, root / "extracted")
                self.assertFalse((root / "extracted").exists())

    def test_regular_source_archive_is_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "source.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                content = b"synthetic source"
                entry = tarfile.TarInfo("source/main.go")
                entry.size = len(content)
                bundle.addfile(entry, io.BytesIO(content))
            MODULE.extract_source(archive, root / "extracted")
            self.assertEqual((root / "extracted/source/main.go").read_bytes(), content)

    def test_build_cannot_inherit_operator_credentials_or_compiler_overrides(self):
        private = {
            "CLOUDFLARE_API_TOKEN": "private",
            "AWS_ACCESS_KEY_ID": "private",
            "TF_CLI_CONFIG_FILE": "/private/config",
            "TF_REATTACH_PROVIDERS": "private",
            "GOPRIVATE": "*",
            "GOINSECURE": "*",
            "GOFLAGS": "-modfile=/private/go.mod",
            "GOROOT": "/unverified/compiler",
        }
        with patch.dict(os.environ, private):
            environment = MODULE.clean_environment(
                Path("/temporary"), Path("/verified/bin/go")
            )
        self.assertFalse(set(private) & set(environment))
        self.assertEqual(environment["GOTOOLCHAIN"], "local")
        self.assertEqual(environment["GODEBUG"], "fips140=on")
        self.assertEqual(environment["GOENV"], "off")
        self.assertEqual(environment["GOSUMDB"], "sum.golang.org")
        self.assertEqual(environment["PATH"].split(os.pathsep)[0], "/verified/bin")


if __name__ == "__main__":
    unittest.main()
