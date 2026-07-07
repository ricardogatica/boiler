"""boiler new — wizard de creación de proyectos (B3).

Las dos preguntas clave definen la forma:
  1. ¿Multi-app o app única?
  2. ¿Base de datos? (mysql | postgres | none)

- Front simple (sin DB)  → react/vue con Vite, Astro, Nuxt o Next; sin docker; run.sh host.
- Con DB (php/node/api)  → docker-compose.yml en la raíz + project/.docker/ con la
  configuración que corresponda (Dockerfiles, nginx, tuning de DB), datos en ./.data/.
- Multi-app              → frontend/ + backoffice/ + compose orquestador con nginx de entrada.

Además registra deploy (github|bitbucket|gitlab + railway|aws|digitalocean|vps) en el
manifiesto, asigna el siguiente bloque de puertos libre GLOBAL (todos los workspaces,
registro en ~/.boiler/), y deja run.sh/backup.sh/tasks.yml/git init listos.

Defaults configurables en ~/.boiler/config.yml.
"""
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml

BOILER_HOME = Path.home() / ".boiler"
CONFIG = BOILER_HOME / "config.yml"

STACKS_NO_DB = ["vue-vite", "react-vite", "astro", "nuxt", "next"]
STACKS_DB = ["laravel", "node-api", "nuxt-fullstack"]
DBS = ["mysql", "postgres", "none"]
GIT_PROVIDERS = ["github", "bitbucket", "gitlab", "none"]
DEPLOYS = ["railway", "aws", "digitalocean", "vps", "none"]

DEFAULT_CONFIG = {
    "defaults": {"empresa": "restart", "db": "mysql", "git": "github", "deploy": "railway"},
    "ports": {"block_size": 10, "search_from": 8600},
}


def load_config() -> Dict:
    if CONFIG.is_file():
        cfg = yaml.safe_load(CONFIG.read_text()) or {}
        base = dict(DEFAULT_CONFIG)
        base["defaults"] = {**DEFAULT_CONFIG["defaults"], **(cfg.get("defaults") or {})}
        base["ports"] = {**DEFAULT_CONFIG["ports"], **(cfg.get("ports") or {})}
        return base
    BOILER_HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text("# Configuración global de Boiler (defaults del wizard `boiler new`)\n"
                      + yaml.safe_dump(DEFAULT_CONFIG, sort_keys=False, allow_unicode=True))
    return dict(DEFAULT_CONFIG)


# ── Wizard helpers ────────────────────────────────────────────────────────────
def ask(label: str, choices: Optional[List[str]] = None, default: Optional[str] = None,
        preset: Optional[str] = None) -> str:
    if preset is not None:
        if choices and preset not in choices:
            sys.exit("Valor inválido '%s' para %s (opciones: %s)" % (preset, label, ", ".join(choices)))
        return preset
    if not sys.stdin.isatty():
        return default or (choices[0] if choices else "")
    prompt = label
    if choices:
        prompt += " [%s]" % "/".join(("*" + c if c == default else c) for c in choices)
    elif default:
        prompt += " [%s]" % default
    while True:
        val = input(prompt + ": ").strip() or (default or "")
        if not choices or val in choices:
            return val
        print("  → opciones: %s" % ", ".join(choices))


def next_free_port(block: int = 10, search_from: int = 8600) -> int:
    """Siguiente bloque libre considerando TODOS los workspaces (~/.boiler/registry.yml)."""
    from .cli import load_registry
    used = set()
    reg = load_registry()
    for w in reg["workspaces"]:
        used.add(w["hub_port"])
        os.environ["BOILER_ROOT"] = w["path"]
        from .hub.collectors import registry as hub_registry
        for p in hub_registry.load_projects(force=True):
            if p.get("port"):
                used.update(range(p["port"], p["port"] + block))
    port = search_from
    while any(u in range(port, port + block) for u in used):
        port += block
    return port


def sh(cwd: Path, *args: str) -> None:
    subprocess.run(list(args), cwd=str(cwd), capture_output=True)


# ── Generación de archivos ────────────────────────────────────────────────────
def w(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(0o755)


SCAFFOLDS = {
    "vue-vite": "npm create vite@latest . -- --template vue",
    "react-vite": "npm create vite@latest . -- --template react",
    "astro": "npm create astro@latest .",
    "nuxt": "npx nuxi@latest init . --packageManager npm --gitInit false",
    "next": "npx create-next-app@latest .",
    "nuxt-fullstack": "npx nuxi@latest init . --packageManager npm --gitInit false",
}

DEV_CMDS = {
    "vue-vite": 'npm run dev -- --port "$APP_PORT" --host',
    "react-vite": 'npm run dev -- --port "$APP_PORT" --host',
    "astro": 'npm run dev -- --port "$APP_PORT"',
    "nuxt": 'npm run dev -- --port "$APP_PORT"',
    "next": 'npm run dev -- -p "$APP_PORT"',
    "nuxt-fullstack": 'npm run dev -- --port "$APP_PORT"',
}


def run_sh_host(ctx: Dict) -> str:
    return f'''#!/usr/bin/env bash
#
# {ctx["name"]} — arranque homologado (contrato Boiler §5.1). Generado por `boiler new`.
#
# Puertos (bloque {ctx["port"]}+):
#   {ctx["port"]} → dev server  ← ENTRADA: http://{ctx["domain"]}:{ctx["port"]}
#
# Uso: ./run.sh up|down|restart|status   (./run.sh = up)
set -euo pipefail
cd "$(dirname "$0")"

APP_PORT={ctx["port"]}

case "${{1:-up}}" in
  up)
    if [ ! -f package.json ]; then
      echo "⚠ Proyecto sin scaffold todavía. Ejecuta:"
      echo "    {SCAFFOLDS[ctx["stack"]]}"
      exit 1
    fi
    [ -d node_modules ] || npm install
    echo
    echo "   App → http://{ctx["domain"]}:$APP_PORT"
    echo
    exec {DEV_CMDS[ctx["stack"]]}
    ;;
  down)
    pids="$(lsof -ti ":$APP_PORT" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then kill $pids && echo "✓ Detenido."; else echo "No estaba corriendo."; fi
    ;;
  restart) "$0" down; exec "$0" up ;;
  status)
    lsof -i ":$APP_PORT" -sTCP:LISTEN >/dev/null 2>&1 && echo "Corriendo → http://{ctx["domain"]}:$APP_PORT" || echo "Detenido"
    ;;
  logs) echo "Corre en foreground (./run.sh up)." ;;
  backup) echo "Sin base de datos — nada que respaldar." ;;
  *) echo "Uso: ./run.sh {{up|down|restart|status}}"; exit 1 ;;
esac
'''


def run_sh_docker(ctx: Dict) -> str:
    migrate = ""
    if ctx["stack"] == "laravel":
        migrate = '''
  echo "→ Migraciones…"
  docker compose exec -T app php artisan migrate --force 2>/dev/null || echo "  (aún sin app Laravel — ver README)"'''
    urls = f'''  echo "   App    → http://{ctx["domain"]}:{ctx["port"]}"
  echo "   DB     → localhost:{ctx["port"] + 1} ({ctx["db"]})"'''
    return f'''#!/usr/bin/env bash
#
# {ctx["name"]} — arranque homologado (contrato Boiler §5.1). Generado por `boiler new`.
#
# Puertos (bloque {ctx["port"]}-{ctx["port"] + 9}):
#   {ctx["port"]} → nginx/app  ← ENTRADA: http://{ctx["domain"]}:{ctx["port"]}
#   {ctx["port"] + 1} → {ctx["db"]} (host)
#
# Uso: ./run.sh up [--build] | down | restart | status | logs [svc] | backup
set -euo pipefail
cd "$(dirname "$0")"

wait_db() {{
  echo -n "→ Esperando a la DB"
  for _ in $(seq 1 60); do
    docker compose exec -T db {("mysqladmin ping -h localhost --silent" if ctx["db"] == "mysql" else 'pg_isready -q -U app')} >/dev/null 2>&1 && {{ echo " ✓"; return 0; }}
    echo -n "."; sleep 2
  done
  echo " ✗"; exit 1
}}

cmd_up() {{
  BUILD=""; [ "${{1:-}}" = "--build" ] && BUILD="--build"
  [ -f .env ] || cp .env.example .env
  docker compose up -d $BUILD
  wait_db{migrate}
  echo
{urls}
  echo
  echo "   Logs: ./run.sh logs · Parar: ./run.sh down"
}}

case "${{1:-up}}" in
  up) shift || true; cmd_up "${{1:-}}" ;;
  down) docker compose down; echo "✓ Detenido (datos conservados en ./.data/)." ;;
  restart) docker compose down; cmd_up "" ;;
  status) docker compose ps --format "table {{{{.Name}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}" ;;
  logs) shift; exec docker compose logs -f "$@" ;;
  backup) shift; exec ./backup.sh "$@" ;;
  --build) cmd_up "--build" ;;
  *) echo "Uso: ./run.sh {{up [--build]|down|restart|status|logs [svc]|backup}}"; exit 1 ;;
esac
'''


def backup_sh(ctx: Dict) -> str:
    if ctx["db"] == "mysql":
        dump = '''docker compose exec -T db sh -c 'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --routines --triggers "$MYSQL_DATABASE"' '''
        restore = '''docker compose exec -T db sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' '''
        ready = "mysqladmin ping -h localhost --silent"
    else:
        dump = "docker compose exec -T db pg_dump -U app -d app"
        restore = "docker compose exec -T db psql -U app -d app"
        ready = "pg_isready -q -U app"
    return f'''#!/usr/bin/env bash
# Respaldo guiado de {ctx["name"]} (contrato Boiler §5.2). Generado por `boiler new`.
# Uso: ./backup.sh [--auto|--list|--restore <dir>]
set -euo pipefail
cd "$(dirname "$0")"
BACKUP_DIR=".backups"; KEEP=7; DB_NAME="app"

db_running() {{ docker compose ps --status running db 2>/dev/null | grep -q db; }}
wait_ready() {{ for _ in $(seq 1 60); do docker compose exec -T db {ready} >/dev/null 2>&1 && return 0; sleep 2; done; exit 1; }}

MODE="guided"; TARGET=""
case "${{1:-}}" in
  --auto) MODE="auto" ;;
  --list) ls -d "$BACKUP_DIR"/*/ 2>/dev/null || echo "Sin respaldos."; exit 0 ;;
  --restore) MODE="restore"; TARGET="${{2:?Uso: --restore <dir>}}" ;;
  "") ;;
  *) echo "Uso: ./backup.sh [--auto|--list|--restore <dir>]"; exit 1 ;;
esac

STARTED=0
db_running || {{ docker compose up -d db; wait_ready; STARTED=1; }}

if [ "$MODE" = "restore" ]; then
  DUMP="$BACKUP_DIR/$(basename "$TARGET")/db-$DB_NAME.sql.gz"
  [ -f "$DUMP" ] || {{ echo "No existe $DUMP"; exit 1; }}
  printf "⚠ SOBRESCRIBE la base. Escribe RESTAURAR: "; read -r a; [ "$a" = "RESTAURAR" ] || exit 1
  gunzip -c "$DUMP" | {restore}
  echo "✓ Restaurado."; exit 0
fi

TS="$(date +%Y-%m-%d_%H%M%S)"; DEST="$BACKUP_DIR/$TS"
if [ "$MODE" = "guided" ]; then printf "Respaldar '$DB_NAME' en $DEST/ [s/N] "; read -r a; case "$a" in s|S|si|sí) ;; *) exit 1 ;; esac; fi
mkdir -p "$DEST"
{dump} | gzip > "$DEST/db-$DB_NAME.sql.gz"
gzip -t "$DEST/db-$DB_NAME.sql.gz" && [ -s "$DEST/db-$DB_NAME.sql.gz" ] || {{ rm -rf "$DEST"; echo "✗ respaldo corrupto"; exit 1; }}
echo "✓ Respaldo OK: $DEST/db-$DB_NAME.sql.gz ($(du -sh "$DEST/db-$DB_NAME.sql.gz" | cut -f1))"
[ "$STARTED" = "1" ] && docker compose stop db >/dev/null
COUNT="$(ls -d "$BACKUP_DIR"/*/ 2>/dev/null | wc -l | tr -d ' ')"
[ "$COUNT" -gt "$KEEP" ] && ls -d "$BACKUP_DIR"/*/ | sort | head -n $((COUNT - KEEP)) | xargs rm -rf
exit 0
'''


def db_service(ctx: Dict, indent: str = "  ") -> str:
    p = ctx["port"] + 1
    if ctx["db"] == "mysql":
        return f'''{indent}db:
{indent}  image: mysql:8.0
{indent}  command:
{indent}    - --innodb-buffer-pool-size=256M
{indent}    - --performance-schema=OFF
{indent}  environment:
{indent}    MYSQL_ROOT_PASSWORD: ${{DB_ROOT_PASSWORD:-root}}
{indent}    MYSQL_DATABASE: app
{indent}    MYSQL_USER: app
{indent}    MYSQL_PASSWORD: ${{DB_PASSWORD:-secret}}
{indent}  ports:
{indent}    - "{p}:3306"
{indent}  volumes:
{indent}    - ./.data/mysql:/var/lib/mysql
{indent}  healthcheck:
{indent}    test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
{indent}    interval: 5s
{indent}    timeout: 5s
{indent}    retries: 10'''
    return f'''{indent}db:
{indent}  image: postgres:16-alpine
{indent}  environment:
{indent}    POSTGRES_USER: app
{indent}    POSTGRES_PASSWORD: ${{DB_PASSWORD:-secret}}
{indent}    POSTGRES_DB: app
{indent}  ports:
{indent}    - "{p}:5432"
{indent}  volumes:
{indent}    - ./.data/postgres:/var/lib/postgresql/data
{indent}  healthcheck:
{indent}    test: ["CMD-SHELL", "pg_isready -U app -d app"]
{indent}    interval: 5s
{indent}    timeout: 5s
{indent}    retries: 10'''


PHP_DOCKERFILE = '''FROM php:8.3-cli-alpine
RUN apk add --no-cache icu-dev oniguruma-dev libzip-dev {dbdev} git unzip $PHPIZE_DEPS \\
    && docker-php-ext-install pdo {pdo} intl mbstring zip pcntl \\
    && apk del $PHPIZE_DEPS
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
WORKDIR /var/www
EXPOSE 8000
CMD ["php", "artisan", "serve", "--host=0.0.0.0", "--port=8000"]
'''


def compose_single(ctx: Dict) -> str:
    if ctx["stack"] == "laravel":
        app = f'''  app:
    build:
      context: .
      dockerfile: .docker/php/Dockerfile
    working_dir: /var/www
    volumes:
      - .:/var/www
    depends_on:
      db:
        condition: service_healthy
    command: sh -c "if [ ! -f artisan ]; then echo '>>> Sin app Laravel. Scaffold → docker compose run --rm app composer create-project laravel/laravel .'; sleep infinity; fi; composer install --no-interaction && php artisan serve --host=0.0.0.0 --port=8000"

  nginx:
    image: nginx:alpine
    ports:
      - "{ctx["port"]}:80"
    volumes:
      - ./.docker/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - app
'''
    elif ctx["stack"] == "node-api":
        app = f'''  app:
    image: node:22-alpine
    working_dir: /app
    environment:
      PORT: "8000"
      DATABASE_URL: {("mysql://app:${DB_PASSWORD:-secret}@db:3306/app" if ctx["db"] == "mysql" else "postgresql://app:${DB_PASSWORD:-secret}@db:5432/app")}
    volumes:
      - .:/app
      - app_node_modules:/app/node_modules
    ports:
      - "{ctx["port"]}:8000"
    depends_on:
      db:
        condition: service_healthy
    command: sh -c "if [ ! -f package.json ]; then echo '>>> Sin API. Scaffold → npm init / nest new .'; sleep infinity; fi; npm install && npm run dev"
'''
    else:  # nuxt-fullstack: app corre en host (patrón enregla), docker solo para la DB
        app = ""
    volumes = "\nvolumes:\n  app_node_modules:\n" if ctx["stack"] == "node-api" else ""
    return f'''# {ctx["name"]} — generado por `boiler new` ({ctx["stack"]} + {ctx["db"]})
name: {ctx["id"]}

services:
{app}{db_service(ctx)}
{volumes}'''


def compose_multi(ctx: Dict) -> str:
    return f'''# {ctx["name"]} — multi-app generado por `boiler new` (frontend + backoffice + {ctx["db"]})
name: {ctx["id"]}

services:
  frontend:
    image: node:22-alpine
    working_dir: /app
    environment:
      PORT: "3000"
    volumes:
      - ./frontend:/app
      - frontend_node_modules:/app/node_modules
    command: sh -c "if [ ! -f package.json ]; then echo '>>> frontend/ vacío. Scaffold → (cd frontend && npm create vite@latest .)'; sleep infinity; fi; npm install && npm run dev -- --host 0.0.0.0 --port 3000"

  backoffice:
    build:
      context: .
      dockerfile: .docker/php/Dockerfile
    working_dir: /var/www
    volumes:
      - ./backoffice:/var/www
    depends_on:
      db:
        condition: service_healthy
    command: sh -c "if [ ! -f artisan ]; then echo '>>> backoffice/ vacío. Scaffold → docker compose run --rm backoffice composer create-project laravel/laravel .'; sleep infinity; fi; composer install --no-interaction && php artisan serve --host=0.0.0.0 --port=8000"

  nginx:
    image: nginx:alpine
    ports:
      - "{ctx["port"]}:80"
    volumes:
      - ./.docker/nginx/default.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - frontend
      - backoffice

{db_service(ctx)}

volumes:
  frontend_node_modules:
'''


def nginx_conf(ctx: Dict) -> str:
    if ctx["type"] == "multi-app":
        return f'''server {{
    listen 80;
    server_name {ctx["domain"]};
    client_max_body_size 64M;

    # $http_host preserva el puerto :{ctx["port"]} en redirects de Laravel
    location /api      {{ proxy_pass http://backoffice:8000; proxy_set_header Host $http_host; }}
    location /backoffice {{ proxy_pass http://backoffice:8000; proxy_set_header Host $http_host; }}

    location / {{
        proxy_pass http://frontend:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
'''
    return f'''server {{
    listen 80;
    server_name {ctx["domain"]};
    client_max_body_size 64M;

    location / {{
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $http_connection;
    }}
}}
'''


def manifest(ctx: Dict) -> str:
    m = {
        "boiler": 1, "id": ctx["id"], "name": ctx["name"], "empresa": ctx["empresa"],
        "type": ctx["type"], "description": "",
        "local": {"domain": ctx["domain"], "port": ctx["port"], "run": "./run.sh",
                  "compose": "docker-compose.yml" if ctx["docker"] else None,
                  "compose_project": ctx["id"] if ctx["docker"] else None},
        "stack": ctx["stacks"],
        "db": ({"engine": ctx["db"], "data": "./.data/" + ("mysql" if ctx["db"] == "mysql" else "postgres")}
               if ctx["db"] != "none" else {"engine": "none"}),
        "backup": "./backup.sh" if ctx["db"] != "none" else None,
        "tasks": "tasks.yml",
        "repo": {"provider": ctx["git"], "url": None},
        "prod": {"provider": ctx["deploy"], "url": None},
    }
    if ctx["type"] == "multi-app":
        m["apps"] = [
            {"name": "frontend", "path": "frontend", "role": "frontend", "stack": "node"},
            {"name": "backoffice", "path": "backoffice", "role": "backoffice", "stack": "laravel"},
        ]
    return ("# boiler.yml — manifiesto Boiler v1 (generado por `boiler new`)\n"
            + yaml.safe_dump(m, sort_keys=False, allow_unicode=True))


# ── Comando principal ─────────────────────────────────────────────────────────
def cmd_new(args: List[str]) -> None:
    from .cli import require_workspace
    ws = require_workspace()
    cfg = load_config()
    d = cfg["defaults"]

    flags = {}
    pos = []
    it = iter(args)
    for a in it:
        if a.startswith("--"):
            flags[a[2:]] = next(it, "")
        else:
            pos.append(a)
    if not pos:
        sys.exit("Uso: boiler new <nombre> [--type single|multi] [--db mysql|postgres|none] "
                 "[--stack ...] [--empresa X] [--git github|bitbucket|gitlab|none] "
                 "[--deploy railway|aws|digitalocean|vps|none]")
    name = pos[0]
    pid = name.lower().replace(" ", "-").replace(".", "")
    dest = Path(ws["path"]) / name
    if dest.exists():
        sys.exit("Ya existe: %s" % dest)

    print("Boiler · nuevo proyecto '%s' en workspace %s\n" % (name, ws["name"]))
    ptype = ask("¿Multi-app o app única?", ["single", "multi"], "single", flags.get("type"))
    ptype = "multi-app" if ptype in ("multi", "multi-app") else "single"
    if ptype == "multi-app":
        db = ask("Base de datos", ["mysql", "postgres"], d["db"], flags.get("db"))
        stack = "multi"
    else:
        db = ask("¿Base de datos?", DBS, d["db"], flags.get("db"))
        if db == "none":
            stack = ask("Stack (front simple)", STACKS_NO_DB, "vue-vite", flags.get("stack"))
        else:
            stack = ask("Stack", STACKS_DB, "laravel", flags.get("stack"))
    empresa = ask("Empresa (dominio local)", None, d["empresa"], flags.get("empresa"))
    git = ask("Repositorio git", GIT_PROVIDERS, d["git"], flags.get("git"))
    deploy = ask("Deploy", DEPLOYS, d["deploy"], flags.get("deploy"))

    port = next_free_port(cfg["ports"]["block_size"], cfg["ports"]["search_from"])
    domain = "%s.%s.localhost" % (pid, empresa) if empresa != pid else "%s.localhost" % pid
    docker = db != "none" or ptype == "multi-app"
    ctx = {
        "id": pid, "name": name, "empresa": empresa, "type": "multi-app" if ptype == "multi-app" else
        ("landing" if db == "none" else "app"),
        "db": db, "stack": stack, "port": port, "domain": domain, "docker": docker,
        "git": git, "deploy": deploy,
        "stacks": (["node-frontend", "laravel", db] if ptype == "multi-app"
                   else [stack] + ([db] if db != "none" else [])),
    }

    # Archivos
    dest.mkdir(parents=True)
    w(dest / "boiler.yml", manifest(ctx))
    w(dest / "tasks.yml", "# Tareas del proyecto (hub de Boiler)\ntasks: []\n")
    w(dest / ".gitignore", ".env\nnode_modules/\nvendor/\n.data/\n.backups/\n.nuxt/\n.output/\ndist/\n")
    w(dest / ".env.example", "APP_URL=http://%s:%d\nDB_PASSWORD=secret\nDB_ROOT_PASSWORD=root\n" % (domain, port))
    w(dest / "README.md", "# %s\n\nGenerado con `boiler new` (%s%s).\n\n```sh\n./run.sh up   →   http://%s:%d\n```\n\nDeploy: %s · Repo: %s\n"
      % (name, ctx["type"], "" if db == "none" else " + " + db, domain, port, deploy, git))

    if ptype == "multi-app":
        (dest / "frontend").mkdir()
        (dest / "backoffice").mkdir()
        (dest / "frontend" / ".gitkeep").touch()
        (dest / "backoffice" / ".gitkeep").touch()
        w(dest / "docker-compose.yml", compose_multi(ctx))
        w(dest / ".docker/nginx/default.conf", nginx_conf(ctx))
        w(dest / ".docker/php/Dockerfile",
          PHP_DOCKERFILE.format(dbdev="mysql-dev" if db == "mysql" else "postgresql-dev",
                                pdo="pdo_mysql" if db == "mysql" else "pdo_pgsql"))
        w(dest / "run.sh", run_sh_docker(ctx), executable=True)
        w(dest / "backup.sh", backup_sh(ctx), executable=True)
    elif db != "none":
        w(dest / "docker-compose.yml", compose_single(ctx))
        if stack == "laravel":
            w(dest / ".docker/nginx/default.conf", nginx_conf(ctx))
            w(dest / ".docker/php/Dockerfile",
              PHP_DOCKERFILE.format(dbdev="mysql-dev" if db == "mysql" else "postgresql-dev",
                                    pdo="pdo_mysql" if db == "mysql" else "pdo_pgsql"))
        w(dest / "run.sh", run_sh_docker(ctx), executable=True)
        w(dest / "backup.sh", backup_sh(ctx), executable=True)
    else:
        w(dest / "run.sh", run_sh_host(ctx), executable=True)

    sh(dest, "git", "init", "-q", "-b", "main")

    print("\n✓ Proyecto creado: %s" % dest)
    print("  type=%s · db=%s · stack=%s · puerto %d (bloque %d-%d)" % (ctx["type"], db, stack, port, port, port + 9))
    print("  URL local: http://%s:%d" % (domain, port))
    print("  Deploy: %s · Repo: %s (crea el remoto y `git push`)" % (deploy, git))
    if db == "none":
        print("\nPróximo paso — scaffold del front:\n  cd %s && %s" % (dest, SCAFFOLDS[stack]))
    else:
        print("\nPróximo paso:\n  cd %s && ./run.sh up   (la app te indica el scaffold si falta)" % dest)
    print("  Ya visible en el hub y en `boiler list`.")
