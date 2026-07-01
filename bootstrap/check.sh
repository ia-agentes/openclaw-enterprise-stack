#!/usr/bin/env bash
set -e

echo "[CHECK] Ubuntu"

grep -q "Ubuntu" /etc/os-release || {
    echo "Ubuntu não encontrado."
    exit 1
}

echo "[OK] Ubuntu"

command -v docker >/dev/null || {
    echo "Docker não instalado."
    exit 1
}

echo "[OK] Docker"

docker compose version >/dev/null || {
    echo "Docker Compose não instalado."
    exit 1
}

echo "[OK] Docker Compose"