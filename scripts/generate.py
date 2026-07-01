from pathlib import Path
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent

stack = yaml.safe_load(
    (ROOT / "config" / "stack.yml").read_text()
)

defaults = yaml.safe_load(
    (ROOT / "config" / "defaults.yml").read_text()
)

env = Environment(
    loader=FileSystemLoader(ROOT / "templates")
)

compose_template = env.get_template(
    "compose/openclaw-compose.yml.j2"
)

env_template = env.get_template(
    "env/.env.j2"
)

instances_root = ROOT / "instances"

instances_root.mkdir(exist_ok=True)

for instance_name, cfg in stack["instances"].items():

    instance_dir = instances_root / instance_name

    (instance_dir / "data").mkdir(parents=True, exist_ok=True)
    (instance_dir / "data" / ".openclaw").mkdir(exist_ok=True)
    (instance_dir / "data" / "workspace").mkdir(exist_ok=True)
    (instance_dir / "data" / "auth").mkdir(exist_ok=True)

    compose = compose_template.render(
    name=instance_name,
    domain=cfg["domain"],
    image=defaults["image"],
    network=defaults["network"],
    gateway_port=defaults["gateway_port"],
    bridge_port=defaults["bridge_port"],
    msteams_port=defaults["msteams_port"],
    restart=defaults["restart"],
    )

    (instance_dir / "docker-compose.yml").write_text(compose)

    envfile = env_template.render(
        image=defaults["image"],
        timezone=stack["server"]["timezone"],
        gateway_port=defaults["gateway_port"],
        bridge_port=defaults["bridge_port"],
        msteams_port=defaults["msteams_port"],
    )

    (instance_dir / ".env").write_text(envfile)

print()
print("=" * 50)
print("OpenClaw Enterprise Stack")
print("=" * 50)
print()

print(f"{len(stack['instances'])} instâncias geradas.")
print()

for item in stack["instances"]:
    print("✔", item)

print()