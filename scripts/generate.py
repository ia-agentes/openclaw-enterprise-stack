import ipaddress
import json
from pathlib import Path
import secrets
import sys

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent

stack = yaml.safe_load(
    (ROOT / "config" / "stack.yml").read_text(encoding="utf-8")
)

defaults = yaml.safe_load(
    (ROOT / "config" / "defaults.yml").read_text(encoding="utf-8")
)

env = Environment(
    loader=FileSystemLoader(ROOT / "templates"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)

compose_template = env.get_template(
    "compose/openclaw-compose.yml.j2"
)

env_template = env.get_template(
    "env/.env.j2"
)

proxy_compose_template = env.get_template(
    "proxy/docker-compose.yml.j2"
)

traefik_template = env.get_template(
    "proxy/traefik.yml.j2"
)

openclaw_config_template = env.get_template(
    "config/openclaw.json.j2"
)

instances_root = ROOT / "instances"

instances_root.mkdir(exist_ok=True)

required_defaults = ("image", "gateway_port", "bridge_port", "msteams_port", "network", "restart")
missing_defaults = [key for key in required_defaults if key not in defaults]
if missing_defaults:
    sys.exit(f"config/defaults.yml sem chave obrigatória: {', '.join(missing_defaults)}")

if "instances" not in stack or not isinstance(stack["instances"], dict) or not stack["instances"]:
    sys.exit("config/stack.yml precisa declarar ao menos uma instância em 'instances'.")

timezone = stack.get("server", {}).get("timezone", "UTC")
network = stack.get("proxy", {}).get("network", defaults["network"])
proxy_subnet_raw = stack.get("proxy", {}).get("subnet")
trusted_proxy_ip_raw = stack.get("proxy", {}).get("trusted_ip")
if not proxy_subnet_raw or not trusted_proxy_ip_raw:
    sys.exit("config/stack.yml precisa declarar proxy.subnet e proxy.trusted_ip.")

try:
    proxy_subnet = ipaddress.ip_network(proxy_subnet_raw)
    trusted_proxy_ip = ipaddress.ip_address(trusted_proxy_ip_raw)
except ValueError as error:
    sys.exit(f"Configuração de rede do proxy inválida: {error}")

if proxy_subnet.version != 4 or trusted_proxy_ip.version != 4:
    sys.exit("proxy.subnet e proxy.trusted_ip precisam usar IPv4.")

if trusted_proxy_ip not in proxy_subnet:
    sys.exit("proxy.trusted_ip precisa pertencer a proxy.subnet.")

if trusted_proxy_ip in (proxy_subnet.network_address, proxy_subnet.broadcast_address):
    sys.exit("proxy.trusted_ip não pode ser o endereço de rede ou broadcast.")

ssl_email = stack.get("ssl", {}).get("email")
if not ssl_email:
    sys.exit("config/stack.yml precisa declarar ssl.email para o Let's Encrypt.")

seen_ports = {}
seen_domains = {}


def read_env_value(path, key):
    if not path.exists():
        return None

    prefix = f"{key}="
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            value = line[len(prefix):].strip()
            return value or None
    return None


def write_text_lf(path, content):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_openclaw_config(path, domain, port):
    if not path.exists():
        write_text_lf(
            path,
            openclaw_config_template.render(
                domain=domain,
                port=port,
                trusted_proxy_ip=trusted_proxy_ip,
            ),
        )
        return

    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        sys.exit(f"Configuração OpenClaw inválida em {path}: {error}")

    if not isinstance(config, dict):
        sys.exit(f"Configuração OpenClaw precisa ser um objeto JSON: {path}")

    gateway = config.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        sys.exit(f"gateway precisa ser um objeto JSON: {path}")

    gateway["trustedProxies"] = [str(trusted_proxy_ip)]

    control_ui = gateway.setdefault("controlUi", {})
    if not isinstance(control_ui, dict):
        sys.exit(f"gateway.controlUi precisa ser um objeto JSON: {path}")

    existing_origins = control_ui.get("allowedOrigins", [])
    if not isinstance(existing_origins, list) or not all(
        isinstance(origin, str) for origin in existing_origins
    ):
        sys.exit(f"gateway.controlUi.allowedOrigins precisa ser uma lista: {path}")

    required_origins = [
        f"https://{domain}",
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]
    control_ui["allowedOrigins"] = list(
        dict.fromkeys(required_origins + existing_origins)
    )

    write_text_lf(path, json.dumps(config, indent=2) + "\n")


(ROOT / "proxy" / "config").mkdir(parents=True, exist_ok=True)
write_text_lf(
    ROOT / "proxy" / "docker-compose.yml",
    proxy_compose_template.render(
        network=network,
        trusted_proxy_ip=trusted_proxy_ip,
    ),
)
write_text_lf(
    ROOT / "proxy" / "config" / "traefik.yml",
    traefik_template.render(network=network, email=ssl_email),
)

for instance_name, cfg in stack["instances"].items():
    for key in ("domain", "port"):
        if key not in cfg:
            sys.exit(f"Instância '{instance_name}' sem chave obrigatória: {key}")

    if cfg["port"] in seen_ports:
        sys.exit(
            f"Porta duplicada em config/stack.yml: {cfg['port']} "
            f"({seen_ports[cfg['port']]} e {instance_name})"
        )
    seen_ports[cfg["port"]] = instance_name

    if cfg["domain"] in seen_domains:
        sys.exit(
            f"Domínio duplicado em config/stack.yml: {cfg['domain']} "
            f"({seen_domains[cfg['domain']]} e {instance_name})"
        )
    seen_domains[cfg["domain"]] = instance_name

    instance_dir = instances_root / instance_name

    (instance_dir / "data").mkdir(parents=True, exist_ok=True)
    (instance_dir / "data" / ".openclaw").mkdir(exist_ok=True)
    (instance_dir / "data" / "workspace").mkdir(exist_ok=True)
    (instance_dir / "data" / "auth").mkdir(exist_ok=True)

    openclaw_config_path = instance_dir / "data" / ".openclaw" / "openclaw.json"
    write_openclaw_config(
        openclaw_config_path,
        domain=cfg["domain"],
        port=cfg["port"],
    )

    compose = compose_template.render(
        name=instance_name,
        domain=cfg["domain"],
        port=cfg["port"],
        image=defaults["image"],
        network=network,
        gateway_port=defaults["gateway_port"],
        bridge_port=defaults["bridge_port"],
        msteams_port=defaults["msteams_port"],
        restart=defaults["restart"],
    )

    write_text_lf(instance_dir / "docker-compose.yml", compose)

    env_path = instance_dir / ".env"
    gateway_token = (
        read_env_value(env_path, "OPENCLAW_GATEWAY_TOKEN")
        or secrets.token_urlsafe(48)
    )
    openai_api_key = read_env_value(env_path, "OPENAI_API_KEY") or ""
    telegram_bot_token = read_env_value(env_path, "TELEGRAM_BOT_TOKEN") or ""
    telegram_expected_user = read_env_value(env_path, "TELEGRAM_EXPECTED_USER") or ""

    envfile = env_template.render(
        name=instance_name,
        image=defaults["image"],
        timezone=timezone,
        gateway_port=defaults["gateway_port"],
        bridge_port=defaults["bridge_port"],
        msteams_port=defaults["msteams_port"],
        gateway_token=gateway_token,
        openai_api_key=openai_api_key,
        telegram_bot_token=telegram_bot_token,
        telegram_expected_user=telegram_expected_user,
    )

    write_text_lf(env_path, envfile)

print()
print("=" * 50)
print("OpenClaw Enterprise Stack")
print("=" * 50)
print()

print(f"{len(stack['instances'])} instancias geradas.")
print()

for item in stack["instances"]:
    print("[OK]", item)

print()
