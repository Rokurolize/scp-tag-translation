"""README に記載した原典取得コマンドのセキュリティ契約を検証する。"""

import shlex
import shutil
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
README = ROOT / "README.md"
FETCH_URL = "https://scp-jp.wikidot.com/tag-list"
OUTPUT_NAME = "scp-jp-tag-list.html"


def _documented_curl_command() -> list[str]:
    readme = README.read_text(encoding="utf-8")
    start = readme.index("```bash\ncurl ", readme.index("## 辞書の更新方法"))
    end = readme.index("\n```", start)
    command = readme[start + len("```bash\n") : end].replace("\\\n", " ")
    return shlex.split(command)


def _option_value(command: list[str], option: str) -> str:
    return command[command.index(option) + 1]


def _probe_command(command: list[str], output: Path, url: str) -> list[str]:
    probe = command.copy()
    probe[probe.index("--output") + 1] = str(output)
    probe[probe.index(FETCH_URL)] = url
    return probe


def test_readme_fetch_command_has_bounded_https_only_contract():
    command = _documented_curl_command()

    assert command[0] == "curl"
    assert _option_value(command, "--proto") == "=https"
    assert _option_value(command, "--proto-redir") == "=https"
    assert "--location" in command
    assert _option_value(command, "--max-redirs") == "5"
    assert _option_value(command, "--connect-timeout") == "10"
    assert _option_value(command, "--max-time") == "60"
    assert "--fail" in command
    assert "--remove-on-error" in command
    assert _option_value(command, "--output") == OUTPUT_NAME
    assert command[-1] == FETCH_URL


@pytest.mark.skipif(shutil.which("curl") is None, reason="curl is required")
def test_documented_command_rejects_initial_http_url(tmp_path):
    output = tmp_path / "initial-http.txt"
    completed = subprocess.run(
        _probe_command(
            _documented_curl_command(),
            output,
            "http://127.0.0.1:9/source",
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert not output.exists()


class _DowngradeTargetHandler(BaseHTTPRequestHandler):
    requests = 0

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).requests += 1
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"downgraded")

    def log_message(self, _format, *args):
        pass


class _HttpsRedirectHandler(BaseHTTPRequestHandler):
    redirect_url = ""
    requests = 0

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).requests += 1
        self.send_response(302)
        self.send_header("Location", type(self).redirect_url)
        self.end_headers()

    def log_message(self, _format, *args):
        pass


def _serve(server: ThreadingHTTPServer):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


@pytest.mark.skipif(
    shutil.which("curl") is None or shutil.which("openssl") is None,
    reason="curl and openssl are required",
)
def test_documented_command_rejects_http_redirect(tmp_path):
    key = tmp_path / "key.pem"
    cert = tmp_path / "cert.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-subj",
            "/CN=localhost",
            "-days",
            "1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    _DowngradeTargetHandler.requests = 0
    downgrade_server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        _DowngradeTargetHandler,
    )
    downgrade_thread = _serve(downgrade_server)

    _HttpsRedirectHandler.requests = 0
    _HttpsRedirectHandler.redirect_url = (
        f"http://127.0.0.1:{downgrade_server.server_port}/source"
    )
    redirect_server = ThreadingHTTPServer(("127.0.0.1", 0), _HttpsRedirectHandler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    redirect_server.socket = tls.wrap_socket(redirect_server.socket, server_side=True)
    redirect_thread = _serve(redirect_server)

    output = tmp_path / "redirect-http.txt"
    command = _probe_command(
        _documented_curl_command(),
        output,
        f"https://127.0.0.1:{redirect_server.server_port}/source",
    )
    command[1:1] = ["--insecure", "--noproxy", "*"]

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        redirect_server.shutdown()
        downgrade_server.shutdown()
        redirect_thread.join(timeout=5)
        downgrade_thread.join(timeout=5)
        redirect_server.server_close()
        downgrade_server.server_close()

    assert completed.returncode != 0
    assert _HttpsRedirectHandler.requests == 1
    assert _DowngradeTargetHandler.requests == 0
    assert not output.exists()
