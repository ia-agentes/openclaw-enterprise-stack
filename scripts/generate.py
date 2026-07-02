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


(ROOT / "proxy" / "config").mkdir(parents=True, exist_ok=True)
write_text_lf(
    ROOT / "proxy" / "docker-compose.yml",
    proxy_compose_template.render(network=network),
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
    if not openclaw_config_path.exists():
        write_text_lf(
            openclaw_config_path,
            openclaw_config_template.render(
                domain=cfg["domain"],
                port=cfg["port"],
            ),
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

    envfile = env_template.render(
        name=instance_name,
        image=defaults["image"],
        timezone=timezone,
        gateway_port=defaults["gateway_port"],
        bridge_port=defaults["bridge_port"],
        msteams_port=defaults["msteams_port"],
        gateway_token=gateway_token,
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
