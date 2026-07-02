#!/usr/bin/env bash

echo
echo "========================================="
echo " OpenClaw Enterprise Stack - Doctor"
echo "========================================="
echo

echo "Projeto:"
pwd
echo

echo "Docker:"
if command -v docker >/dev/null 2>&1; then
    docker --version
else
    echo "❌ Docker não instalado"
fi

echo
echo "Docker Compose:"
if docker compose version >/dev/null 2>&1; then
    docker compose version
else
    echo "❌ Docker Compose indisponível"
fi

echo
echo "Python:"
if command -v python3 >/dev/null 2>&1; then
    python3 --version
    if python3 - <<'PY' >/dev/null 2>&1
import jinja2
import yaml
PY
    then
        echo "[OK] Dependências Python"
    else
        echo "❌ Dependências Python ausentes. Rode: python3 -m pip install -r requirements.txt"
    fi
else
    echo "❌ Python 3 não instalado"
fi

echo
echo "Instâncias configuradas:"
if [ -d instances ]; then
    find instances -mindepth 1 -maxdepth 1 -type d | wc -l
else
    echo "0 (rode: python3 scripts/generate.py)"
fi

echo
echo "Templates:"
find templates -type f

echo
echo "Configuração:"
ls config

echo
echo "========================================="
