# ============================================================================
# Sliver C2 — SERVIDOR (daemon multiplayer)
# Versao FIXADA: v1.5.41 (binario oficial pre-compilado do BishopFox)
#
# Optamos por baixar o binario oficial da release em vez de compilar o tag
# antigo: o codigo-fonte atual do repo ja e uma versao MUITO mais nova
# (toolchain Go/URLs de assets incompativeis), entao compilar a 1.5.41 do
# zero seria fragil. O binario de release ja traz todos os assets embutidos.
# ============================================================================
FROM debian:bookworm-slim

ARG SLIVER_VERSION=v1.5.41
ARG SLIVER_SERVER_SHA256=""

ENV DEBIAN_FRONTEND=noninteractive

# ca-certificates: TLS na hora do download / operacao | curl: baixar o binario
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Usuario nao-root. uid/gid 999 identico no client -> volume /shared compartilhavel.
RUN groupadd -g 999 sliver \
    && useradd -r -u 999 -g sliver -m -d /home/sliver sliver

# Baixa o SERVIDOR oficial da release fixada e valida o checksum SHA-256.
RUN curl -fL --retry 3 -o /opt/sliver-server \
      "https://github.com/BishopFox/sliver/releases/download/${SLIVER_VERSION}/sliver-server_linux" \
    && if [ -n "$SLIVER_SERVER_SHA256" ]; then \
         echo "${SLIVER_SERVER_SHA256}  /opt/sliver-server" | sha256sum -c - ; \
       else echo "AVISO: SLIVER_SERVER_SHA256 vazio -> verificacao de integridade pulada"; fi \
    && chmod 0755 /opt/sliver-server

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# Cria os diretorios com dono 'sliver' ANTES do VOLUME: assim os volumes nomeados
# herdam a permissao correta na primeira montagem (evita "permission denied").
RUN mkdir -p /home/sliver/.sliver /shared \
    && chown -R sliver:sliver /home/sliver /shared \
    && chmod 0770 /shared

USER sliver
WORKDIR /home/sliver

# .sliver  = certs/config/db/implants gerados (persistente)
# /shared  = troca o .cfg do operador com o container do client
VOLUME ["/home/sliver/.sliver", "/shared"]

# 31337 = canal do operador (multiplayer). Portas de listener C2 sao
# publicadas via docker-compose (80/443/8888 por padrao).
EXPOSE 31337

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
