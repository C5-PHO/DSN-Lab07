#!/bin/sh
set -eu

if ! command -v ab >/dev/null 2>&1; then
  echo "Apache Benchmark (ab) no está instalado" >&2
  exit 1
fi

echo "Backend directo (1000 peticiones, concurrencia 50):"
ab -n 1000 -c 50 http://127.0.0.1:8081/api/instance | grep -E 'Requests per second:|Time per request:|Failed requests:'

echo "Nginx (1000 peticiones, concurrencia 50):"
ab -n 1000 -c 50 http://127.0.0.1:8080/api/instance | grep -E 'Requests per second:|Time per request:|Failed requests:'

