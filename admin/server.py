#!/usr/bin/env python3
import json
import os
import http.client
import re
import shutil
import socket
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml


ROOT = Path(__file__).resolve().parent.parent
HOST_ROOT = Path(os.environ.get("OCES_HOST_ROOT", str(ROOT)))
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DOCKER_SOCKET = "/var/run/docker.sock"
CREATE_LOCK = threading.Lock()
INSTANCE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
REQUEST_ID_RE = re.compile(r"^[a-f0-9-]{32,40}$", re.IGNORECASE)
OPENAI_KEY_RE = re.compile(r"^sk-[A-Za-z0-9_-]{20,}$")
OPENAI_MODELS = {
    "openai/gpt-5.5",
    "openai/gpt-5.5-mini",
    "openai/gpt-5.5-nano",
    "openai/gpt-5.4",
    "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano",
    "openai/gpt-5",
    "openai/gpt-5-mini",
    "openai/gpt-5-nano",
    "openai/chat-latest",
}


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_request(method, path, payload=None, timeout=30):
    if not os.path.exists(DOCKER_SOCKET):
        raise RuntimeError("docker socket unavailable")

    conn = UnixHTTPConnection(DOCKER_SOCKET, timeout=timeout)
    body = None
    headers = {"Host": "docker"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise RuntimeError(body.strip() or f"Docker API HTTP {response.status}")
        return response.status, body
    finally:
        conn.close()


def docker_json(method, path, payload=None, timeout=30):
    status, body = docker_request(method, path, payload=payload, timeout=timeout)
    if not body:
        return {}
    return json.loads(body)


def docker_demux(data):
    raw = data.encode("latin1", errors="ignore")
    output = bytearray()
    index = 0
    while index + 8 <= len(raw):
        size = int.from_bytes(raw[index + 4:index + 8], "big")
        index += 8
        if size < 0 or index + size > len(raw):
            break
        output.extend(raw[index:index + size])
        index += size
    if output:
        return output.decode("utf-8", errors="replace")
    return data


def docker_exec(container, cmd, timeout=30):
    created = docker_json(
        "POST",
        f"/containers/{container}/exec",
        payload={
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "Cmd": cmd,
        },
        timeout=timeout,
    )
    exec_id = created["Id"]
    _, body = docker_request(
        "POST",
        f"/exec/{exec_id}/start",
        payload={"Detach": False, "Tty": False},
        timeout=timeout,
    )
    inspect = docker_json("GET", f"/exec/{exec_id}/json", timeout=timeout)
    output = docker_demux(body).strip()
    if inspect.get("ExitCode") not in (0, None):
        raise RuntimeError(output or f"exec failed in {container}")
    return output


def known_instances():
    return set(load_stack()["instances"].keys())


def load_stack():
    stack = yaml.safe_load((ROOT / "config" / "stack.yml").read_text(encoding="utf-8"))
    if not isinstance(stack, dict) or not isinstance(stack.get("instances"), dict):
        raise ValueError("config/stack.yml invalido")
    return stack


def load_defaults():
    defaults = yaml.safe_load((ROOT / "config" / "defaults.yml").read_text(encoding="utf-8"))
    if not isinstance(defaults, dict):
        raise ValueError("config/defaults.yml invalido")
    return defaults


def append_instance_to_stack(name, domain, port):
    stack_path = ROOT / "config" / "stack.yml"
    raw = stack_path.read_text(encoding="utf-8")
    in_instances = False
    insert_at = None
    lines = raw.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        if line == "instances:":
            in_instances = True
            continue
        if not in_instances:
            continue
        if not line.startswith(" "):
            insert_at = index
            break

    block = [
        "",
        f"  {name}:",
        f"    domain: {domain}",
        f"    port: {port}",
    ]
    if insert_at is None:
        new_lines = lines + block
    else:
        new_lines = lines[:insert_at] + block + lines[insert_at:]
    stack_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def read_env(path):
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def write_env_value(path, key, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated = False
    next_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)
    if not updated:
        next_lines.append(f"{key}={value}")
    path.write_text("\n".join(next_lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def validate_instance_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    name = str(payload.get("name", "")).strip().lower()
    domain = str(payload.get("domain", "")).strip().lower()
    port = payload.get("port")

    if not INSTANCE_NAME_RE.match(name):
        raise ValueError("nome deve usar 2 a 32 caracteres: letras minusculas, numeros e hifen")
    if not DOMAIN_RE.match(domain):
        raise ValueError("dominio invalido")
    try:
        port = int(port)
    except (TypeError, ValueError):
        raise ValueError("porta precisa ser numerica")
    if port < 1024 or port > 65535:
        raise ValueError("porta precisa estar entre 1024 e 65535")

    stack = load_stack()
    if name in stack["instances"]:
        raise ValueError("instancia ja existe")
    for existing_name, cfg in stack["instances"].items():
        if cfg.get("domain") == domain:
            raise ValueError(f"dominio ja usado por {existing_name}")
        if int(cfg.get("port", 0)) == port:
            raise ValueError(f"porta ja usada por {existing_name}")

    return name, domain, port


def run_generate():
    result = subprocess.run(
        ["python3", str(ROOT / "scripts" / "generate.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout


def wait_container(container_id, timeout=45):
    return docker_json("POST", f"/containers/{container_id}/wait", timeout=timeout)


def chown_instance_data(name):
    data_dir = HOST_ROOT / "instances" / name / "data"
    payload = {
        "Image": "openclaw:latest",
        "Cmd": ["-R", "node:node", "/data"],
        "Entrypoint": ["chown"],
        "User": "root",
        "HostConfig": {
            "AutoRemove": False,
            "Binds": [f"{data_dir}:/data"],
        },
    }
    created = docker_json("POST", "/containers/create", payload=payload, timeout=30)
    container_id = created["Id"]
    try:
        docker_request("POST", f"/containers/{container_id}/start", timeout=30)
        result = wait_container(container_id)
        if result.get("StatusCode") != 0:
            raise RuntimeError("falha ao ajustar permissoes da instancia")
    finally:
        try:
            docker_request("DELETE", f"/containers/{container_id}?force=true", timeout=15)
        except Exception:
            pass


def create_openclaw_container(name, domain, port):
    defaults = load_defaults()
    network = load_stack().get("proxy", {}).get("network", defaults["network"])
    gateway_port = str(defaults["gateway_port"])
    env_file = read_env(ROOT / "instances" / name / ".env")
    host_instance_dir = HOST_ROOT / "instances" / name
    openclaw_dir = host_instance_dir / "data" / ".openclaw"
    workspace_dir = host_instance_dir / "data" / "workspace"
    auth_dir = host_instance_dir / "data" / "auth"

    env = {
        **env_file,
        "HOME": "/home/node",
        "OPENCLAW_HOME": "/home/node",
        "TERM": "xterm-256color",
        "OPENCLAW_STATE_DIR": "/home/node/.openclaw",
        "OPENCLAW_CONFIG_PATH": "/home/node/.openclaw/openclaw.json",
        "OPENCLAW_CONFIG_DIR": "/home/node/.openclaw",
        "OPENCLAW_WORKSPACE_DIR": "/home/node/.openclaw/workspace",
        "OPENCLAW_GATEWAY_TOKEN": env_file.get("OPENCLAW_GATEWAY_TOKEN", ""),
        "OPENCLAW_ALLOW_INSECURE_PRIVATE_WS": env_file.get("OPENCLAW_ALLOW_INSECURE_PRIVATE_WS", ""),
        "TZ": env_file.get("OPENCLAW_TZ", "UTC"),
    }

    payload = {
        "Image": env_file.get("OPENCLAW_IMAGE") or defaults["image"],
        "Cmd": ["node", "dist/index.js", "gateway", "--bind", env_file.get("OPENCLAW_GATEWAY_BIND", "lan"), "--port", gateway_port],
        "Env": [f"{key}={value}" for key, value in env.items()],
        "Labels": {
            "traefik.enable": "true",
            "traefik.docker.network": network,
            f"traefik.http.routers.{name}.rule": f"Host(`{domain}`)",
            f"traefik.http.routers.{name}.entrypoints": "websecure",
            f"traefik.http.routers.{name}.tls.certresolver": "letsencrypt",
            f"traefik.http.routers.{name}.middlewares": "security@file,gzip@file",
            f"traefik.http.services.{name}.loadbalancer.server.port": gateway_port,
        },
        "ExposedPorts": {f"{gateway_port}/tcp": {}},
        "Healthcheck": {
            "Test": [
                "CMD",
                "node",
                "-e",
                f"fetch('http://127.0.0.1:{gateway_port}/healthz').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))",
            ],
            "Interval": 30000000000,
            "Timeout": 5000000000,
            "Retries": 5,
            "StartPeriod": 20000000000,
        },
        "HostConfig": {
            "Init": True,
            "RestartPolicy": {"Name": defaults.get("restart", "unless-stopped")},
            "SecurityOpt": ["no-new-privileges:true"],
            "CapDrop": ["NET_ADMIN", "NET_RAW"],
            "ExtraHosts": ["host.docker.internal:host-gateway"],
            "NetworkMode": network,
            "Binds": [
                f"{openclaw_dir}:/home/node/.openclaw",
                f"{workspace_dir}:/home/node/.openclaw/workspace",
                f"{auth_dir}:/home/node/.config/openclaw",
            ],
            "PortBindings": {f"{gateway_port}/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]},
        },
        "NetworkingConfig": {"EndpointsConfig": {network: {}}},
    }

    docker_json("GET", f"/images/{payload['Image']}/json", timeout=30)
    try:
        docker_json("GET", f"/containers/oces-{name}/json", timeout=15)
        raise RuntimeError("container ja existe")
    except RuntimeError as exc:
        if "No such container" not in str(exc) and "404" not in str(exc):
            raise

    created = docker_json("POST", f"/containers/create?name=oces-{name}", payload=payload, timeout=30)
    try:
        docker_request("POST", f"/containers/{created['Id']}/start", timeout=30)
    except Exception:
        try:
            docker_request("DELETE", f"/containers/{created['Id']}?force=true", timeout=15)
        except Exception:
            pass
        raise
    return created["Id"]


def remove_openclaw_container(name):
    try:
        docker_json("GET", f"/containers/oces-{name}/json", timeout=15)
    except RuntimeError as exc:
        if "No such container" in str(exc) or "404" in str(exc):
            return
        raise
    docker_request("DELETE", f"/containers/oces-{name}?force=true", timeout=45)


def recreate_openclaw_container(name):
    stack = load_stack()
    cfg = stack["instances"].get(name)
    if not cfg:
        raise ValueError("unknown instance")
    chown_instance_data(name)
    remove_openclaw_container(name)
    container_id = create_openclaw_container(name, cfg["domain"], int(cfg["port"]))
    return container_id


def create_instance(payload):
    with CREATE_LOCK:
        name, domain, port = validate_instance_payload(payload)
        stack_path = ROOT / "config" / "stack.yml"
        previous_stack = stack_path.read_text(encoding="utf-8")
        try:
            append_instance_to_stack(name, domain, port)
            generate_output = run_generate()
            chown_instance_data(name)
            container_id = create_openclaw_container(name, domain, port)
        except Exception:
            stack_path.write_text(previous_stack, encoding="utf-8", newline="\n")
            instance_dir = ROOT / "instances" / name
            if instance_dir.exists() and instance_dir.is_dir() and instance_dir.parent == ROOT / "instances":
                shutil.rmtree(instance_dir)
            try:
                run_generate()
            except Exception:
                pass
            raise
        return {
            "ok": True,
            "instance": {"name": name, "domain": domain, "port": port},
            "containerId": container_id,
            "generate": generate_output,
        }


def configure_openai_key(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    api_key = str(payload.get("apiKey", "")).strip()
    if not OPENAI_KEY_RE.match(api_key):
        raise ValueError("API key da OpenAI invalida")

    with CREATE_LOCK:
        env_path = ROOT / "instances" / instance / ".env"
        write_env_value(env_path, "OPENAI_API_KEY", api_key)
        container_id = recreate_openclaw_container(instance)
    return {"ok": True, "instance": instance, "action": "openai-key", "containerId": container_id}


def configure_default_model(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    model = str(payload.get("model", "")).strip()
    if model not in OPENAI_MODELS:
        raise ValueError("modelo nao permitido")

    output = docker_exec(
        f"oces-{instance}",
        ["node", "dist/index.js", "models", "set", model],
        timeout=60,
    )
    docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)
    return {"ok": True, "instance": instance, "action": "model", "model": model, "output": output}


def start_openai_oauth(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    script = r'''
set -eu
dir=/tmp/oces-openai-oauth
mkdir -p "$dir"
if [ -s "$dir/pid" ] && kill -0 "$(cat "$dir/pid")" 2>/dev/null; then
  printf '{"started":false,"running":true,"pid":%s}\n' "$(cat "$dir/pid")"
  exit 0
fi
rm -f "$dir/log" "$dir/exit" "$dir/pid"
(
  node dist/index.js models auth login --provider openai --device-code
  code=$?
  echo "$code" > "$dir/exit"
  exit "$code"
) > "$dir/log" 2>&1 &
pid=$!
echo "$pid" > "$dir/pid"
printf '{"started":true,"running":true,"pid":%s}\n' "$pid"
'''
    output = docker_exec(f"oces-{instance}", ["sh", "-lc", script], timeout=15)
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        data = {"started": True, "running": True, "output": output}
    data.update({"ok": True, "instance": instance, "action": "openai-oauth-start"})
    return data


def openai_oauth_status(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    script = r'''
const fs = require("node:fs");
const { spawnSync } = require("node:child_process");
const dir = "/tmp/oces-openai-oauth";
const read = (name) => {
  try { return fs.readFileSync(`${dir}/${name}`, "utf8").trim(); }
  catch { return ""; }
};
const pid = read("pid");
let running = false;
if (pid) {
  const probe = spawnSync("kill", ["-0", pid], { stdio: "ignore" });
  running = probe.status === 0;
}
const exitRaw = read("exit");
const exitCode = exitRaw ? Number(exitRaw) : null;
let log = read("log");
log = log
  .replace(/sk-[A-Za-z0-9_-]+/g, "sk-***")
  .replace(/(access_token|refresh_token)["'=:\s]+[A-Za-z0-9._-]+/gi, "$1=***");
const links = [...new Set(log.match(/https?:\/\/[^\s)]+/g) || [])].slice(0, 6);
console.log(JSON.stringify({ running, pid: pid || null, exitCode, log, links }));
'''
    output = docker_exec(f"oces-{instance}", ["node", "-e", script], timeout=15)
    data = json.loads(output or "{}")
    data.update({"ok": True, "instance": instance, "action": "openai-oauth-status"})
    return data


def pending_device_requests():
    script = r'''
const fs = require("node:fs");
const path = "/home/node/.openclaw/devices/pending.json";
const rows = [];
if (fs.existsSync(path)) {
  const pending = JSON.parse(fs.readFileSync(path, "utf8"));
  const now = Date.now();
  for (const request of Object.values(pending)) {
    if (!request || now - request.ts > 5 * 60 * 1000) continue;
    if (!["openclaw-control-ui", "webchat-ui"].includes(request.clientId)) continue;
    rows.push({
      requestId: request.requestId,
      clientId: request.clientId || "",
      remoteIp: request.remoteIp || "",
      scopes: Array.isArray(request.scopes) ? request.scopes : [],
      ageSeconds: Math.max(0, Math.round((now - request.ts) / 1000)),
    });
  }
}
console.log(JSON.stringify(rows));
'''
    rows = []
    for instance in sorted(known_instances()):
        container = f"oces-{instance}"
        try:
            output = docker_exec(container, ["node", "-e", script], timeout=20)
            pending = json.loads(output or "[]")
        except Exception as exc:
            rows.append({"instance": instance, "error": str(exc), "requests": []})
            continue
        rows.append({"instance": instance, "requests": pending})
    return rows


def approve_device_request(instance, request_id):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not REQUEST_ID_RE.match(request_id):
        raise ValueError("request id invalido")
    output = docker_exec(
        f"oces-{instance}",
        ["node", "dist/index.js", "devices", "approve", request_id],
        timeout=45,
    )
    return {"ok": True, "instance": instance, "requestId": request_id, "output": output}


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

        if self.command == "GET" and parsed.path == "/api/devices/pending":
            try:
                self.write_json({"ok": True, "items": pending_device_requests()})
            except Exception as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=500)
            return

        if self.command == "POST" and parsed.path == "/api/devices/approve":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                approved = approve_device_request(
                    str(payload.get("instance", "")).strip(),
                    str(payload.get("requestId", "")).strip(),
                )
            except ValueError as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=400)
                return
            except Exception as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=500)
                return
            self.write_json(approved)
            return

        if self.command == "POST" and parsed.path == "/api/instances":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                created = create_instance(payload)
            except ValueError as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=400)
                return
            except Exception as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=500)
                return
            self.write_json(created, status=201)
            return

        if parsed.path.startswith("/api/instances/"):
            parts = [part for part in parsed.path.split("/") if part]
            if (
                len(parts) == 6
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "oauth"
                and parts[4] == "openai"
                and parts[5] == "status"
                and self.command == "GET"
            ):
                try:
                    status = openai_oauth_status(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(status)
                return

            if (
                len(parts) == 6
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "oauth"
                and parts[4] == "openai"
                and parts[5] == "start"
                and self.command == "POST"
            ):
                try:
                    started = start_openai_oauth(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(started)
                return

        if self.command == "POST" and parsed.path.startswith("/api/instances/"):
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "restart":
                instance = unquote(parts[2])
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

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "openai-key":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    configured = configure_openai_key(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(configured)
                return

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "model":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    configured = configure_default_model(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(configured)
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
