#!/usr/bin/env python3
import json
import os
import http.client
import socket
import subprocess
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DOCKER_SOCKET = "/var/run/docker.sock"


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_request(method, path, timeout=30):
    if not os.path.exists(DOCKER_SOCKET):
        raise RuntimeError("docker socket unavailable")

    conn = UnixHTTPConnection(DOCKER_SOCKET, timeout=timeout)
    try:
        conn.request(method, path, headers={"Host": "docker"})
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(body.strip() or f"Docker API HTTP {response.status}")
        return response.status, body
    finally:
        conn.close()


def known_instances():
    stack_path = ROOT / "config" / "stack.yml"
    names = []
    in_instances = False
    for raw_line in stack_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line == "instances:":
            in_instances = True
            continue
        if not in_instances or not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.strip().endswith(":"):
            names.append(line.strip()[:-1])
    return set(names)


class AdminHandler(SimpleHTTPRequestHandler):
    server_version = "OCESAdmin/1.0"

    def translate_path(self, path):
        parsed = urlparse(path)
        if parsed.path == "/":
            return str(STATIC_ROOT / "index.html")
        return str(STATIC_ROOT / parsed.path.lstrip("/"))

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api(parsed)
            return
        if parsed.path == "/healthz":
            self.write_json({"ok": True})
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self.handle_api(parsed)
            return
        self.write_json({"ok": False, "error": "not found"}, status=404)

    def handle_api(self, parsed):
        if not self.authorized():
            self.request_auth()
            return

        if parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            args = ["python3", str(ROOT / "scripts" / "status.py"), "--json"]
            for instance in query.get("instance", []):
                args.extend(["--instance", instance])
            result = subprocess.run(
                args,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=90,
                check=False,
            )
            if result.returncode != 0:
                self.write_json(
                    {"ok": False, "error": (result.stderr or result.stdout).strip()},
                    status=500,
                )
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(result.stdout.encode("utf-8"))
            return

        if self.command == "POST" and parsed.path.startswith("/api/instances/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "restart":
                instance = parts[2]
                if instance not in known_instances():
                    self.write_json({"ok": False, "error": "unknown instance"}, status=404)
                    return
                try:
                    docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json({"ok": True, "action": "restart", "instance": instance})
                return

        self.write_json({"ok": False, "error": "not found"}, status=404)

    def authorized(self):
        token = os.environ.get("OCES_ADMIN_TOKEN", "")
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        return header == f"Bearer {token}"

    def request_auth(self):
        self.write_json(
            {"ok": False, "error": "unauthorized"},
            status=401,
            extra_headers={"WWW-Authenticate": "Bearer"},
        )

    def write_json(self, payload, status=200, extra_headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)


def main():
    host = os.environ.get("OCES_ADMIN_HOST", "0.0.0.0")
    port = int(os.environ.get("OCES_ADMIN_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), AdminHandler)
    print(f"OCES admin listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
