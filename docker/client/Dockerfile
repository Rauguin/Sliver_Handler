# ============================================================================
# Sliver C2 — CLIENTE (console do operador)
# Versao FIXADA: v1.5.41 (binario oficial pre-compilado do BishopFox)
# ============================================================================
FROM debian:bookworm-slim

ARG SLIVER_VERSION=v1.5.41
ARG SLIVER_CLIENT_SHA256=""

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Mesmo uid/gid 999 do server para compartilhar o volume /shared sem conflito.
RUN groupadd -g 999 sliver \
    && useradd -r -u 999 -g sliver -m -d /home/sliver sliver

# Baixa o CLIENTE oficial da release fixada e valida o checksum SHA-256.
RUN curl -fL --retry 3 -o /usr/local/bin/sliver-client \
      "https://github.com/BishopFox/sliver/releases/download/${SLIVER_VERSION}/sliver-client_linux" \
    && if [ -n "$SLIVER_CLIENT_SHA256" ]; then \
         echo "${SLIVER_CLIENT_SHA256}  /usr/local/bin/sliver-client" | sha256sum -c - ; \
       else echo "AVISO: SLIVER_CLIENT_SHA256 vazio -> verificacao de integridade pulada"; fi \
    && chmod 0755 /usr/local/bin/sliver-client

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# .sliver-client guarda os configs importados (persistente).
RUN mkdir -p /home/sliver/.sliver-client /shared \
    && chown -R sliver:sliver /home/sliver /shared

USER sliver
WORKDIR /home/sliver
VOLUME ["/home/sliver/.sliver-client"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
