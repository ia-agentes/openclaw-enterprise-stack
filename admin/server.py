#!/usr/bin/env python3
import json
import os
import hmac
import http.client
import posixpath
import re
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import yaml


ROOT = Path(__file__).resolve().parent.parent
HOST_ROOT = Path(os.environ.get("OCES_HOST_ROOT", str(ROOT)))
STATIC_ROOT = Path(__file__).resolve().parent / "static"
DOCKER_SOCKET = "/var/run/docker.sock"
CREATE_LOCK = threading.Lock()
UPDATE_LOCK = threading.Lock()
UPDATE_JOB = {
    "running": False,
    "ok": None,
    "error": None,
    "log": "",
    "startedAt": None,
    "finishedAt": None,
    "sourceRef": None,
}
INSTANCE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
REQUEST_ID_RE = re.compile(r"^[a-f0-9-]{32,40}$", re.IGNORECASE)
OPENAI_KEY_RE = re.compile(r"^sk-[A-Za-z0-9_-]{20,}$")
TELEGRAM_BOT_TOKEN_RE = re.compile(r"^[0-9]{6,}:[A-Za-z0-9_-]{20,}$")
TELEGRAM_PAIRING_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
WHATSAPP_PAIRING_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{4,32}$")
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")
TELEGRAM_USER_ID_RE = re.compile(r"^(?:telegram:|tg:)?[0-9]{4,20}$", re.IGNORECASE)
TELEGRAM_GROUP_ID_RE = re.compile(r"^-?[0-9]{5,30}$")
TELEGRAM_GROUP_DISCOVERY_RE = re.compile(r"(?<![A-Za-z0-9])(-100[0-9]{6,20}|-[0-9]{6,20})(?![A-Za-z0-9])")
WHATSAPP_GROUP_ID_RE = re.compile(r"^[A-Za-z0-9._:+-]{5,120}@g\.us$")
WHATSAPP_GROUP_DISCOVERY_RE = re.compile(r"([0-9][0-9-]{4,80}@g\.us)", re.IGNORECASE)
BROWSER_PROFILE_RE = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")
DB_HOST_RE = re.compile(r"^[A-Za-z0-9._:-]{1,253}$")
DB_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
DB_VIEW_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.$-]{0,127}$")
ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
WHATSAPP_TIMELOCK_RE = re.compile(
    r"WhatsApp reachout timelock is active;.*?type=([A-Z0-9_]+).*?until=([0-9T:.\-]+Z)",
    re.IGNORECASE,
)
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
TICKETS_DB_TYPES = {
    "postgres": 5432,
    "mysql": 3306,
    "mssql": 1433,
    "mariadb": 3306,
}
TICKETS_SSL_MODES = {"prefer", "require", "disable", "verify-ca", "verify-full"}


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


def docker_request_bytes(method, path, payload=None, timeout=30):
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
        body = response.read()
        if response.status >= 400:
            message = body.decode("utf-8", errors="replace").strip()
            raise RuntimeError(message or f"Docker API HTTP {response.status}")
        return response.status, body
    finally:
        conn.close()


def docker_json(method, path, payload=None, timeout=30):
    status, body = docker_request(method, path, payload=payload, timeout=timeout)
    if not body:
        return {}
    return json.loads(body)


def docker_demux(data):
    raw = data if isinstance(data, bytes) else data.encode("latin1", errors="ignore")
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
    return raw.decode("utf-8", errors="replace")


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
    _, body = docker_request_bytes(
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


def docker_logs(container, tail=500, timeout=30):
    _, body = docker_request_bytes(
        "GET",
        f"/containers/{container}/logs?stdout=true&stderr=true&tail={int(tail)}",
        timeout=timeout,
    )
    return docker_demux(body).strip()


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


def instance_state_dir(instance):
    return ROOT / "instances" / instance / "data" / ".openclaw"


def instance_config_path(instance):
    return instance_state_dir(instance) / "openclaw.json"


def instance_access_meta_path(instance):
    return instance_state_dir(instance) / "oces-access.json"


def read_json_file(path, default):
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    return data if data is not None else default


def get_gateway_token(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")

    env_path = ROOT / "instances" / instance / ".env"
    token = read_env(env_path).get("OPENCLAW_GATEWAY_TOKEN", "").strip()
    source = ".env" if token else ""

    if not token:
        config = read_json_file(instance_config_path(instance), {})
        gateway = config.get("gateway") if isinstance(config.get("gateway"), dict) else {}
        auth = gateway.get("auth") if isinstance(gateway.get("auth"), dict) else {}
        raw_token = str(auth.get("token", "")).strip()
        if raw_token and not raw_token.startswith("${"):
            token = raw_token
            source = "openclaw.json"

    if not token:
        raise ValueError("token do gateway nao encontrado para esta instancia")

    stack = load_stack()
    cfg = stack["instances"].get(instance, {})
    return {
        "ok": True,
        "instance": instance,
        "domain": cfg.get("domain", ""),
        "token": token,
        "source": source,
    }


def tickets_db_env_path(instance):
    return ROOT / "instances" / instance / ".env"


def tickets_db_summary(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")

    env = read_env(tickets_db_env_path(instance))
    db_type = env.get("TICKETS_DB_TYPE", "").strip()
    host = env.get("TICKETS_DB_HOST", "").strip()
    port = env.get("TICKETS_DB_PORT", "").strip()
    database = env.get("TICKETS_DB_NAME", "").strip()
    user = env.get("TICKETS_DB_USER", "").strip()
    view = env.get("TICKETS_DB_SAFE_VIEW", "").strip()
    sslmode = env.get("TICKETS_DB_SSLMODE", "").strip() or "prefer"
    password_saved = bool(env.get("TICKETS_DB_PASSWORD", ""))
    configured = bool(db_type and host and port and database and user and view)
    return {
        "ok": True,
        "instance": instance,
        "configured": configured,
        "type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "user": user,
        "safeView": view,
        "sslmode": sslmode,
        "passwordSaved": password_saved,
        "mode": "read-only",
    }


def normalize_tickets_db_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")

    db_type = str(payload.get("type", "")).strip().lower()
    host = str(payload.get("host", "")).strip()
    raw_port = str(payload.get("port", "")).strip()
    database = str(payload.get("database", "")).strip()
    user = str(payload.get("user", "")).strip()
    password = str(payload.get("password", "")).strip()
    safe_view = str(payload.get("safeView", "")).strip() or "vw_chamados_agent"
    sslmode = str(payload.get("sslmode", "prefer")).strip().lower() or "prefer"

    if db_type not in TICKETS_DB_TYPES:
        raise ValueError("tipo de banco nao permitido")
    if not DB_HOST_RE.match(host) or host in {".", "-", "_"}:
        raise ValueError("host do banco invalido")
    if raw_port:
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise ValueError("porta do banco invalida") from exc
    else:
        port = TICKETS_DB_TYPES[db_type]
    if port < 1 or port > 65535:
        raise ValueError("porta do banco invalida")
    if not DB_NAME_RE.match(database):
        raise ValueError("nome do banco invalido")
    if not user or len(user) > 128 or any(char.isspace() for char in user):
        raise ValueError("usuario do banco invalido")
    if safe_view and not DB_VIEW_RE.match(safe_view):
        raise ValueError("view/tabela segura invalida")
    if sslmode not in TICKETS_SSL_MODES:
        raise ValueError("modo SSL invalido")

    return {
        "type": db_type,
        "host": host,
        "port": str(port),
        "database": database,
        "user": user,
        "password": password,
        "safeView": safe_view,
        "sslmode": sslmode,
    }


def save_tickets_db_config(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    config = normalize_tickets_db_payload(payload)
    env_path = tickets_db_env_path(instance)
    with CREATE_LOCK:
        write_env_value(env_path, "TICKETS_DB_TYPE", config["type"])
        write_env_value(env_path, "TICKETS_DB_HOST", config["host"])
        write_env_value(env_path, "TICKETS_DB_PORT", config["port"])
        write_env_value(env_path, "TICKETS_DB_NAME", config["database"])
        write_env_value(env_path, "TICKETS_DB_USER", config["user"])
        if config["password"]:
            write_env_value(env_path, "TICKETS_DB_PASSWORD", config["password"])
        write_env_value(env_path, "TICKETS_DB_SAFE_VIEW", config["safeView"])
        write_env_value(env_path, "TICKETS_DB_SSLMODE", config["sslmode"])
    return tickets_db_summary(instance)


def test_tickets_db_reachability(instance):
    summary = tickets_db_summary(instance)
    if not summary["configured"]:
        raise ValueError("configure host, porta, banco, usuario e view segura antes de testar")
    started = time.time()
    try:
        with socket.create_connection((summary["host"], int(summary["port"])), timeout=8):
            pass
    except OSError as exc:
        return {
            **summary,
            "reachable": False,
            "latencyMs": None,
            "error": str(exc),
        }
    latency_ms = int((time.time() - started) * 1000)
    return {
        **summary,
        "reachable": True,
        "latencyMs": latency_ms,
        "error": "",
    }


def write_json_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".oces-bak")
        try:
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
        except Exception:
            pass
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2).rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )


def normalize_access_identity(channel, kind, identity):
    channel = str(channel or "").strip().lower()
    kind = str(kind or "").strip().lower()
    value = str(identity or "").strip()
    if channel not in ("telegram", "whatsapp"):
        raise ValueError("canal precisa ser telegram ou whatsapp")
    if kind not in ("contact", "group"):
        raise ValueError("tipo precisa ser contato ou grupo")
    if channel == "telegram" and kind == "contact":
        value = re.sub(r"^(telegram|tg):", "", value, flags=re.IGNORECASE)
        if not TELEGRAM_USER_ID_RE.match(value):
            raise ValueError("contato Telegram precisa ser o ID numerico do usuario")
        return value
    if channel == "telegram" and kind == "group":
        if not TELEGRAM_GROUP_ID_RE.match(value):
            raise ValueError("grupo Telegram precisa ser o chat id numerico, exemplo -1001234567890")
        return value
    if channel == "whatsapp" and kind == "contact":
        value = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if not PHONE_RE.match(value):
            raise ValueError("contato WhatsApp precisa estar em formato internacional, exemplo +5541999578125")
        return value
    if not WHATSAPP_GROUP_ID_RE.match(value):
        raise ValueError("grupo WhatsApp precisa ser o id do grupo terminado em @g.us")
    return value


def owner_identity(channel, identity):
    return f"{channel}:{identity}"


def unique_list(values):
    seen = set()
    result = []
    for value in values or []:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def read_access_meta(instance):
    data = read_json_file(instance_access_meta_path(instance), {"items": []})
    if not isinstance(data, dict):
        return {"items": []}
    if not isinstance(data.get("items"), list):
        data["items"] = []
    return data


def write_access_meta(instance, items):
    write_json_file(
        instance_access_meta_path(instance),
        {"items": sorted(items, key=lambda item: (item["channel"], item["kind"], item["id"]))},
    )


def access_meta_index(meta):
    indexed = {}
    for item in meta.get("items", []):
        if not isinstance(item, dict):
            continue
        key = (str(item.get("channel", "")), str(item.get("kind", "")), str(item.get("id", "")))
        if all(key):
            indexed[key] = item
    return indexed


def append_access_item(items, item):
    key = (item["channel"], item["kind"], item["id"])
    next_items = [
        existing
        for existing in items
        if (existing.get("channel"), existing.get("kind"), existing.get("id")) != key
    ]
    next_items.append(item)
    return next_items


def remove_access_item(items, channel, kind, identity):
    return [
        existing
        for existing in items
        if existing.get("channel") != channel or existing.get("kind") != kind or existing.get("id") != identity
    ]


def ensure_channel_config(config, channel):
    channels = config.setdefault("channels", {})
    if not isinstance(channels, dict):
        config["channels"] = {}
        channels = config["channels"]
    cfg = channels.setdefault(channel, {})
    if not isinstance(cfg, dict):
        channels[channel] = {}
        cfg = channels[channel]
    return cfg


def set_group_config(channel_cfg, group_id):
    groups = channel_cfg.setdefault("groups", {})
    if not isinstance(groups, dict):
        channel_cfg["groups"] = {}
        groups = channel_cfg["groups"]
    current = groups.get(group_id)
    if not isinstance(current, dict):
        current = {}
    current.setdefault("requireMention", False)
    groups[group_id] = current


def remove_group_config(channel_cfg, group_id):
    groups = channel_cfg.get("groups")
    if isinstance(groups, dict):
        groups.pop(group_id, None)
        if not groups:
            channel_cfg.pop("groups", None)


def set_access_in_config(config, channel, kind, identity, access):
    channel_cfg = ensure_channel_config(config, channel)
    if kind == "contact":
        channel_cfg["dmPolicy"] = "allowlist"
        channel_cfg["allowFrom"] = unique_list([*(channel_cfg.get("allowFrom") or []), identity])
    else:
        channel_cfg["groupPolicy"] = "allowlist"
        set_group_config(channel_cfg, identity)

    commands = config.setdefault("commands", {})
    if not isinstance(commands, dict):
        config["commands"] = {}
        commands = config["commands"]
    owners = unique_list(commands.get("ownerAllowFrom") or [])
    scoped_owner = owner_identity(channel, identity)
    if access == "admin" and kind == "contact":
        owners = unique_list([*owners, scoped_owner])
    else:
        owners = [item for item in owners if item != scoped_owner]
    if owners:
        commands["ownerAllowFrom"] = owners
    else:
        commands.pop("ownerAllowFrom", None)


def remove_access_from_config(config, channel, kind, identity):
    channel_cfg = ensure_channel_config(config, channel)
    if kind == "contact":
        channel_cfg["allowFrom"] = [
            item for item in unique_list(channel_cfg.get("allowFrom") or []) if item != identity
        ]
        if not channel_cfg["allowFrom"]:
            channel_cfg.pop("allowFrom", None)
    else:
        remove_group_config(channel_cfg, identity)

    commands = config.get("commands")
    if isinstance(commands, dict):
        scoped_owner = owner_identity(channel, identity)
        commands["ownerAllowFrom"] = [
            item for item in unique_list(commands.get("ownerAllowFrom") or []) if item != scoped_owner
        ]
        if not commands["ownerAllowFrom"]:
            commands.pop("ownerAllowFrom", None)


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


def docker_pull_image(image, tag="latest", timeout=900):
    docker_request("POST", f"/images/create?fromImage={image}&tag={tag}", timeout=timeout)


def run_helper_container(image, cmd, binds=None, workdir=None, timeout=900, user=None):
    payload = {
        "Image": image,
        "Cmd": cmd,
        "WorkingDir": workdir or "/",
        "User": user or "",
        "HostConfig": {
            "AutoRemove": False,
            "Binds": binds or [],
        },
    }
    created = docker_json("POST", "/containers/create", payload=payload, timeout=30)
    container_id = created["Id"]
    try:
        docker_request("POST", f"/containers/{container_id}/start", timeout=30)
        result = wait_container(container_id, timeout=timeout)
        _, logs_raw = docker_request_bytes(
            "GET",
            f"/containers/{container_id}/logs?stdout=true&stderr=true",
            timeout=60,
        )
        output = docker_demux(logs_raw).strip()
        if result.get("StatusCode") != 0:
            raise RuntimeError(output or f"helper container failed: {image}")
        return output
    finally:
        try:
            docker_request("DELETE", f"/containers/{container_id}?force=true", timeout=30)
        except Exception:
            pass


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


def ensure_default_channel_plugins(name):
    script = r'''
set -eu
log=/tmp/oces-whatsapp-plugin-install.log
if ! openclaw plugins install clawhub:@openclaw/whatsapp >"$log" 2>&1; then
  if ! grep -qi "already exists" "$log"; then
    cat "$log"
    exit 1
  fi
fi
cat "$log"
openclaw plugins enable whatsapp >/dev/null 2>&1 || true
openclaw plugins enable telegram >/dev/null 2>&1 || true
openclaw channels add --channel whatsapp >/dev/null 2>&1 || true
'''
    return docker_exec(f"oces-{name}", ["sh", "-lc", script], timeout=240)


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
            plugin_output = ensure_default_channel_plugins(name)
            docker_request("POST", f"/containers/oces-{name}/restart?t=10", timeout=45)
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
            "plugins": plugin_output,
        }


def update_timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append_update_log(message):
    with UPDATE_LOCK:
        current = UPDATE_JOB.get("log") or ""
        line = f"[{update_timestamp()}] {message}".rstrip()
        UPDATE_JOB["log"] = (current + "\n" + line).strip()[-80000:]


def set_update_job(**changes):
    with UPDATE_LOCK:
        UPDATE_JOB.update(changes)
        return dict(UPDATE_JOB)


def get_update_job():
    with UPDATE_LOCK:
        return dict(UPDATE_JOB)


def prepare_openclaw_update_source():
    script = r'''
set -eu
repo="${OPENCLAW_UPDATE_REPO:-https://github.com/openclaw/openclaw.git}"
ref="${OPENCLAW_UPDATE_REF:-}"
mkdir -p /workspace/.cache/openclaw-update
cd /workspace/.cache/openclaw-update
if [ -z "$ref" ]; then
  ref="$(git ls-remote --tags --refs "$repo" 'refs/tags/v*' \
    | sed 's#.*refs/tags/##' \
    | grep -E '^v[0-9]{4}\.[0-9]+\.[0-9]+$' \
    | sort -V \
    | tail -n 1)"
fi
test -n "$ref"
rm -rf source.tmp source
git clone --depth 1 --branch "$ref" "$repo" source.tmp
mv source.tmp source
printf '%s\n' "$ref" > source/.oces-source-ref
printf 'Fonte OpenClaw preparada: %s\n' "$ref"
'''
    output = run_helper_container(
        "openclaw:latest",
        ["sh", "-lc", script],
        binds=[f"{HOST_ROOT}:/workspace"],
        workdir="/workspace",
        timeout=900,
        user="root",
    )
    source_ref = ""
    source_ref_path = ROOT / ".cache" / "openclaw-update" / "source" / ".oces-source-ref"
    if source_ref_path.exists():
        source_ref = source_ref_path.read_text(encoding="utf-8").strip()
    return source_ref, output


def build_openclaw_latest_image():
    docker_pull_image("docker", "27-cli", timeout=900)
    return run_helper_container(
        "docker:27-cli",
        ["sh", "-lc", "docker build -t openclaw:latest /workspace/.cache/openclaw-update/source"],
        binds=[
            "/var/run/docker.sock:/var/run/docker.sock",
            f"{HOST_ROOT}:/workspace",
        ],
        workdir="/workspace",
        timeout=3600,
        user="root",
    )


def run_openclaw_update_job():
    try:
        with CREATE_LOCK:
            append_update_log("Preparando a fonte oficial mais recente do OpenClaw...")
            source_ref, source_output = prepare_openclaw_update_source()
            if source_ref:
                set_update_job(sourceRef=source_ref)
            if source_output:
                append_update_log(source_output)

            append_update_log("Construindo a imagem Docker openclaw:latest...")
            build_output = build_openclaw_latest_image()
            if build_output:
                append_update_log(build_output[-12000:])

            instances = sorted(known_instances())
            append_update_log(f"Recriando {len(instances)} instancia(s) com a nova imagem...")
            for name in instances:
                append_update_log(f"Recriando {name}...")
                recreate_openclaw_container(name)
                try:
                    plugin_output = ensure_default_channel_plugins(name)
                    if plugin_output:
                        append_update_log(f"{name}: plugins verificados.")
                    docker_request("POST", f"/containers/oces-{name}/restart?t=10", timeout=45)
                except Exception as exc:
                    append_update_log(f"Aviso em {name}: {exc}")
            append_update_log("Atualizacao concluida.")
            set_update_job(running=False, ok=True, error=None, finishedAt=update_timestamp())
    except Exception as exc:
        append_update_log(f"ERRO: {exc}")
        set_update_job(running=False, ok=False, error=str(exc), finishedAt=update_timestamp())


def start_openclaw_update():
    current = get_update_job()
    if current.get("running"):
        raise ValueError("atualizacao ja em andamento")
    set_update_job(
        running=True,
        ok=None,
        error=None,
        log="",
        startedAt=update_timestamp(),
        finishedAt=None,
        sourceRef=None,
    )
    thread = threading.Thread(target=run_openclaw_update_job, daemon=True)
    thread.start()
    append_update_log("Atualizacao OpenClaw iniciada pelo painel.")
    return get_update_job()


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


def configure_telegram(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    bot_token = str(payload.get("botToken", "")).strip()
    expected_user = str(payload.get("expectedUser", "")).strip()

    if bot_token and not TELEGRAM_BOT_TOKEN_RE.match(bot_token):
        raise ValueError("token do bot Telegram invalido")

    env_path = ROOT / "instances" / instance / ".env"
    output = ""
    with CREATE_LOCK:
        if bot_token:
            write_env_value(env_path, "TELEGRAM_BOT_TOKEN", bot_token)
        write_env_value(env_path, "TELEGRAM_EXPECTED_USER", expected_user)
        if bot_token:
            output = docker_exec(
                f"oces-{instance}",
                ["openclaw", "channels", "add", "--channel", "telegram", "--token", bot_token],
                timeout=60,
            )
            docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)

    return {
        "ok": True,
        "instance": instance,
        "action": "telegram-config",
        "configured": bool(bot_token or read_env(env_path).get("TELEGRAM_BOT_TOKEN")),
        "expectedUser": expected_user,
        "output": output,
    }


def telegram_pairing_status(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    env = read_env(ROOT / "instances" / instance / ".env")
    output = ""
    pending = []
    try:
        output = docker_exec(
            f"oces-{instance}",
            ["openclaw", "pairing", "list", "--channel", "telegram", "--json"],
            timeout=30,
        )
        if output:
            parsed = json.loads(output)
            if isinstance(parsed, list):
                pending = parsed
            elif isinstance(parsed, dict):
                found_collection = False
                for key in ("pending", "requests", "items"):
                    if isinstance(parsed.get(key), list):
                        pending = parsed[key]
                        found_collection = True
                        break
                if not found_collection and parsed:
                    pending = [parsed]
    except json.JSONDecodeError:
        pass
    except Exception as exc:
        output = str(exc)

    return {
        "ok": True,
        "instance": instance,
        "action": "telegram-pairing-status",
        "configured": bool(env.get("TELEGRAM_BOT_TOKEN")),
        "expectedUser": env.get("TELEGRAM_EXPECTED_USER", ""),
        "pending": pending,
        "output": ANSI_RE.sub("", output).replace("\r", ""),
    }


def approve_telegram_pairing(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    code = str(payload.get("code", "")).strip()
    if not TELEGRAM_PAIRING_CODE_RE.match(code):
        raise ValueError("codigo de pareamento invalido")
    output = docker_exec(
        f"oces-{instance}",
        ["openclaw", "pairing", "approve", "--channel", "telegram", "--notify", code],
        timeout=45,
    )
    return {"ok": True, "instance": instance, "action": "telegram-pairing-approve", "code": code, "output": output}


def extract_pairing_requests(output):
    if not output:
        return []
    parsed = json.loads(output)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        for key in ("pending", "requests", "items"):
            if isinstance(parsed.get(key), list):
                return parsed[key]
        return [parsed] if parsed else []
    return []


def configure_whatsapp_number(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    number = str(payload.get("number", "")).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if number and not PHONE_RE.match(number):
        raise ValueError("numero deve estar em formato internacional, exemplo +5541999578125")

    env_path = ROOT / "instances" / instance / ".env"
    write_env_value(env_path, "WHATSAPP_EXPECTED_NUMBER", number)
    return {"ok": True, "instance": instance, "action": "whatsapp-number", "number": number}


def whatsapp_pairing_status(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    output = ""
    pending = []
    try:
        output = docker_exec(
            f"oces-{instance}",
            ["openclaw", "pairing", "list", "--channel", "whatsapp", "--json"],
            timeout=30,
        )
        pending = extract_pairing_requests(output)
    except json.JSONDecodeError:
        pass
    except Exception as exc:
        output = str(exc)

    return {
        "ok": True,
        "instance": instance,
        "action": "whatsapp-pairing-status",
        "pending": pending,
        "output": ANSI_RE.sub("", output).replace("\r", ""),
    }


def discover_telegram_groups(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")

    candidates = {}

    def add_candidate(group_id, source, detail=""):
        value = str(group_id or "").strip()
        if not TELEGRAM_GROUP_ID_RE.match(value):
            return
        current = candidates.setdefault(
            value,
            {
                "id": value,
                "channel": "telegram",
                "kind": "group",
                "label": "",
                "source": source,
                "detail": "",
            },
        )
        if detail and not current.get("detail"):
            current["detail"] = detail[:240]
        if current.get("source") != "pairing" and source == "pairing":
            current["source"] = source

    try:
        pairing = telegram_pairing_status(instance)
        for item in pairing.get("pending", []):
            raw = json.dumps(item, ensure_ascii=False)
            for match in TELEGRAM_GROUP_DISCOVERY_RE.findall(raw):
                add_candidate(match, "pairing", raw)
    except Exception:
        pass

    try:
        logs = docker_logs(f"oces-{instance}", tail=1000, timeout=30)
        for line in logs.splitlines():
            lowered = line.lower()
            if "telegram" not in lowered or ("group" not in lowered and "-100" not in lowered):
                continue
            clean = ANSI_RE.sub("", line).replace("\r", "")
            for match in TELEGRAM_GROUP_DISCOVERY_RE.findall(clean):
                add_candidate(match, "log", clean)
    except Exception:
        pass

    configured = {
        item["id"]
        for item in list_channel_access(instance).get("items", [])
        if item.get("channel") == "telegram" and item.get("kind") == "group"
    }
    items = []
    for group_id, item in candidates.items():
        item["configured"] = group_id in configured
        if not item.get("label"):
            item["label"] = "Grupo Telegram"
        items.append(item)
    items.sort(key=lambda item: (item.get("configured", False), item.get("source") != "pairing", item["id"]))
    return {"ok": True, "instance": instance, "items": items}


def discover_whatsapp_groups(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")

    candidates = {}

    def add_candidate(group_id, source, detail=""):
        value = str(group_id or "").strip()
        if not WHATSAPP_GROUP_ID_RE.match(value):
            return
        current = candidates.setdefault(
            value,
            {
                "id": value,
                "channel": "whatsapp",
                "kind": "group",
                "label": "",
                "source": source,
                "detail": "",
            },
        )
        if detail and not current.get("detail"):
            current["detail"] = detail[:240]
        if current.get("source") != "pairing" and source == "pairing":
            current["source"] = source

    try:
        pairing = whatsapp_pairing_status(instance)
        for item in pairing.get("pending", []):
            raw = json.dumps(item, ensure_ascii=False)
            for match in WHATSAPP_GROUP_DISCOVERY_RE.findall(raw):
                add_candidate(match, "pairing", raw)
    except Exception:
        pass

    try:
        logs = docker_logs(f"oces-{instance}", tail=700, timeout=30)
        for line in logs.splitlines():
            if "@g.us" not in line:
                continue
            for match in WHATSAPP_GROUP_DISCOVERY_RE.findall(line):
                add_candidate(match, "log", ANSI_RE.sub("", line).replace("\r", ""))
    except Exception:
        pass

    configured = {
        item["id"]
        for item in list_channel_access(instance).get("items", [])
        if item.get("channel") == "whatsapp" and item.get("kind") == "group"
    }
    items = []
    for item in sorted(candidates.values(), key=lambda value: value["id"]):
        item["configured"] = item["id"] in configured
        items.append(item)
    return {"ok": True, "instance": instance, "items": items}


def approve_whatsapp_pairing(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    code = str(payload.get("code", "")).strip()
    if not WHATSAPP_PAIRING_CODE_RE.match(code):
        raise ValueError("codigo de pareamento invalido")
    output = docker_exec(
        f"oces-{instance}",
        ["openclaw", "pairing", "approve", "whatsapp", code],
        timeout=45,
    )
    return {"ok": True, "instance": instance, "action": "whatsapp-pairing-approve", "code": code, "output": output}


def parse_iso_utc(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def whatsapp_timelock_alert(instance):
    db_path = instance_state_dir(instance) / "state" / "openclaw.sqlite"
    if not db_path.exists():
        return None
    connection = None
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=3)
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT target, last_error, failed_at, updated_at, substr(entry_json, 1, 1200) AS entry_json
            FROM delivery_queue_entries
            WHERE channel = 'whatsapp'
              AND status = 'failed'
              AND last_error LIKE '%reachout timelock%'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchall()
    except sqlite3.Error:
        return None
    finally:
        if connection is not None:
            connection.close()
    if not rows:
        return None

    row = rows[0]
    error = row["last_error"] or ""
    match = WHATSAPP_TIMELOCK_RE.search(error)
    until = match.group(2) if match else ""
    until_dt = parse_iso_utc(until) if until else None
    return {
        "kind": "reachout_timelock",
        "active": bool(until_dt and until_dt > datetime.now(timezone.utc)),
        "type": match.group(1) if match else "",
        "until": until,
        "target": row["target"] or "",
        "message": error,
        "failedAt": row["failed_at"],
        "updatedAt": row["updated_at"],
    }


def config_access_entries(config, meta):
    indexed = access_meta_index(meta)
    entries = []
    entry_keys = set()
    commands = config.get("commands") if isinstance(config.get("commands"), dict) else {}
    owners = set(unique_list(commands.get("ownerAllowFrom") or []))
    channels = config.get("channels") if isinstance(config.get("channels"), dict) else {}

    for channel in ("telegram", "whatsapp"):
        channel_cfg = channels.get(channel) if isinstance(channels.get(channel), dict) else {}
        for identity in unique_list(channel_cfg.get("allowFrom") or []):
            key = (channel, "contact", identity)
            saved = indexed.get(key, {})
            access = "admin" if owner_identity(channel, identity) in owners else saved.get("access", "chat")
            entries.append(
                {
                    "channel": channel,
                    "kind": "contact",
                    "id": identity,
                    "label": saved.get("label", ""),
                    "access": access if access in ("chat", "admin") else "chat",
                    "source": saved.get("source", "config"),
                }
            )
            entry_keys.add(key)
        groups = channel_cfg.get("groups")
        if isinstance(groups, dict):
            for identity in sorted(groups.keys()):
                key = (channel, "group", identity)
                saved = indexed.get(key, {})
                entries.append(
                    {
                        "channel": channel,
                        "kind": "group",
                        "id": identity,
                        "label": saved.get("label", ""),
                        "access": "chat",
                        "source": saved.get("source", "config"),
                    }
                )
                entry_keys.add(key)
    for owner in sorted(owners):
        if ":" not in owner:
            continue
        channel, identity = owner.split(":", 1)
        if channel not in ("telegram", "whatsapp") or not identity:
            continue
        key = (channel, "contact", identity)
        if key in entry_keys:
            continue
        saved = indexed.get(key, {})
        entries.append(
            {
                "channel": channel,
                "kind": "contact",
                "id": identity,
                "label": saved.get("label", ""),
                "access": "admin",
                "source": saved.get("source", "owner"),
            }
        )
    return sorted(entries, key=lambda item: (item["channel"], item["kind"], item["label"] or item["id"]))


def list_channel_access(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    config = read_json_file(instance_config_path(instance), {})
    if not isinstance(config, dict):
        config = {}
    meta = read_access_meta(instance)
    return {"ok": True, "instance": instance, "items": config_access_entries(config, meta)}


def save_channel_access(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    channel = str(payload.get("channel", "")).strip().lower()
    kind = str(payload.get("kind", "")).strip().lower()
    identity = normalize_access_identity(channel, kind, payload.get("id", ""))
    access = str(payload.get("access", "chat")).strip().lower()
    if access not in ("chat", "admin"):
        raise ValueError("acesso precisa ser conversa ou admin")
    if kind == "group" and access == "admin":
        raise ValueError("acesso admin e permitido apenas para contatos; grupos ficam como conversa")
    label = str(payload.get("label", "")).strip()[:80]

    with CREATE_LOCK:
        config_path = instance_config_path(instance)
        config = read_json_file(config_path, {})
        if not isinstance(config, dict):
            config = {}
        set_access_in_config(config, channel, kind, identity, access)
        write_json_file(config_path, config)

        meta = read_access_meta(instance)
        item = {
            "channel": channel,
            "kind": kind,
            "id": identity,
            "label": label,
            "access": access,
            "source": "dashboard",
            "updatedAt": update_timestamp(),
        }
        write_access_meta(instance, append_access_item(meta.get("items", []), item))
        chown_instance_data(instance)
        docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)

    return {"ok": True, "instance": instance, "item": item, "items": list_channel_access(instance)["items"]}


def delete_channel_access(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    channel = str(payload.get("channel", "")).strip().lower()
    kind = str(payload.get("kind", "")).strip().lower()
    identity = normalize_access_identity(channel, kind, payload.get("id", ""))

    with CREATE_LOCK:
        config_path = instance_config_path(instance)
        config = read_json_file(config_path, {})
        if not isinstance(config, dict):
            config = {}
        remove_access_from_config(config, channel, kind, identity)
        write_json_file(config_path, config)
        meta = read_access_meta(instance)
        write_access_meta(instance, remove_access_item(meta.get("items", []), channel, kind, identity))
        chown_instance_data(instance)
        docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)

    return {"ok": True, "instance": instance, "items": list_channel_access(instance)["items"]}


def browser_config_summary(config):
    browser = config.get("browser") if isinstance(config.get("browser"), dict) else {}
    profiles = browser.get("profiles") if isinstance(browser.get("profiles"), dict) else {}
    items = []
    for name, profile in sorted(profiles.items()):
        if not isinstance(profile, dict):
            continue
        items.append(
            {
                "name": name,
                "driver": profile.get("driver", ""),
                "attachOnly": bool(profile.get("attachOnly")),
                "userDataDir": profile.get("userDataDir", ""),
                "cdpUrl": profile.get("cdpUrl", ""),
                "executablePath": profile.get("executablePath", ""),
                "color": profile.get("color", ""),
            }
        )
    return {
        "enabled": bool(browser.get("enabled")),
        "profiles": items,
        "raw": browser if isinstance(browser, dict) else {},
    }


def get_browser_config(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    config = read_json_file(instance_config_path(instance), {})
    if not isinstance(config, dict):
        config = {}
    return {"ok": True, "instance": instance, "browser": browser_config_summary(config)}


def normalize_browser_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload invalido")
    profile_name = str(payload.get("profileName") or "edge").strip().lower()
    if not BROWSER_PROFILE_RE.match(profile_name):
        raise ValueError("perfil precisa usar letras minusculas, numeros, hifen ou underline")
    driver = str(payload.get("driver") or "existing-session").strip()
    if driver != "existing-session":
        raise ValueError("este painel gerencia apenas o modo existing-session")
    user_data_dir = str(payload.get("userDataDir") or "").strip()
    if not user_data_dir:
        raise ValueError("informe o diretorio do perfil do navegador")
    if "\x00" in user_data_dir or "\n" in user_data_dir or "\r" in user_data_dir:
        raise ValueError("diretorio do perfil invalido")
    cdp_url = str(payload.get("cdpUrl") or "").strip()
    if cdp_url:
        parsed_cdp = urlparse(cdp_url)
        if parsed_cdp.scheme not in ("http", "https") or not parsed_cdp.netloc:
            raise ValueError("CDP URL precisa ser uma URL http(s), exemplo http://127.0.0.1:9222")
    color = str(payload.get("color") or "#0078D7").strip()
    if not re.match(r"^#[0-9A-Fa-f]{6}$", color):
        raise ValueError("cor precisa estar no formato #RRGGBB")
    profile = {
        "driver": driver,
        "attachOnly": bool(payload.get("attachOnly", True)),
        "userDataDir": user_data_dir,
        "color": color,
    }
    if cdp_url:
        profile["cdpUrl"] = cdp_url
    return {
        "profileName": profile_name,
        "profile": profile,
    }


def save_browser_config(instance, payload):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    normalized = normalize_browser_payload(payload)

    with CREATE_LOCK:
        config_path = instance_config_path(instance)
        config = read_json_file(config_path, {})
        if not isinstance(config, dict):
            config = {}
        browser = config.setdefault("browser", {})
        if not isinstance(browser, dict):
            config["browser"] = {}
            browser = config["browser"]
        browser["enabled"] = True
        profiles = browser.setdefault("profiles", {})
        if not isinstance(profiles, dict):
            browser["profiles"] = {}
            profiles = browser["profiles"]
        profiles[normalized["profileName"]] = normalized["profile"]
        write_json_file(config_path, config)
        chown_instance_data(instance)
        docker_request("POST", f"/containers/oces-{instance}/restart?t=10", timeout=45)

    return {
        "ok": True,
        "instance": instance,
        "action": "browser-config",
        "profileName": normalized["profileName"],
        "browser": browser_config_summary(config),
    }


def validate_browser_config(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    config = read_json_file(instance_config_path(instance), {})
    if not isinstance(config, dict):
        config = {}
    output = ""
    ok = False
    try:
        output = docker_exec(
            f"oces-{instance}",
            ["openclaw", "browser", "profiles"],
            timeout=45,
        )
        ok = True
    except Exception as exc:
        output = str(exc)
    return {
        "ok": True,
        "instance": instance,
        "action": "browser-validate",
        "validated": ok,
        "browser": browser_config_summary(config),
        "output": ANSI_RE.sub("", output).replace("\r", ""),
    }


def start_openai_oauth(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    script = r'''
set -u
dir=/tmp/oces-openai-oauth
mkdir -p "$dir"
if [ -s "$dir/pid" ] && kill -0 "$(cat "$dir/pid")" 2>/dev/null; then
  printf '{"started":false,"running":true,"pid":%s}\n' "$(cat "$dir/pid")"
  exit 0
fi
rm -f "$dir/log" "$dir/exit" "$dir/pid"
(
  if command -v script >/dev/null 2>&1; then
    script -q -e -c "node dist/index.js models auth login --provider openai --device-code" /dev/null
  else
    node dist/index.js models auth login --provider openai --device-code
  fi
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
const cleanLog = log.replace(/\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])/g, "");
const deviceUrl = (
  cleanLog.match(/URL:\s*(https?:\/\/\S+)/i)?.[1] ||
  links.find((link) => /\/codex\/device\b/.test(link)) ||
  ""
);
const deviceCode = cleanLog.match(/Code:\s*([A-Z0-9-]{4,})/i)?.[1] || "";
const expiresText = cleanLog.match(/Code expires in[^\n\r.]*(?:\.)?/i)?.[0] || "";
console.log("__OCES_JSON__" + JSON.stringify({
  running,
  pid: pid || null,
  exitCode,
  log,
  links,
  deviceUrl,
  deviceCode,
  expiresText,
}));
'''
    output = docker_exec(f"oces-{instance}", ["node", "-e", script], timeout=15)
    marker = "__OCES_JSON__"
    payload = output.rsplit(marker, 1)[-1] if marker in output else output
    json_start = payload.find("{")
    if json_start >= 0:
        payload = payload[json_start:]
    data, _ = json.JSONDecoder().raw_decode(payload or "{}")
    data.update({"ok": True, "instance": instance, "action": "openai-oauth-status"})
    return data


def start_whatsapp_login(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    script = r'''
set -eu
dir=/tmp/oces-whatsapp-login
mkdir -p "$dir"
if [ -s "$dir/pid" ] && kill -0 "$(cat "$dir/pid")" 2>/dev/null; then
  printf '{"started":false,"running":true,"pid":%s}\n' "$(cat "$dir/pid")"
  exit 0
fi
rm -f "$dir/log" "$dir/exit" "$dir/pid"
(
  if command -v script >/dev/null 2>&1; then
    TERM=xterm-256color COLUMNS=160 LINES=80 script -q -e -c "stty cols 160 rows 80 2>/dev/null || true; openclaw channels login --channel whatsapp --verbose" /dev/null
  else
    TERM=xterm-256color COLUMNS=160 LINES=80 openclaw channels login --channel whatsapp --verbose
  fi
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
    data.update({"ok": True, "instance": instance, "action": "whatsapp-login-start"})
    return data


def whatsapp_login_status(instance):
    if instance not in known_instances():
        raise ValueError("unknown instance")
    container = f"oces-{instance}"
    pid = docker_exec(container, ["sh", "-lc", "cat /tmp/oces-whatsapp-login/pid 2>/dev/null || true"], timeout=10).strip()
    running_raw = docker_exec(
        container,
        ["sh", "-lc", 'pid="$(cat /tmp/oces-whatsapp-login/pid 2>/dev/null || true)"; [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && echo true || echo false'],
        timeout=10,
    ).strip()
    exit_raw = docker_exec(container, ["sh", "-lc", "cat /tmp/oces-whatsapp-login/exit 2>/dev/null || true"], timeout=10).strip()
    log = docker_exec(container, ["sh", "-lc", "tail -c 70000 /tmp/oces-whatsapp-login/log 2>/dev/null || true"], timeout=20)
    log = ANSI_RE.sub("", log).replace("\r", "")
    qr_marker = "Open the WhatsApp app"
    qr_index = log.rfind(qr_marker)
    if qr_index >= 0:
        log = log[qr_index:]
    if len(log) > 70000:
        log = log[-70000:]
    env = read_env(ROOT / "instances" / instance / ".env")
    return {
        "ok": True,
        "instance": instance,
        "action": "whatsapp-login-status",
        "running": running_raw == "true",
        "pid": pid or None,
        "exitCode": int(exit_raw) if exit_raw.isdigit() else None,
        "log": log,
        "number": env.get("WHATSAPP_EXPECTED_NUMBER", ""),
        "deliveryAlert": whatsapp_timelock_alert(instance),
    }


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
        clean_path = posixpath.normpath(unquote(parsed.path))
        if clean_path in ("", "."):
            clean_path = "/"
        if clean_path == "/":
            return str(STATIC_ROOT / "index.html")
        if clean_path.startswith("../") or clean_path == "..":
            return str(STATIC_ROOT / "__not_found__")
        return str(STATIC_ROOT / clean_path.lstrip("/"))

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

        if self.command == "GET" and parsed.path == "/api/admin/openclaw-update/status":
            self.write_json({"ok": True, "job": get_update_job()})
            return

        if self.command == "POST" and parsed.path == "/api/admin/openclaw-update/start":
            try:
                started = start_openclaw_update()
            except ValueError as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=409)
                return
            except Exception as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=500)
                return
            self.write_json({"ok": True, "job": started})
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
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "access"
                and self.command == "GET"
            ):
                try:
                    access = list_channel_access(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(access)
                return

            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "browser"
                and self.command == "GET"
            ):
                try:
                    config = get_browser_config(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(config)
                return

            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "gateway-token"
                and self.command == "GET"
            ):
                try:
                    token = get_gateway_token(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(token)
                return

            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "tickets-db"
                and self.command == "GET"
            ):
                try:
                    config = tickets_db_summary(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(config)
                return

            if (
                len(parts) == 6
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "channels"
                and parts[4] == "telegram"
                and parts[5] == "status"
                and self.command == "GET"
            ):
                try:
                    status = telegram_pairing_status(unquote(parts[2]))
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
                and parts[3] == "channels"
                and parts[4] == "whatsapp"
                and parts[5] == "login-status"
                and self.command == "GET"
            ):
                try:
                    status = whatsapp_login_status(unquote(parts[2]))
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
                and parts[3] == "channels"
                and parts[4] == "whatsapp"
                and parts[5] == "login-start"
                and self.command == "POST"
            ):
                try:
                    started = start_whatsapp_login(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(started)
                return

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
                len(parts) == 7
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "channels"
                and parts[4] == "whatsapp"
                and parts[5] == "pairing"
                and parts[6] == "status"
                and self.command == "GET"
            ):
                try:
                    status = whatsapp_pairing_status(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(status)
                return

            if (
                len(parts) == 7
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "channels"
                and parts[4] == "telegram"
                and parts[5] == "groups"
                and parts[6] == "discovery"
                and self.command == "GET"
            ):
                try:
                    groups = discover_telegram_groups(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(groups)
                return

            if (
                len(parts) == 7
                and parts[0] == "api"
                and parts[1] == "instances"
                and parts[3] == "channels"
                and parts[4] == "whatsapp"
                and parts[5] == "groups"
                and parts[6] == "discovery"
                and self.command == "GET"
            ):
                try:
                    groups = discover_whatsapp_groups(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(groups)
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

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "access":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    saved = save_channel_access(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(saved)
                return

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "browser":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    saved = save_browser_config(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(saved)
                return

            if len(parts) == 4 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "tickets-db":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    saved = save_tickets_db_config(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(saved)
                return

            if len(parts) == 5 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "browser" and parts[4] == "validate":
                try:
                    data = validate_browser_config(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(data)
                return

            if len(parts) == 5 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "tickets-db" and parts[4] == "test":
                try:
                    data = test_tickets_db_reachability(unquote(parts[2]))
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(data)
                return

            if len(parts) == 5 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "access" and parts[4] == "remove":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    removed = delete_channel_access(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(removed)
                return

            if len(parts) == 6 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "channels" and parts[4] == "whatsapp" and parts[5] == "number":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    configured = configure_whatsapp_number(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(configured)
                return

            if len(parts) == 6 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "channels" and parts[4] == "telegram" and parts[5] == "config":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    configured = configure_telegram(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(configured)
                return

            if len(parts) == 7 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "channels" and parts[4] == "telegram" and parts[5] == "pairing" and parts[6] == "approve":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    approved = approve_telegram_pairing(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(approved)
                return

            if len(parts) == 7 and parts[0] == "api" and parts[1] == "instances" and parts[3] == "channels" and parts[4] == "whatsapp" and parts[5] == "pairing" and parts[6] == "approve":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                    approved = approve_whatsapp_pairing(unquote(parts[2]), payload)
                except ValueError as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=400)
                    return
                except Exception as exc:
                    self.write_json({"ok": False, "error": str(exc)}, status=500)
                    return
                self.write_json(approved)
                return

        self.write_json({"ok": False, "error": "not found"}, status=404)

    def authorized(self):
        token = os.environ.get("OCES_ADMIN_TOKEN", "")
        if not token:
            return False
        header = self.headers.get("Authorization", "")
        expected = f"Bearer {token}"
        return hmac.compare_digest(header, expected)

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

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

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
