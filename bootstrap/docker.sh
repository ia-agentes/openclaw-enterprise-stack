#!/usr/bin/env bash
set -e

docker network inspect oces_proxy >/dev/null 2>&1 || \
docker network create oces_proxy

echo "[OK] Rede Docker criada"