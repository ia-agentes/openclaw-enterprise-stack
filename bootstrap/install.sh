#!/usr/bin/env bash
set -e

echo "====================================="
echo " OpenClaw Enterprise Stack Installer "
echo "====================================="

bash bootstrap/check.sh
bash bootstrap/directories.sh

if python3 - <<'PY' >/dev/null 2>&1
import jinja2
import yaml
PY
then
    echo "[OK] Dependências Python já instaladas"
elif python3 -m pip --version >/dev/null 2>&1; then
    python3 -m pip install -r requirements.txt
else
    echo "Dependências Python ausentes e pip indisponível." >&2
    echo "Instale python3-pip ou os pacotes python3-yaml e python3-jinja2." >&2
    exit 1
fi

python3 scripts/generate.py

bash bootstrap/docker.sh
bash bootstrap/traefik.sh

echo
echo "Instalação base concluída."
