"""Security boundaries of the opt-in provider build, without network access."""

import importlib.util
import io
import os
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "secure_provider", Path(__file__).parents[1] / "scripts/build_secure_provider.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SecureProviderBuildTests(unittest.TestCase):
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
        self.assertEqual(environment["GOENV"], "off")
        self.assertEqual(environment["GOSUMDB"], "sum.golang.org")
        self.assertEqual(environment["PATH"].split(os.pathsep)[0], "/verified/bin")


if __name__ == "__main__":
    unittest.main()
