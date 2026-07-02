#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-list}"
ASSUME_YES=false

if [ "$#" -gt 0 ]; then
    shift
fi

if [ "$ACTION" = "approve" ]; then
    if [ "${1:-}" = "--yes" ]; then
        ASSUME_YES=true
        shift
    fi
fi

if [ "$#" -gt 0 ] || { [ "$ACTION" != "list" ] && [ "$ACTION" != "approve" ]; }; then
    echo "Uso: oces devices {list|approve [--yes]}" >&2
    exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker não encontrado no PATH." >&2
    exit 1
fi

mapfile -t containers < <(
    docker ps \
        --filter "name=oces-" \
        --format "{{.Names}}" |
        grep -v '^oces-traefik$' |
        sort
)

if [ "${#containers[@]}" -eq 0 ]; then
    echo "Nenhuma instância OpenClaw em execução." >&2
    exit 1
fi

pending=()

for container in "${containers[@]}"; do
    while IFS='|' read -r request_id remote_ip scopes; do
        [ -n "$request_id" ] || continue
        instance="${container#oces-}"
        printf '%-14s %-36s %-15s %s\n' \
            "$instance" "$request_id" "${remote_ip:--}" "${scopes:--}"
        pending+=("$container"$'\t'"$request_id")
    done < <(
        docker exec "$container" node -e '
            const fs = require("node:fs");
            const path = "/home/node/.openclaw/devices/pending.json";
            if (!fs.existsSync(path)) process.exit(0);
            const pending = JSON.parse(fs.readFileSync(path, "utf8"));
            const now = Date.now();
            for (const request of Object.values(pending)) {
              if (!request || now - request.ts > 5 * 60 * 1000) continue;
              if (!["openclaw-control-ui", "webchat-ui"].includes(request.clientId)) continue;
              const fields = [
                request.requestId,
                request.remoteIp || "",
                Array.isArray(request.scopes) ? request.scopes.join(",") : "",
              ];
              console.log(fields.map((value) => String(value).replaceAll("|", " ")).join("|"));
            }
        '
    )
done

if [ "${#pending[@]}" -eq 0 ]; then
    echo "Nenhum pedido recente da Control UI está pendente."
    exit 0
fi

if [ "$ACTION" = "list" ]; then
    exit 0
fi

if [ "$ASSUME_YES" != true ]; then
    printf 'Aprovar os %d pedido(s) acima? [y/N] ' "${#pending[@]}"
    read -r answer
    case "$answer" in
        y|Y|yes|YES|sim|SIM) ;;
        *)
            echo "Aprovação cancelada."
            exit 0
            ;;
    esac
fi

failures=0
for item in "${pending[@]}"; do
    IFS=$'\t' read -r container request_id <<< "$item"
    if docker exec "$container" node dist/index.js devices approve "$request_id"; then
        echo "[OK] ${container#oces-}: $request_id"
    else
        echo "[ERRO] ${container#oces-}: $request_id" >&2
        failures=$((failures + 1))
    fi
done

if [ "$failures" -gt 0 ]; then
    echo "$failures aprovação(ões) falharam." >&2
    exit 1
fi
