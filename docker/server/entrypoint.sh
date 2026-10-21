#!/bin/bash
# ============================================================================
# Entrypoint do SERVIDOR Sliver (v1.5.41)
#   1) descompacta os assets embutidos (1x)
#   2) gera o config do operador p/ o client (grava no volume /shared)
#   3) sobe o daemon multiplayer em foreground
# ============================================================================
set -euo pipefail

OPERATOR_NAME="${OPERATOR_NAME:-neo}"
SERVER_HOST="${SERVER_HOST:-sliver-server}"
OPERATOR_LPORT="${OPERATOR_LPORT:-31337}"

SLIVER_ROOT="${HOME}/.sliver"
SHARED_DIR="/shared"
STAMP="${SLIVER_ROOT}/.unpacked"
OP_CFG="${SHARED_DIR}/${OPERATOR_NAME}_${SERVER_HOST}.cfg"

mkdir -p "${SLIVER_ROOT}" "${SHARED_DIR}"

# 1) Descompacta os assets embutidos no binario (Go toolchain, garble, etc.).
#    Vao para ~/.sliver (que e volume), por isso o marcador de "ja descompactado".
if [ ! -f "${STAMP}" ]; then
  echo "[*] Primeira execucao: descompactando assets do Sliver (pode demorar)..."
  /opt/sliver-server unpack --force
  touch "${STAMP}"
fi

# 2) Gera o config do operador para o client.
#    O comando 'operator' ja roda certs.SetupCAs() internamente, entao pode
#    rodar antes do daemon sem problema. lhost = como o client alcanca o server.
if [ ! -f "${OP_CFG}" ]; then
  echo "[*] Gerando config do operador '${OPERATOR_NAME}' (lhost=${SERVER_HOST} lport=${OPERATOR_LPORT})..."
  /opt/sliver-server operator \
      --name  "${OPERATOR_NAME}" \
      --lhost "${SERVER_HOST}" \
      --lport "${OPERATOR_LPORT}" \
      --save  "${OP_CFG}"
  echo "[+] Config salvo em ${OP_CFG} (compartilhado com o client)"
else
  echo "[=] Config do operador ja existe em ${OP_CFG}"
fi

# 3) Sobe o daemon multiplayer em foreground (0.0.0.0 p/ o client alcancar).
echo "[*] Subindo o daemon do Sliver em 0.0.0.0:${OPERATOR_LPORT} ..."
exec /opt/sliver-server daemon --lhost 0.0.0.0 --lport "${OPERATOR_LPORT}"
