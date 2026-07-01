#!/usr/bin/env bash
set -e

BASE="$(cd "$(dirname "$0")/.." && pwd)"

echo "===================================="
echo "Build OpenClaw"
echo "===================================="

docker build \
    -t openclaw:latest \
    "$BASE/vendor/openclaw"

for dir in "$BASE"/instances/*; do
    [ -d "$dir" ] || continue

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