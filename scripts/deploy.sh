#!/usr/bin/env bash
set -e

BASE="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker não encontrado no PATH." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose não está disponível." >&2
    exit 1
fi

if ! compgen -G "$BASE/instances/*/docker-compose.yml" >/dev/null; then
    echo "Nenhuma instância gerada. Rode: python3 scripts/generate.py" >&2
    exit 1
fi

echo "===================================="
echo "Build OpenClaw"
echo "===================================="

docker build \
    -t openclaw:latest \
    "$BASE/vendor/openclaw"

for dir in "$BASE"/instances/*; do
    [ -d "$dir" ] || continue
    [ -f "$dir/docker-compose.yml" ] || continue

    docker run --rm \
        --user root \
        --entrypoint chown \
        -v "$dir/data:/data" \
        openclaw:latest \
        -R node:node /data

    echo
    echo "===================================="
    echo "Deploy $(basename "$dir")"
    echo "===================================="

    docker compose \
        -f "$dir/docker-compose.yml" \
        --env-file "$dir/.env" \
        up -d
done

echo
echo "Deploy concluído."
