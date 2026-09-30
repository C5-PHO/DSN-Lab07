#!/bin/sh
set -eu

total="${1:-100}"
case "$total" in
  ''|*[!0-9]*) echo "El número de peticiones debe ser entero" >&2; exit 2 ;;
esac

i=0
while [ "$i" -lt "$total" ]; do
  curl --fail --silent http://127.0.0.1:8080/api/instance
  printf '\n'
  i=$((i + 1))
done | sort | uniq -c

