#!/usr/bin/env bash
set -e

BASE="$(cd "$(dirname "$0")/.." && pwd)"

NETWORK="${OCES_NETWORK:-}"
NETWORK_SUBNET="${OCES_NETWORK_SUBNET:-}"
if [ -z "$NETWORK" ] && command -v python3 >/dev/null 2>&1; then
    NETWORK="$(
        cd "$BASE"
        python3 - <<'PY' 2>/dev/null || true
from pathlib import Path
import yaml

stack = yaml.safe_load(Path("config/stack.yml").read_text(encoding="utf-8")) or {}
defaults = yaml.safe_load(Path("config/defaults.yml").read_text(encoding="utf-8")) or {}
print(stack.get("proxy", {}).get("network") or defaults.get("network") or "")
PY
    )"
fi

if [ -z "$NETWORK_SUBNET" ] && command -v python3 >/dev/null 2>&1; then
    NETWORK_SUBNET="$(
        cd "$BASE"
        python3 - <<'PY' 2>/dev/null || true
from pathlib import Path
import yaml

stack = yaml.safe_load(Path("config/stack.yml").read_text(encoding="utf-8")) or {}
print(stack.get("proxy", {}).get("subnet") or "")
PY
    )"
fi

NETWORK="${NETWORK:-oces_proxy}"

network_args=()
if [ -n "$NETWORK_SUBNET" ]; then
    network_args+=(--subnet "$NETWORK_SUBNET")
fi

docker network inspect "$NETWORK" >/dev/null 2>&1 || \
docker network create "${network_args[@]}" "$NETWORK"

echo "[OK] Rede Docker pronta: $NETWORK"
