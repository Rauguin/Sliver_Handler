#!/usr/bin/env python3
"""
Sliver_Handler - gerenciador de ambientes Docker para o Sliver C2.

Cada "sessao" e um ambiente isolado (server + client Docker) com uma versao
especifica do Sliver, volumes proprios e config independente. Permite manter
varios labs/versoes separados e trocar entre eles.

Uso:
  Sliver_Handler.py                        # sem argumento: mostra esta ajuda
  Sliver_Handler.py new   <nome> [versao]  # cria sessao com versao (default: v1.5.41)
  Sliver_Handler.py up                     # builda (1x) e sobe a sessao ativa
  Sliver_Handler.py client                 # console interativo do operador
  Sliver_Handler.py server                 # shell no container do server
  Sliver_Handler.py use   <nome>           # troca para outra sessao (para a anterior)
  Sliver_Handler.py list                   # lista todas as sessoes (* = ativa)
  Sliver_Handler.py stop                   # para a sessao ativa
  Sliver_Handler.py del   <nome>           # remove sessao + containers + volumes
  Sliver_Handler.py rename <a> <b>         # renomeia uma sessao
  Sliver_Handler.py status                 # estado da sessao ativa
  Sliver_Handler.py logs                   # logs do server ativo (Ctrl+C sai)
  Sliver_Handler.py reset                  # zera volumes da sessao ativa (lab do zero)
  Sliver_Handler.py versions               # versoes do Sliver disponiveis
  Sliver_Handler.py config                 # mostra config da sessao ativa

Requer: Docker com o plugin compose (docker compose).
Dados das sessoes ficam em ~/.sliver-handler/ (fora do repo).
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------- cores / output
R, B   = "\033[0m", "\033[1m"
RED    = "\033[1;31m"
GRN    = "\033[1;32m"
YLW    = "\033[1;33m"
CYN    = "\033[1;36m"


def info(msg): print(f"{GRN}[*]{R} {msg}")
def warn(msg): print(f"{YLW}[!]{R} {msg}")
def err(msg):  print(f"{RED}[x]{R} {msg}", file=sys.stderr)


# ---------------------------------------------------------- catalogo de versoes
BUILTIN_VERSIONS = {
    "v1.5.41": {
        "server_sha256": "ce75590d1d79bc808d98b70ec03355d1117ca54c3b49b6ba474aa704ea9a6c2e",
        "client_sha256": "afeb282bb991650ada2e73c65ed5a1770e1a3bc415b2e1e07462b854c077c93d",
        "notes": "Labs HTB Academy (C2, AEN). Release estavel e verificada.",
    },
}
DEFAULT_VERSION = "v1.5.41"


# ---------------------------------------------------------- caminhos
SCRIPT_DIR   = Path(__file__).resolve().parent
COMPOSE_FILE = SCRIPT_DIR / "docker" / "docker-compose.yml"

BASE_DIR   = Path.home() / ".sliver-handler"
SESS_DIR   = BASE_DIR / "sessions"
ACTIVE_F   = BASE_DIR / "active"
CUSTOM_VER = BASE_DIR / "versions.json"


# ---------------------------------------------------------- init / prereqs
def init_paths():
    SESS_DIR.mkdir(parents=True, exist_ok=True)


def check_prereqs():
    if not COMPOSE_FILE.exists():
        err(f"docker-compose.yml nao encontrado em {COMPOSE_FILE}")
        sys.exit(1)
    if subprocess.run(["docker", "info"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        err("Docker nao acessivel. Verifique se o daemon esta rodando e suas permissoes.")
        sys.exit(1)
    if subprocess.run(["docker", "compose", "version"],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
        err("Plugin 'docker compose' nao encontrado. Instale: apt install docker-compose-plugin")
        sys.exit(1)


# ---------------------------------------------------------- versoes
def all_versions():
    versions = dict(BUILTIN_VERSIONS)
    if CUSTOM_VER.exists():
        try:
            versions.update(json.loads(CUSTOM_VER.read_text()))
        except (json.JSONDecodeError, OSError):
            pass
    return versions


def version_info(tag):
    return all_versions().get(tag, {})


# ---------------------------------------------------------- sessoes
def valid_name(name):
    return bool(name) and "/" not in name and not name.startswith(".")


def session_path(name):
    return SESS_DIR / name


def active_session():
    if ACTIVE_F.exists():
        return ACTIVE_F.read_text().strip() or None
    return None


def set_active(name):
    if name is None:
        ACTIVE_F.unlink(missing_ok=True)
    else:
        ACTIVE_F.write_text(name)


def require_active():
    name = active_session()
    if not name:
        err("Nenhuma sessao ativa. Crie com: Sliver_Handler.py new <nome>")
        sys.exit(1)
    if not session_path(name).exists():
        err(f"Sessao ativa '{name}' nao existe mais. Use 'list' e 'use <outra>'.")
        set_active(None)
        sys.exit(1)
    return name


def project_name(session):
    return f"sliver-{session.lower()}"


def read_meta(name):
    f = session_path(name) / "meta.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def write_meta(name, **fields):
    sp = session_path(name)
    sp.mkdir(parents=True, exist_ok=True)
    meta = read_meta(name)
    meta.update(fields)
    meta["updated"] = datetime.now().isoformat(timespec="seconds")
    (sp / "meta.json").write_text(json.dumps(meta, indent=2))


def generate_env(name, version, operator="neo"):
    vi = version_info(version)
    sp = session_path(name)
    sp.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Sessao: {name} | Sliver {version}",
        f"SLIVER_VERSION={version}",
        f"SLIVER_SERVER_SHA256={vi.get('server_sha256', '')}",
        f"SLIVER_CLIENT_SHA256={vi.get('client_sha256', '')}",
        f"OPERATOR_NAME={operator}",
        f"SERVER_HOST=sliver-server",
        f"OPERATOR_LPORT=31337",
    ]
    (sp / ".env").write_text("\n".join(lines) + "\n")


def load_session_env(name):
    env = {}
    f = session_path(name) / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


# ---------------------------------------------------------- docker compose
def dc(session, *args, **kw):
    env_file = str(session_path(session) / ".env")
    cmd = ["docker", "compose",
           "-f", str(COMPOSE_FILE),
           "--project-name", project_name(session),
           "--env-file", env_file,
           *args]
    return subprocess.run(cmd, **kw)


def dc_out(session, *args):
    p = dc(session, *args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    return p.stdout.strip()


def container_state(session, service):
    raw = dc_out(session, "ps", "--format", "{{.State}}", service)
    return raw.splitlines()[0].lower() if raw else "not_found"


def session_running(name):
    return container_state(name, "server") == "running"


def stop_session(name):
    if session_running(name):
        info(f"Parando sessao '{name}'...")
        dc(name, "down")


# ---------------------------------------------------------- comandos
def cmd_new(args):
    if not args or not valid_name(args[0]):
        err("uso: Sliver_Handler.py new <nome> [versao]")
        err(f"     versao padrao: {DEFAULT_VERSION}")
        err(f"     conhecidas: {', '.join(all_versions().keys())}")
        sys.exit(1)
    name = args[0]
    version = args[1] if len(args) > 1 else DEFAULT_VERSION
    if session_path(name).exists():
        err(f"Sessao '{name}' ja existe. Use outro nome ou 'del {name}' primeiro.")
        sys.exit(1)

    vi = version_info(version)
    if not vi:
        warn(f"Versao '{version}' nao esta no catalogo (checksums desconhecidos).")
        warn("O build vai prosseguir SEM verificacao de integridade.")

    old = active_session()
    if old and session_running(old):
        stop_session(old)

    info(f"Criando sessao '{name}' com Sliver {version}...")
    generate_env(name, version)
    write_meta(name, version=version,
               created=datetime.now().isoformat(timespec="seconds"))
    set_active(name)

    info("Buildando e subindo o server (primeira vez pode demorar)...")
    r = dc(name, "up", "-d", "--build", "server")
    if r.returncode != 0:
        err("Falha no build/start. Verifique os logs com: Sliver_Handler.py logs")
        sys.exit(1)
    print()
    info(f"Sessao '{name}' criada e ativa (Sliver {version})")
    info(f"Console:  {B}Sliver_Handler.py client{R}")


def cmd_up(args):
    name = require_active()
    old = active_session()
    if old and old != name and session_running(old):
        stop_session(old)

    env = load_session_env(name)
    info(f"Subindo sessao '{name}' (Sliver {env.get('SLIVER_VERSION', '?')})...")
    r = dc(name, "up", "-d", "--build", "server")
    if r.returncode != 0:
        err("Falha ao subir. Verifique: Sliver_Handler.py logs")
        sys.exit(1)
    print()
    info(f"Server no ar  |  sessao: {CYN}{name}{R}  |  Sliver {env.get('SLIVER_VERSION', '?')}")
    info(f"Console:  {B}Sliver_Handler.py client{R}")
    info(f"Logs:     {B}Sliver_Handler.py logs{R}")


def cmd_client(args):
    name = require_active()
    if not session_running(name):
        warn("Server nao esta rodando. Subindo...")
        cmd_up([])
        print()
    env_file = str(session_path(name) / ".env")
    meta = read_meta(name)
    info(f"Console — sessao '{name}' (Sliver {meta.get('version', '?')})")
    info("Ctrl+D ou 'exit' para sair")
    os.execvp("docker", ["docker", "compose",
                          "-f", str(COMPOSE_FILE),
                          "--project-name", project_name(name),
                          "--env-file", env_file,
                          "run", "--rm", "client"])


def cmd_server(args):
    name = require_active()
    if not session_running(name):
        warn("Server nao esta rodando. Subindo...")
        cmd_up([])
        print()
    env_file = str(session_path(name) / ".env")
    info(f"Shell no server — sessao '{name}'")
    os.execvp("docker", ["docker", "compose",
                          "-f", str(COMPOSE_FILE),
                          "--project-name", project_name(name),
                          "--env-file", env_file,
                          "exec", "server", "/bin/bash"])


def cmd_use(args):
    if not args:
        err("uso: Sliver_Handler.py use <nome>")
        sys.exit(1)
    name = args[0]
    if not session_path(name).exists():
        err(f"Sessao '{name}' nao existe. Veja 'list'.")
        sys.exit(1)
    if active_session() == name and session_running(name):
        info(f"'{name}' ja e a sessao ativa e esta rodando.")
        return

    old = active_session()
    if old and old != name and session_running(old):
        stop_session(old)

    set_active(name)
    env = load_session_env(name)
    info(f"Sessao ativa: {CYN}{name}{R} (Sliver {env.get('SLIVER_VERSION', '?')})")

    info("Subindo...")
    r = dc(name, "up", "-d", "--build", "server")
    if r.returncode != 0:
        err("Falha ao subir. Verifique: Sliver_Handler.py logs")
        sys.exit(1)
    print()
    info(f"Pronta. Console:  {B}Sliver_Handler.py client{R}")


def cmd_list(args):
    act = active_session()
    names = sorted(p.name for p in SESS_DIR.iterdir() if p.is_dir())
    if not names:
        info("Nenhuma sessao. Crie com:  Sliver_Handler.py new <nome> [versao]")
        return
    print(f"\n{B}Sessoes Sliver C2{R}   (* = ativa)\n")
    print(f"   {'NOME':<20}{'VERSAO':<14}{'ESTADO':<14}{'CRIADA':<20}")
    print(f"   {'-'*18:<20}{'-'*12:<14}{'-'*12:<14}{'-'*18:<20}")
    for n in names:
        meta = read_meta(n)
        env = load_session_env(n)
        version = env.get("SLIVER_VERSION", meta.get("version", "?"))
        state = container_state(n, "server")
        mark = f"{GRN}*{R}" if n == act else " "
        sc = GRN if state == "running" else RED if state == "not_found" else YLW
        created = (meta.get("created") or "?")[:19].replace("T", " ")
        print(f" {mark} {n:<20}{version:<14}{sc}{state:<12}{R}  {created}")
    print()


def cmd_stop(args):
    name = require_active()
    if not session_running(name):
        info(f"Sessao '{name}' ja esta parada.")
        return
    stop_session(name)
    info("Containers parados. Volumes preservados.")


def cmd_del(args):
    if not args:
        err("uso: Sliver_Handler.py del <nome>")
        sys.exit(1)
    name = args[0]
    if not session_path(name).exists():
        err(f"Sessao '{name}' nao existe.")
        sys.exit(1)

    info(f"Removendo sessao '{name}' (containers + volumes + config)...")
    dc(name, "down", "-v", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    shutil.rmtree(session_path(name))
    if active_session() == name:
        set_active(None)
    info(f"Sessao '{name}' removida.")


def cmd_rename(args):
    if len(args) < 2 or not valid_name(args[1]):
        err("uso: Sliver_Handler.py rename <antigo> <novo>")
        sys.exit(1)
    old, new = args[0], args[1]
    if not session_path(old).exists():
        err(f"Sessao '{old}' nao existe.")
        sys.exit(1)
    if session_path(new).exists():
        err(f"Sessao '{new}' ja existe.")
        sys.exit(1)
    if session_running(old):
        err(f"Sessao '{old}' esta rodando. Pare com 'stop' antes.")
        sys.exit(1)

    dc(old, "down", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    session_path(old).rename(session_path(new))
    generate_env(new, read_meta(new).get("version", DEFAULT_VERSION))
    write_meta(new)
    if active_session() == old:
        set_active(new)
    info(f"'{old}' -> '{new}'")


def cmd_status(args):
    name = require_active()
    env = load_session_env(name)
    meta = read_meta(name)
    srv = container_state(name, "server")
    cli = container_state(name, "client")

    def color(st):
        if st == "running": return GRN
        if st == "not_found": return RED
        return YLW

    print(f"\n{B}Sliver C2 — Sessao '{name}'{R}")
    print(f"  Versao    : {env.get('SLIVER_VERSION', '?')}")
    print(f"  Server    : {color(srv)}{srv}{R}")
    print(f"  Client    : {color(cli)}{cli}{R}")
    print(f"  Operador  : {env.get('OPERATOR_NAME', '?')}")
    print(f"  Portas    : {env.get('OPERATOR_LPORT', '31337')} (operador), 80/443/8888 (C2)")
    print(f"  Criada    : {meta.get('created', '?')}")
    print(f"  Projeto   : {project_name(name)}")
    vols = dc_out(name, "config", "--volumes")
    if vols:
        print(f"  Volumes   : {', '.join(vols.splitlines())}")
    print()


def cmd_logs(args):
    name = require_active()
    info(f"Logs — sessao '{name}' (Ctrl+C para sair)")
    try:
        dc(name, "logs", "-f", "--tail", "100", "server")
    except KeyboardInterrupt:
        pass


def cmd_reset(args):
    name = require_active()
    warn(f"Reset da sessao '{name}': APAGA volumes (certs, config, implantes).")
    try:
        resp = input("  Confirma? [s/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        info("Cancelado.")
        return
    if resp not in ("s", "sim", "y", "yes"):
        info("Cancelado.")
        return
    info("Parando e removendo volumes...")
    dc(name, "down", "-v")
    info(f"Sessao '{name}' zerada. 'up' refaz tudo do zero.")


def fetch_github_versions():
    try:
        url = "https://api.github.com/repos/BishopFox/sliver/releases?per_page=50"
        req = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Sliver_Handler",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            releases = json.loads(resp.read())
        return [(r["tag_name"], r.get("published_at", "")[:10])
                for r in releases if r.get("tag_name")]
    except Exception:
        return None


def cmd_versions(args):
    catalog = all_versions()
    info("Consultando releases no GitHub...")
    github = fetch_github_versions()

    if github:
        print(f"\n{B}Versoes do Sliver (GitHub + catalogo local){R}\n")
        for tag, date in github:
            vi = catalog.get(tag, {})
            default = f" {YLW}(default){R}" if tag == DEFAULT_VERSION else ""
            if vi.get("server_sha256"):
                status = f"{GRN}checksum verificado{R}"
            else:
                status = f"{YLW}sem checksum{R}"
            notes = f"  {vi['notes']}" if vi.get("notes") else ""
            print(f"  {CYN}{tag}{R}{default}  [{status}]  {date}{notes}")
    else:
        warn("Nao foi possivel consultar o GitHub (offline?). Catalogo local:")
        print(f"\n{B}Versoes do Sliver (catalogo local){R}\n")
        for tag, vi in sorted(catalog.items()):
            default = f" {YLW}(default){R}" if tag == DEFAULT_VERSION else ""
            verified = f"{GRN}SHA-256{R}" if vi.get("server_sha256") else f"{YLW}sem checksum{R}"
            notes = vi.get("notes", "")
            print(f"  {CYN}{tag}{R}{default}  [{verified}]")
            if notes:
                print(f"    {notes}")

    print(f"\n  'new <nome> <tag>' cria sessao com qualquer versao listada.")
    print(f"  Sem checksum no catalogo, o build prossegue sem verificacao.\n")


def cmd_config(args):
    name = require_active()
    env = load_session_env(name)
    if not env:
        err(f"Config nao encontrado para sessao '{name}'")
        sys.exit(1)
    print(f"\n{B}Config — sessao '{name}'{R}\n")
    for k, v in env.items():
        if "SHA256" in k:
            display = f"{v[:16]}...{v[-8:]}" if len(v) > 24 else v or "(vazio)"
            print(f"  {k:<25}{display}")
        else:
            print(f"  {k:<25}{CYN}{v}{R}")
    print()


def cmd_help(args):
    print(__doc__)


# ---------------------------------------------------------- dispatch
COMMANDS = {
    "new": cmd_new, "create": cmd_new,
    "up": cmd_up, "start": cmd_up,
    "client": cmd_client, "console": cmd_client, "c": cmd_client,
    "server": cmd_server, "srv": cmd_server, "s": cmd_server,
    "use": cmd_use, "switch": cmd_use,
    "list": cmd_list, "ls": cmd_list,
    "stop": cmd_stop, "down": cmd_stop,
    "del": cmd_del, "rm": cmd_del, "delete": cmd_del,
    "rename": cmd_rename, "mv": cmd_rename,
    "status": cmd_status, "st": cmd_status,
    "logs": cmd_logs, "log": cmd_logs,
    "reset": cmd_reset, "nuke": cmd_reset,
    "versions": cmd_versions, "ver": cmd_versions,
    "config": cmd_config, "env": cmd_config,
    "help": cmd_help, "-h": cmd_help, "--help": cmd_help,
}


def main():
    argv = sys.argv[1:]

    if not argv or argv[0] in ("help", "-h", "--help"):
        cmd_help([])
        return

    check_prereqs()
    init_paths()

    cmd = argv[0]
    handler = COMMANDS.get(cmd)
    if not handler:
        err(f"comando desconhecido: {cmd}\n")
        cmd_help([])
        sys.exit(1)
    handler(argv[1:])


if __name__ == "__main__":
    main()
