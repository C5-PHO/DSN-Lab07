#!/bin/sh
set -eu

echo "Salud de cada backend:"
for port in 8081 8082 8083; do
  curl --fail --silent "http://127.0.0.1:$port/health"
  printf '\n'
done

echo "Balanceo Round Robin:"
./scripts/count-distribution.sh 12

echo "Origen del formulario a través de Nginx:"
status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --header 'Origin: http://127.0.0.1:8080' \
  --header 'Content-Type: application/json' \
  --data '{"email":"invalid@example.com","password":"invalid"}' \
  http://127.0.0.1:8080/api/login)
if [ "$status" != 401 ]; then
  echo "Login por 8080 devolvió HTTP $status; se esperaba 401 para credenciales inválidas" >&2
  exit 1
fi
echo "OK: el origen se conserva (HTTP 401 por credenciales inválidas)"
