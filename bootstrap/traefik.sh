#!/usr/bin/env bash
set -e

echo "[INFO] Instalando Traefik..."

mkdir -p /opt/oces/proxy

cp proxy/docker-compose.yml /opt/oces/proxy/

mkdir -p /opt/oces/proxy/config
mkdir -p /opt/oces/proxy/dynamic
mkdir -p /opt/oces/proxy/logs
mkdir -p /opt/oces/proxy/letsencrypt

cp proxy/config/traefik.yml /opt/oces/proxy/config/
cp proxy/dynamic/security.yml /opt/oces/proxy/dynamic/

touch /opt/oces/proxy/letsencrypt/acme.json

chmod 600 /opt/oces/proxy/letsencrypt/acme.json

cd /opt/oces/proxy

docker compose pull

docker compose up -d

echo "[OK] Traefik iniciado."