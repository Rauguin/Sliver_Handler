#!/bin/bash
# ============================================================================
# Entrypoint do CLIENTE Sliver (v1.5.41)
#   espera o config do operador aparecer no /shared, importa e conecta.
#   Sem args -> abre o console interativo.
#   Com args -> executa como subcomando (ex: docker compose run client version)
# ============================================================================
set -euo pipefail

OPERATOR_NAME="${OPERATOR_NAME:-neo}"
SERVER_HOST="${SERVER_HOST:-sliver-server}"
OP_CFG="/shared/${OPERATOR_NAME}_${SERVER_HOST}.cfg"

echo "[*] Aguardando o config do operador em ${OP_CFG} ..."
for _ in $(seq 1 60); do
  [ -f "${OP_CFG}" ] && break
  sleep 2
done
if [ ! -f "${OP_CFG}" ]; then
  echo "[!] Config do operador nao apareceu em 120s."
  echo "    O server subiu?  ->  docker compose up -d server"
  exit 1
fi

# Importa o config (idempotente; reimportar apenas atualiza).
echo "[*] Importando config do operador..."
/usr/local/bin/sliver-client import "${OP_CFG}"

if [ "$#" -gt 0 ]; then
  exec /usr/local/bin/sliver-client "$@"
fi

echo "[*] Conectando ao server ${SERVER_HOST} ..."
exec /usr/local/bin/sliver-client
