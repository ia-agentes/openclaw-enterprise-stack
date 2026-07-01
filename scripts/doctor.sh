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
python3 --version

echo
echo "Instâncias configuradas:"
find instances -mindepth 1 -maxdepth 1 -type d | wc -l

echo
echo "Templates:"
find templates -type f

echo
echo "Configuração:"
ls config

echo
echo "========================================="
