#!/bin/sh
set -eu

echo "Salud de cada backend:"
for port in 8081 8082 8083; do
  curl --fail --silent "http://127.0.0.1:$port/health"
  printf '\n'
done

echo "Balanceo Round Robin:"
./scripts/count-distribution.sh 12

