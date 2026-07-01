#!/usr/bin/env bash
set -e

BASE=/opt/oces

mkdir -p $BASE

mkdir -p $BASE/proxy/config
mkdir -p $BASE/proxy/dynamic
mkdir -p $BASE/proxy/letsencrypt
mkdir -p $BASE/proxy/logs

mkdir -p $BASE/instances

touch $BASE/proxy/letsencrypt/acme.json

chmod 600 $BASE/proxy/letsencrypt/acme.json

echo "[OK] Diretórios criados"