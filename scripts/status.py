#!/usr/bin/env python3
import argparse
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


ROOT = Path(__file__).resolve().parent.parent
DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")


def run(command, timeout=30):
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        return {"ok": False, "returncode": 127, "stdout": "", "stderr": str(error)}
    except subprocess.TimeoutExpired as error:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": error.stdout or "",
            "stderr": "command timed out",
        }

    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path, timeout=30):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.socket_path)


def docker_api(method, path, body=None, timeout=30):
    if not hasattr(socket, "AF_UNIX") or not Path(DOCKER_SOCKET).exists():
        raise RuntimeError("Docker socket indisponivel")
    connection = UnixHTTPConnection(DOCKER_SOCKET, timeout=timeout)
    payload = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Host": "localhost"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(payload))
    connection.request(method, path, body=payload, headers=headers)
    response = connection.getresponse()
    data = response.read()
    if response.status >= 400:
        raise RuntimeError(data.decode("utf-8", errors="replace") or f"HTTP {response.status}")
    return data


def docker_api_json(method, path, body=None, timeout=30):
    raw = docker_api(method, path, body=body, timeout=timeout)
    return json.loads(raw.decode("utf-8"))


def docker_exec(container, command, timeout=45):
    if shutil.which("docker"):
        result = run(["docker", "exec", container, *command], timeout=timeout)
        return result

    try:
        created = docker_api_json(
            "POST",
            f"/containers/{container}/exec",
            body={
                "AttachStdout": True,
                "AttachStderr": True,
                "Tty": False,
                "Cmd": command,
            },
            timeout=timeout,
        )
        raw = docker_api(
            "POST",
            f"/exec/{created['Id']}/start",
            body={"Detach": False, "Tty": False},
            timeout=timeout,
        )
        inspect = docker_api_json("GET", f"/exec/{created['Id']}/json", timeout=timeout)
        stdout, stderr = split_docker_stream(raw)
        return {
            "ok": inspect.get("ExitCode") == 0,
            "returncode": inspect.get("ExitCode"),
            "stdout": stdout,
            "stderr": stderr,
        }
    except Exception as error:
        return {"ok": False, "returncode": 1, "stdout": "", "stderr": str(error)}


def split_docker_stream(raw):
    stdout = bytearray()
    stderr = bytearray()
    index = 0
    while index + 8 <= len(raw):
        stream_type = raw[index]
        size = int.from_bytes(raw[index + 4:index + 8], "big")
        index += 8
        chunk = raw[index:index + size]
        index += size
        if stream_type == 2:
            stderr.extend(chunk)
        else:
            stdout.extend(chunk)
    if index < len(raw):
        stdout.extend(raw[index:])
    return (
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def load_stack():
    raw = (ROOT / "config" / "stack.yml").read_text(encoding="utf-8")
    if yaml is not None:
        stack = yaml.safe_load(raw)
    else:
        stack = parse_stack_yaml(raw)
    if not isinstance(stack, dict) or not isinstance(stack.get("instances"), dict):
        raise SystemExit("config/stack.yml invalido: instances precisa ser um objeto.")
    return stack


def parse_stack_yaml(raw):
    data = {}
    path = []
    for raw_line in raw.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        level = indent // 2
        key, sep, value = raw_line.strip().partition(":")
        if not sep:
            continue
        path = path[:level]
        parent = data
        for part in path:
            parent = parent.setdefault(part, {})
        if value.strip():
            parent[key] = parse_scalar(value.strip())
        else:
            parent[key] = {}
            path.append(key)
    return data


def parse_scalar(value):
    if value.isdigit():
        return int(value)
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return value.strip("\"'")


def http_health(domain, timeout):
    started = time.time()
    try:
        with urllib.request.urlopen(f"https://{domain}/healthz", timeout=timeout) as response:
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "elapsedMs": round((time.time() - started) * 1000),
                "error": None,
            }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {
            "ok": False,
            "status": None,
            "elapsedMs": round((time.time() - started) * 1000),
            "error": str(error),
        }


def docker_inspect(container):
    try:
        if shutil.which("docker"):
            result = run(["docker", "inspect", container], timeout=15)
            if not result["ok"]:
                raise RuntimeError(result["stderr"].strip() or result["stdout"].strip())
            payload = json.loads(result["stdout"])[0]
        else:
            payload = docker_api_json("GET", f"/containers/{container}/json", timeout=15)
    except (json.JSONDecodeError, IndexError, KeyError, RuntimeError) as error:
        return {
            "exists": False,
            "running": False,
            "health": "unknown",
            "image": None,
            "status": "unknown",
            "startedAt": None,
            "error": str(error),
        }

    state = payload.get("State") or {}
    return {
        "exists": True,
        "running": state.get("Running") is True,
        "health": (state.get("Health") or {}).get("Status"),
        "image": (payload.get("Config") or {}).get("Image"),
        "status": state.get("Status"),
        "startedAt": state.get("StartedAt"),
        "restartCount": payload.get("RestartCount"),
        "error": state.get("Error") or None,
    }


def openclaw_version(container):
    result = docker_exec(container, ["node", "dist/index.js", "--version"], timeout=20)
    if not result["ok"]:
        return {"ok": False, "version": None, "error": brief_error(result)}
    return {"ok": True, "version": result["stdout"].strip(), "error": None}


def openclaw_models(container):
    result = docker_exec(container, ["node", "dist/index.js", "models", "status"], timeout=35)
    data = {
        "ok": result["ok"],
        "default": None,
        "configured": None,
        "openai": {
            "apiKey": False,
            "oauth": False,
            "token": False,
            "effective": None,
        },
        "error": None,
    }
    if not result["ok"]:
        data["error"] = brief_error(result)
        return data

    for raw_line in result["stdout"].splitlines():
        line = raw_line.strip()
        if line.startswith("Default"):
            data["default"] = value_after_colon(line)
        elif line.startswith("Configured models"):
            data["configured"] = value_after_colon(line)
        elif line.startswith("- openai effective="):
            data["openai"]["effective"] = sanitize_model_auth_line(line)
            data["openai"]["apiKey"] = "api_key=" in line and "api_key=0" not in line
            data["openai"]["oauth"] = "oauth=" in line and "oauth=0" not in line
            data["openai"]["token"] = "token=" in line and "token=0" not in line
    return data


def channels_status(container):
    result = docker_exec(
        container,
        ["node", "dist/index.js", "channels", "status", "--probe", "--json"],
        timeout=45,
    )
    if not result["ok"]:
        return {
            "ok": False,
            "telegram": channel_absent(),
            "whatsapp": channel_absent(),
            "error": brief_error(result),
        }

    try:
        payload = json.loads(result["stdout"])
    except json.JSONDecodeError as error:
        return {
            "ok": False,
            "telegram": channel_absent(),
            "whatsapp": channel_absent(),
            "error": str(error),
        }

    channels = payload.get("channels") or {}
    accounts = payload.get("channelAccounts") or {}
    return {
        "ok": True,
        "telegram": summarize_channel("telegram", channels.get("telegram"), accounts.get("telegram")),
        "whatsapp": summarize_channel("whatsapp", channels.get("whatsapp"), accounts.get("whatsapp")),
        "eventLoop": payload.get("eventLoop") or {},
        "error": None,
    }


def summarize_channel(name, channel, accounts):
    if not channel:
        return channel_absent()

    account = accounts[0] if isinstance(accounts, list) and accounts else {}
    probe = channel.get("probe") or account.get("probe") or {}
    bot = probe.get("bot") or {}
    summary = {
        "present": True,
        "configured": bool(channel.get("configured")),
        "running": bool(channel.get("running")),
        "connected": coalesce_bool(account.get("connected"), channel.get("connected")),
        "linked": coalesce_bool(channel.get("linked"), account.get("linked")),
        "statusState": channel.get("statusState"),
        "healthState": channel.get("healthState"),
        "lastError": channel.get("lastError") or account.get("lastError"),
        "lastProbeOk": probe.get("ok"),
        "lastConnectedAt": account.get("lastConnectedAt") or channel.get("lastConnectedAt"),
    }
    if name == "telegram":
        summary["username"] = bot.get("username") or (probe.get("botInfo") or {}).get("username")
        summary["tokenSource"] = channel.get("tokenSource") or account.get("tokenSource")
        summary["connected"] = summary["connected"] if summary["connected"] is not None else summary["running"]
    if name == "whatsapp":
        self_info = channel.get("self") or {}
        summary["jid"] = self_info.get("jid")
        summary["e164"] = self_info.get("e164")
    return summary


def channel_absent():
    return {
        "present": False,
        "configured": False,
        "running": False,
        "connected": False,
        "linked": False,
        "statusState": "absent",
        "healthState": "absent",
        "lastError": None,
        "lastProbeOk": None,
        "lastConnectedAt": None,
    }


def coalesce_bool(*values):
    for value in values:
        if isinstance(value, bool):
            return value
    return None


def value_after_colon(line):
    if ":" not in line:
        return None
    value = line.split(":", 1)[1].strip()
    return value or None


def sanitize_model_auth_line(line):
    pieces = []
    for part in line.split("|"):
        stripped = part.strip()
        if "sk-" in stripped:
            stripped = "api_key configured"
        pieces.append(stripped)
    return " | ".join(pieces)


def brief_error(result):
    text = (result.get("stderr") or result.get("stdout") or "").strip()
    if not text:
        return f"exit {result.get('returncode')}"
    return text.splitlines()[-1][:500]


def instance_status(name, cfg, args):
    domain = cfg["domain"]
    container = f"oces-{name}"
    item = {
        "name": name,
        "domain": domain,
        "url": f"https://{domain}",
        "port": cfg["port"],
        "container": container,
        "docker": docker_inspect(container),
        "publicHealth": None,
        "version": None,
        "models": None,
        "channels": None,
    }
    if args.public_health:
        item["publicHealth"] = http_health(domain, args.http_timeout)
    if item["docker"]["exists"] and item["docker"]["running"]:
        item["version"] = openclaw_version(container)
        item["models"] = openclaw_models(container)
        item["channels"] = channels_status(container) if args.channels else None
    return item


def parse_args():
    parser = argparse.ArgumentParser(description="OpenClaw Enterprise Stack status")
    parser.add_argument("--json", action="store_true", help="emit compact JSON")
    parser.add_argument("--pretty", action="store_true", help="emit formatted JSON")
    parser.add_argument("--instance", action="append", default=[], help="filter by instance name")
    parser.add_argument("--no-public-health", dest="public_health", action="store_false")
    parser.add_argument("--no-channels", dest="channels", action="store_false")
    parser.add_argument("--http-timeout", type=float, default=5.0)
    parser.set_defaults(public_health=True, channels=True)
    return parser.parse_args()


def main():
    args = parse_args()
    stack = load_stack()
    selected = set(args.instance)
    instances = []
    for name, cfg in stack["instances"].items():
        if selected and name not in selected:
            continue
        instances.append(instance_status(name, cfg, args))

    payload = {
        "schema": "oces.status.v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "company": stack.get("company") or {},
        "instances": instances,
    }
    if args.json or args.pretty:
        indent = 2 if args.pretty else None
        print(json.dumps(payload, ensure_ascii=False, indent=indent))
    else:
        for item in instances:
            docker = item["docker"]
            health = item.get("publicHealth") or {}
            channels = item.get("channels") or {}
            telegram = (channels.get("telegram") or {}).get("connected")
            whatsapp = (channels.get("whatsapp") or {}).get("connected")
            print(
                f"{item['name']:<12} "
                f"{docker.get('status') or '-':<10} "
                f"{docker.get('health') or '-':<10} "
                f"http={health.get('status') or '-'} "
                f"telegram={format_bool(telegram)} "
                f"whatsapp={format_bool(whatsapp)} "
                f"{item['domain']}"
            )


def format_bool(value):
    if value is True:
        return "on"
    if value is False:
        return "off"
    return "-"


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
