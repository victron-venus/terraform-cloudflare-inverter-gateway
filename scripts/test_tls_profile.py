"""Actual Terraform/provider TLS regression using isolated synthetic state and credentials.

Requires Linux and explicit TLS_TEST_* binary paths. No live backend is configured;
only the loopback HTTPS fixture is contacted. Both ordinary and strict clients are
calibrated so a missing binary or a malformed fixture cannot masquerade as rejection.
"""

import datetime
import http.server
import io
import json
import os
import pathlib
import shutil
import ssl
import subprocess
import tempfile
import threading
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

TF = pathlib.Path(os.environ["TLS_TEST_TERRAFORM"]).resolve()
PROV = pathlib.Path(os.environ["TLS_TEST_PROVIDER_DIR"]).resolve()
PLATFORM = os.environ["TLS_TEST_PLATFORM"]


def run(bits, strict, mode):
    with tempfile.TemporaryDirectory() as td:
        p = pathlib.Path(td)
        key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
        n = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(n)
            .issuer_name(n)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None), critical=True
            )
            .add_extension(
                x509.SubjectAlternativeName([x509.DNSName("localhost")]), False
            )
            .sign(key, hashes.SHA256())
        )
        (p / "ca.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        (p / "key.pem").write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append((self.path, self.headers.get("Authorization")))
                if self.path.startswith("/module.zip"):
                    z = io.BytesIO()
                    with zipfile.ZipFile(z, "w") as a:
                        a.writestr("main.tf", 'output "ok" { value = true }')
                    body = z.getvalue()
                    ctype = "application/zip"
                else:
                    body = json.dumps(
                        {
                            "success": True,
                            "errors": [],
                            "messages": [],
                            "result": {
                                "id": "0" * 32,
                                "name": "synthetic.invalid",
                                "status": "active",
                            },
                        }
                    ).encode()
                    ctype = "application/json"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
        ctx.load_cert_chain(p / "ca.pem", p / "key.pem")
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        root = p / "root"
        root.mkdir()
        port = srv.server_port
        (root / "main.tf").write_text(
            (
                'module "probe" { source = "https://localhost:'
                + str(port)
                + '/module.zip" }\n'
                if mode == "module"
                else ""
            )
            + 'terraform {\n required_providers {\n cloudflare = { source="registry.terraform.io/cloudflare/cloudflare", version="5.24.0" }\n }\n }\nprovider "cloudflare" {\n api_token="synthetic-test-token-00000000000000000000"\n base_url="https://localhost:'
            + str(port)
            + '/"\n }\ndata "cloudflare_zone" "probe" { zone_id="00000000000000000000000000000000" }\n'
        )
        mirror = (
            p / "mirror/registry.terraform.io/cloudflare/cloudflare/5.24.0" / PLATFORM
        )
        mirror.parent.mkdir(parents=True)
        shutil.copytree(PROV, mirror)
        (p / "config").write_text(
            'provider_installation {\n filesystem_mirror {\n path="'
            + str(p / "mirror")
            + '"\n }\n }'
        )
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(p),
            "TF_CLI_CONFIG_FILE": str(p / "config"),
            "SSL_CERT_FILE": str(p / "ca.pem"),
            "SSL_CERT_DIR": str(p / "empty-ca"),
            "CHECKPOINT_DISABLE": "1",
            "TF_IN_AUTOMATION": "1",
            "TF_INPUT": "0",
        }
        if strict:
            env["GODEBUG"] = "fips140=on"
        ini = subprocess.run(
            [str(TF), "init", "-backend=false", "-input=false", "-no-color"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        plan = None
        if not ini.returncode:
            plan = subprocess.run(
                [str(TF), "plan", "-input=false", "-no-color"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
        srv.shutdown()
        thread.join()
        rejected = strict and bits < 2048
        if rejected:
            result = ini if mode == "module" else plan
            assert result is not None and result.returncode != 0, (
                "Weak key was not rejected"
            )
            assert "no FIPS compatible certificate chains" in result.stderr, (
                result.stderr
            )
            assert not requests, "Application bytes reached weak peer"
        else:
            assert ini.returncode == 0, ini.stderr
            assert plan is not None and plan.returncode == 0, (
                plan.stderr if plan else "No plan"
            )
            assert requests and any(
                auth == "Bearer synthetic-test-token-00000000000000000000"
                for _, auth in requests
            )
        print(
            f"{mode}: RSA-{bits}, strict={strict}: expected result, {len(requests)} requests"
        )


if __name__ == "__main__":
    if not __import__("sys").platform.startswith("linux"):
        raise SystemExit("This certificate-store fixture requires Linux")
    for mode in ("module", "provider"):
        for bits in (2048, 2047):
            for strict in (False, True):
                run(bits, strict, mode)
