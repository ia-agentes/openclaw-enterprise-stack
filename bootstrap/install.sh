#!/usr/bin/env bash
set -e

echo "====================================="
echo " OpenClaw Enterprise Stack Installer "
echo "====================================="

bash bootstrap/check.sh
bash bootstrap/directories.sh
bash bootstrap/docker.sh

python3 -m pip install -r requirements.txt

python3 scripts/generate.py

bash bootstrap/traefik.sh

echo
echo "Instalação base concluída."