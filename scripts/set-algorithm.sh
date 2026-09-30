#!/bin/sh
set -eu

mode="${1:-}"
case "$mode" in
  round_robin|weighted|least_conn|ip_hash) ;;
  *) echo "Uso: $0 {round_robin|weighted|least_conn|ip_hash}" >&2; exit 2 ;;
esac

docker compose exec -T nginx sh -c "cp /etc/nginx/examples/$mode.conf /etc/nginx/conf.d/default.conf && nginx -t && nginx -s reload"
echo "Algoritmo activo: $mode"

