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

OPENCLAW_BUILD_CONTEXT="$BASE/vendor/openclaw"
if [ -d "$BASE/.cache/openclaw-update/source" ]; then
    OPENCLAW_BUILD_CONTEXT="$BASE/.cache/openclaw-update/source"
fi

echo "Build context: $OPENCLAW_BUILD_CONTEXT"

docker build \
    --build-arg OPENCLAW_INSTALL_BROWSER=1 \
    -t openclaw:latest \
    "$OPENCLAW_BUILD_CONTEXT"

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
        up -d --force-recreate
done

echo
echo "Deploy concluído."
