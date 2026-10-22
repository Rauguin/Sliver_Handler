<p align="center">
  <img src="caramelo.jpeg" alt="Caramelo Storm" width="160">
</p>

<h1 align="center">Sliver_Handler</h1>

<p align="center">
  <strong>Gerenciador de ambientes Docker para o Sliver C2.</strong><br>
  Mantém várias versões/labs do Sliver isolados — cada sessão é um ambiente Docker
  completo (server + client + volumes próprios) — e troca entre eles com um comando.
</p>

<p align="center">
  <em>Feito por <strong>Avocado</strong> · equipe <strong>Caramelo Storm</strong></em><br>
  <a href="https://www.linkedin.com/in/rafael-raugi/">💼 LinkedIn</a> ·
  <a href="https://www.youtube.com/@avocado-shell">📺 YouTube @avocado-shell</a>
</p>

---

Plataformas como o **HTB Academy** fixam o Sliver em uma versão específica (ex: `v1.5.41`),
enquanto o repositório oficial já está várias releases à frente. Instalar pelo `apt` ou
compilar o `main` quebra a compatibilidade com o lab. O `Sliver_Handler` resolve isso:
cada **sessão** é um par de containers Docker (server + client) com uma **versão fixada**
do Sliver, baixada do binário oficial da release e **verificada por SHA-256**. Você cria
sessões com versões diferentes, troca entre elas e cada uma mantém seus próprios
certificados, config de operador, banco e implantes gerados — **sem conflito**.

> 🔒 **Persistência e isolamento:** cada sessão roda como um Docker Compose project
> separado (`--project-name`) com volumes próprios. Os dados ficam nos volumes Docker
> e os metadados em `~/.sliver-handler/` (fora do repo). Ao deletar uma sessão,
> containers e volumes são removidos juntos.

## O que ele faz

- **Sessões nomeadas** — cada lab/curso/versão num ambiente Docker isolado.
- **Multi-versão** — rode `v1.5.41` para o HTB Academy e `v1.7.8` para outro lab, cada
  um com seus próprios certificados, operadores e implantes.
- **Troca atômica** — `use <nome>` para a sessão atual e sobe a outra.
- **Catálogo de versões** — consulta as releases do Sliver direto do GitHub e marca
  quais têm checksum verificado no catálogo local.

<p align="center">
  <img src="versions.png" alt="Listagem de todas as releases do Sliver com status de checksum" width="720">
  <br><sub><code>versions</code> — consulta a API do GitHub e marca a <code>v1.5.41</code> como <strong>checksum verificado</strong>.</sub>
</p>

- **Integridade** — versões conhecidas são verificadas por SHA-256 durante o build;
  versões novas funcionam mas avisam que não há checksum cadastrado.
- **Dois consoles** — `client` abre o console do operador (`sliver >`), `server`
  abre o console do server (`[server] sliver >`) com comandos de admin como
  `new-operator` e `multiplayer`. `shell` dá bash direto no container para debug.
- **Operadores e acesso externo** — `operator` gera configs com IP auto-detectado ou
  apontando para uma VPS/tunnel. `connect` usa o `.cfg` pra conectar via host network
  sem instalar binário nativo. O server aceita qualquer rota (direto, VPN, VPS).
- **Arquivos acessíveis** — o diretório `/shared` dentro do container é um bind mount
  local (`~/.sliver-handler/sessions/<nome>/shared/`). Configs de operador, implantes
  e qualquer arquivo salvo em `/shared/` aparecem na sua máquina. `grab` copia
  arquivos de qualquer outro caminho do container.
- **Python 3 stdlib** — sem dependências externas, só Docker.

## Como rodar

```bash
cd Sliver_Handler

# Veja as versoes disponiveis (consulta o GitHub)
./Sliver_Handler.py versions

# Crie uma sessao para o lab do HTB (v1.5.41, default)
./Sliver_Handler.py new htb-academy

# Crie outra sessao com versao diferente
./Sliver_Handler.py new lab-novo v1.7.8

# Liste as sessoes (* = ativa)
./Sliver_Handler.py list

# Troque de sessao (para a atual, sobe a outra)
./Sliver_Handler.py use htb-academy

# Abra o console do operador
./Sliver_Handler.py client

# Shell no server (debug, checar certs, gerar operadores)
./Sliver_Handler.py server
```

### Operadores e acesso externo

O `client` padrão conecta via rede Docker interna (hostname `sliver-server`). Para
conectar **de fora** — da sua máquina, de outra na rede ou via VPS — gere um config
com o IP de destino:

```bash
# Acesso local — IP auto-detectado (192.168.1.177)
./Sliver_Handler.py operator raugi

# Acesso via LAN — IP explicito
./Sliver_Handler.py operator raugi --lhost 192.168.1.177

# Acesso via VPS (ela tunela pro seu Kali)
./Sliver_Handler.py operator raugi --lhost 55.55.55.55

# Porta diferente (VPS redireciona 8443 -> 31337)
./Sliver_Handler.py operator raugi --lhost 55.55.55.55 --lport 8443

# Conecta usando o config gerado (via host network, sem Docker interno)
./Sliver_Handler.py connect raugi_192.168.1.177.cfg

# Lista configs disponiveis na sessao
./Sliver_Handler.py connect
```

O `--lhost` é apenas o endereço que o client **usa pra conectar** — não é validado pelo
server. O server aceita qualquer operador com certificado mTLS válido, independente da
rota (direto, VPN, VPS, tunnel). Basta que a porta esteja acessível.

```
 ┌─────────────────────────────────────────────────────────┐
 │                      seu Kali (192.168.1.177)           │
 │  ┌──────────────────────────────────────────────────┐   │
 │  │ Docker                                           │   │
 │  │  server (daemon 0.0.0.0:31337)  ◄─── client     │   │
 │  │       │                          (rede Docker)   │   │
 │  └───────┼──────────────────────────────────────────┘   │
 │          │ porta 31337 publicada no host                 │
 ├──────────┼──────────────────────────────────────────────┤
 │          ▼                                              │
 │   192.168.1.177:31337  ◄────  connect (host network)    │
 │          │                                              │
 └──────────┼──────────────────────────────────────────────┘
            │ (ou via VPS / tunnel)
            ▼
    55.55.55.55:31337  ◄────  operador remoto
```

### Arquivos compartilhados

O diretório `/shared` dentro do container é um **bind mount** para
`~/.sliver-handler/sessions/<nome>/shared/` na sua máquina. Tudo que o server
ou client salvar em `/shared/` aparece localmente — sem `docker cp`.

```bash
# No console do Sliver:
[server] sliver > new-operator --name colega --lhost 192.168.1.177 --save /shared/colega.cfg
[server] sliver > generate --mtls 192.168.1.177:443 --os windows --save /shared/implant.exe

# Na sua maquina:
./Sliver_Handler.py shared          # lista o que tem no shared/
./Sliver_Handler.py grab /home/sliver/.sliver/outro.db .  # copia de QUALQUER lugar do container
```

<p align="center">
  <img src="New.png" alt="Criando uma sessao HTB-Academy com Sliver v1.5.41" width="720">
  <br><sub>Criando a sessão <code>HTB-Academy</code> com Sliver <code>v1.5.41</code> — build + server no ar em um comando.</sub>
</p>

<p align="center">
  <img src="Status.png" alt="Status da sessao ativa mostrando versao, estado e portas" width="720">
  <br><sub>Estado da sessão ativa: versão, server <strong>running</strong>, operador, portas e volumes.</sub>
</p>

<p align="center">
  <img src="Client.png" alt="Console interativo do operador conectado ao Sliver v1.5.41" width="720">
  <br><sub>Console do operador — o client importa o config, conecta e abre o shell do Sliver.</sub>
</p>

<p align="center">
  <img src="Server.png" alt="Shell bash dentro do container do server" width="720">
  <br><sub><code>shell</code> — bash no container do server para debug e checar arquivos.</sub>
</p>

## Comandos

<p align="center">
  <img src="Help.png" alt="Saida do Sliver_Handler.py sem argumentos mostrando todos os comandos" width="720">
  <br><sub>Ajuda do Sliver_Handler (<code>./Sliver_Handler.py</code> sem argumentos ou <code>help</code>).</sub>
</p>

| Comando | Ação |
|---------|------|
| `new <nome> [versao]` (`create`) | Cria sessão com versão do Sliver (default: `v1.5.41`) e sobe |
| `up` (`start`) | Builda (1x) e sobe a sessão ativa |
| `client` (`console`, `c`) | Console interativo do operador na sessão ativa |
| `server` (`srv`, `s`) | Console do server (`[server] sliver >` com `new-operator`, etc.) |
| `shell` (`bash`, `sh`) | Bash no container do server (debug, checar certs) |
| `shared` (`files`) | Lista arquivos compartilhados da sessão (configs, implantes) |
| `grab <path> [dest]` (`cp`) | Copia arquivo do container do server para a máquina |
| `operator <op> [--lhost IP]` (`op`) | Gera config de operador para acesso externo (auto-detecta IP) |
| `connect [cfg]` (`conn`) | Conecta com um `.cfg` específico via host network |
| `use <nome>` (`switch`) | Troca para outra sessão (para a anterior, sobe a nova) |
| `list` (`ls`) | Lista todas as sessões (`*` = ativa) com versão e estado |
| `stop` (`down`) | Para os containers da sessão ativa (volumes preservados) |
| `del <nome>` (`rm`, `delete`) | Remove sessão + containers + volumes |
| `rename <a> <b>` (`mv`) | Renomeia uma sessão |
| `status` (`st`) | Estado detalhado da sessão ativa |
| `logs` (`log`) | Logs do server ativo (`Ctrl+C` sai) |
| `reset` (`nuke`) | Zera volumes da sessão ativa (lab do zero, pede confirmação) |
| `versions` (`ver`) | Lista releases do Sliver (GitHub + catálogo local) |
| `config` (`env`) | Mostra config (`.env`) da sessão ativa |
| `help` | Ajuda |

## Requisitos

- **Docker** com o plugin **Compose v2**: `sudo apt install docker.io docker-compose-plugin`
- Usuário no grupo `docker`: `sudo usermod -aG docker $USER` (ou rode com `sudo`)
- **Python 3** (stdlib apenas — **sem dependências externas**)
- Arquitetura **x86-64** (a release `v1.5.41` só publica binário Linux amd64)

## Como funciona (resumo técnico)

1. **Sessão = Docker Compose project** — cada sessão roda com `--project-name sliver-<nome>`
   e `--env-file` próprio, gerando containers e volumes isolados automaticamente.
2. **Versão fixada por binário oficial** — os Dockerfiles baixam o `sliver-server_linux` e
   `sliver-client_linux` da release no GitHub e verificam o SHA-256 no build.
3. **Catálogo de versões** — checksums conhecidos ficam hardcoded no script; versões extras
   podem ser adicionadas em `~/.sliver-handler/versions.json`. O comando `versions` consulta
   a API do GitHub para listar todas as releases disponíveis.
4. **Server entrypoint** — na primeira execução, descompacta os assets embutidos no binário
   (`unpack`), gera o config do operador padrão e sobe o daemon multiplayer. O client espera
   o config aparecer em `/shared`, importa e conecta.
5. **Bind mount `/shared`** — cada sessão tem um diretório local
   (`~/.sliver-handler/sessions/<nome>/shared/`) montado em `/shared` nos containers.
   Configs de operador, implantes e qualquer arquivo salvo lá aparecem na máquina host.
6. **Operador + connect** — `operator` gera configs com IP externo (auto-detectado ou
   via `--lhost`). `connect` roda o client Docker com `--network host`, importa o `.cfg`
   e conecta pelo IP real — sem instalar binário nativo.
7. **Uma sessão por vez** — ao trocar (`use`), a sessão atual para antes da nova subir,
   evitando conflito de portas.

## Portas / listeners C2

| Porta | Uso |
|-------|-----|
| `31337` | Canal do operador (multiplayer) |
| `80` | Listener C2 HTTP |
| `443` | Listener C2 HTTPS / mTLS |
| `8888` | Listener C2 extra |

Todas publicadas no host. Ao criar um listener no console (`mtls`, `http`, `https`),
use uma dessas portas para que o implante alcance o server de fora do Docker.

## Estrutura

```
Sliver_Handler.py              gerenciador (Python 3, stdlib)
docker/
  ├── docker-compose.yml       orquestra server + client
  ├── server/
  │   ├── Dockerfile           baixa sliver-server da release (+ SHA-256)
  │   └── entrypoint.sh        unpack → gera config → daemon
  └── client/
      ├── Dockerfile           baixa sliver-client da release (+ SHA-256)
      └── entrypoint.sh        espera config → import → console

~/.sliver-handler/             (criado em runtime; NÃO versionado)
  ├── active                   nome da sessão ativa
  ├── versions.json            versões extras (opcional)
  └── sessions/<nome>/
      ├── meta.json            nome, versão, timestamps
      ├── .env                 config do docker compose da sessão
      └── shared/              bind mount do /shared (configs, implantes)
```

## Aviso

Ferramenta de apoio a **operações ofensivas autorizadas** e **labs de estudo**.
O Sliver C2 é um projeto GPLv3 do BishopFox — esta ferramenta apenas orquestra
a execução em containers Docker. Você é responsável pelo uso.

## Licença

[MIT](LICENSE) — uso autorizado apenas em assessments com autorização por escrito
e em ambientes de laboratório/estudo.

---

<p align="center">
  <sub>⚡ <strong>Caramelo Storm</strong> ·
  <a href="https://www.linkedin.com/in/rafael-raugi/">LinkedIn</a> ·
  <a href="https://www.youtube.com/@avocado-shell">YouTube @avocado-shell</a></sub>
</p>
