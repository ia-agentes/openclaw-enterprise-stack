from pathlib import Path
import yaml
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent

cfg = yaml.safe_load((ROOT / "config" / "stack.yml").read_text())

env = Environment(
    loader=FileSystemLoader(ROOT / "templates")
)

compose_tpl = env.get_template("compose/openclaw-compose.yml.j2")
env_tpl = env.get_template("env/.env.j2")

image = "ghcr.io/openclaw/openclaw:latest"

for name, item in cfg["instances"].items():

    target = ROOT / "instances" / name

    target.mkdir(parents=True, exist_ok=True)

    (target / "workspace").mkdir(exist_ok=True)

    compose = compose_tpl.render(
        name=name,
        domain=item["domain"],
        internal_port=3000,
        image=image
    )

    (target / "docker-compose.yml").write_text(compose)

    envfile = env_tpl.render(
        timezone=cfg["server"]["timezone"],
        internal_port=3000
    )

    (target / ".env").write_text(envfile)

print("Instâncias geradas com sucesso.")