"""boiler — CLI global del sistema Boiler.

Se puede iniciar en CUALQUIER carpeta (vacía o con proyectos existentes).
El registro central vive en ~/.boiler/registry.yml: todos los workspaces
inicializados, su puerto de hub, y con ello la vista global de puertos/URLs.

Comandos:
  boiler init [nombre]     registra la carpeta actual como workspace (asigna puerto de hub)
  boiler hub               levanta el hub del workspace actual (foreground)
  boiler list              proyectos del workspace actual (descubiertos por boiler.yml)
  boiler up|down|status <id>   delega en el run.sh del proyecto
  boiler add [ruta]        adopta un proyecto EXISTENTE (analiza, genera boiler.yml, recomienda estructura)
  boiler service install   hub global como servicio de macOS (LaunchAgent, arranca al iniciar sesión)
  boiler workspaces        todos los workspaces registrados (centralización)
  boiler ports             vista global de puertos usados (hubs + proyectos de cada workspace)
  boiler audit             escaneo de vulnerabilidades (OSV.dev) de todos los workspaces
  boiler version           versión instalada
  boiler update            actualiza Boiler desde su repo (git pull + deps + reinicia el servicio)
"""
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from . import __version__

BOILER_HOME = Path.home() / ".boiler"
REGISTRY = BOILER_HOME / "registry.yml"
HUB_PORT_BASE = 8500


# ── Registro central ──────────────────────────────────────────────────────────
def load_registry() -> Dict:
    if REGISTRY.is_file():
        return yaml.safe_load(REGISTRY.read_text()) or {"workspaces": []}
    return {"workspaces": []}


def save_registry(reg: Dict) -> None:
    BOILER_HOME.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(
        "# Registro central de Boiler — workspaces inicializados y sus puertos de hub.\n"
        + yaml.safe_dump(reg, sort_keys=False, allow_unicode=True))


def find_workspace(cwd: Path) -> Optional[Dict]:
    """Workspace registrado que contiene a cwd (el más profundo)."""
    reg = load_registry()
    best = None
    for w in reg["workspaces"]:
        wp = Path(w["path"])
        try:
            cwd.resolve().relative_to(wp)
        except ValueError:
            continue
        if best is None or len(str(wp)) > len(str(Path(best["path"]))):
            best = w
    return best


def require_workspace() -> Dict:
    w = find_workspace(Path.cwd())
    if not w:
        sys.exit("Esta carpeta no pertenece a ningún workspace Boiler.\n"
                 "Inicialízala con:  boiler init")
    return w


def _set_root(w: Dict) -> None:
    os.environ["BOILER_ROOT"] = w["path"]


# ── Comandos ──────────────────────────────────────────────────────────────────
def cmd_init(args: List[str]) -> None:
    cwd = Path.cwd().resolve()
    reg = load_registry()
    for w in reg["workspaces"]:
        if Path(w["path"]) == cwd:
            print("Ya registrado: %s (hub en :%s)" % (w["name"], w["hub_port"]))
            return
    used = {w["hub_port"] for w in reg["workspaces"]}
    port = HUB_PORT_BASE
    while port in used:
        port += 1
    name = args[0] if args else cwd.name
    reg["workspaces"].append({
        "name": name, "path": str(cwd), "hub_port": port,
        "created": time.strftime("%Y-%m-%d"),
    })
    save_registry(reg)
    (cwd / ".boiler").mkdir(exist_ok=True)
    n = _count_manifests(cwd)
    print("✓ Workspace '%s' registrado." % name)
    print("  Ruta:      %s" % cwd)
    print("  Hub:       http://%s.boiler.localhost:%d  →  boiler hub" % (name.lower().replace(' ', '-'), port))
    print("  Proyectos: %d con boiler.yml detectados" % n)
    if n == 0:
        print("  (carpeta nueva: crea proyectos y decláralos con boiler.yml — ver MANIFEST.md)")


def _count_manifests(root: Path) -> int:
    os.environ["BOILER_ROOT"] = str(root)
    from .hub.collectors import registry as hub_registry
    return len(hub_registry.load_projects(force=True))


GLOBAL_HUB_PORT = 8500


def cmd_hub() -> None:
    """Hub GLOBAL: agrega los proyectos de TODOS los workspaces registrados."""
    os.environ["BOILER_GLOBAL"] = "1"
    boiler_dir = Path(__file__).resolve().parents[1]
    uvicorn = boiler_dir / ".venv" / "bin" / "uvicorn"
    n = len(load_registry()["workspaces"])
    print("Hub global (%d workspaces) → http://localhost:%d  (Ctrl+C para detener)" % (n, GLOBAL_HUB_PORT))
    os.chdir(str(boiler_dir))
    os.execv(str(uvicorn), [str(uvicorn), "boiler.hub.main:app",
                            "--host", "0.0.0.0", "--port", str(GLOBAL_HUB_PORT)])


PLIST = Path.home() / "Library" / "LaunchAgents" / "cl.boiler.hub.plist"


def cmd_service(args):
    """LaunchAgent de macOS: el hub global siempre corriendo."""
    action = args[0] if args else "status"
    boiler_dir = Path(__file__).resolve().parents[1]
    if action == "install":
        BOILER_HOME.mkdir(parents=True, exist_ok=True)
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        PLIST.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>cl.boiler.hub</string>
  <key>ProgramArguments</key><array>
    <string>%s/.venv/bin/uvicorn</string>
    <string>boiler.hub.main:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>%d</string>
  </array>
  <key>WorkingDirectory</key><string>%s</string>
  <key>EnvironmentVariables</key><dict>
    <key>BOILER_GLOBAL</key><string>1</string>
    <key>PYTHONPATH</key><string>%s</string>
    <key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>%s/hub.log</string>
  <key>StandardErrorPath</key><string>%s/hub.log</string>
</dict></plist>
""" % (boiler_dir, GLOBAL_HUB_PORT, boiler_dir, boiler_dir, BOILER_HOME, BOILER_HOME))
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        subprocess.run(["launchctl", "load", str(PLIST)], capture_output=True)
        print("✓ Servicio instalado y levantado: http://localhost:%d (arranca solo al iniciar sesión)" % GLOBAL_HUB_PORT)
        print("  Log: %s/hub.log · Desinstalar: boiler service uninstall" % BOILER_HOME)
    elif action == "uninstall":
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        PLIST.unlink(missing_ok=True)
        print("✓ Servicio desinstalado.")
    else:
        out = subprocess.run(["launchctl", "list", "cl.boiler.hub"], capture_output=True, text=True)
        if out.returncode == 0:
            print("Servicio ACTIVO → http://localhost:%d" % GLOBAL_HUB_PORT)
        else:
            print("Servicio no instalado. Usa: boiler service install")


def cmd_list() -> None:
    w = require_workspace()
    _set_root(w)
    from .hub.collectors import docker_state, registry as hub_registry
    docker_map = docker_state.docker_running_by_project()
    projects = hub_registry.load_projects(force=True)
    print("Workspace: %s (%s) · hub :%s\n" % (w["name"], w["path"], w["hub_port"]))
    print("%-14s %-9s %-10s %s" % ("ID", "TYPE", "ESTADO", "URL"))
    for p in projects:
        containers = docker_map.get(p.get("compose_project") or "", [])
        port_up = docker_state.port_listening(p["port"]) if p.get("port") else False
        up = bool(containers) or port_up
        estado = "🟢 up" + (" (%d)" % len(containers) if containers else "") if up else "⚪ down"
        print("%-14s %-9s %-10s %s" % (p["id"], p.get("type", "?"), estado, p.get("local_url") or "-"))
    if not projects:
        print("(sin proyectos con boiler.yml todavía)")


def cmd_run_sh(project_id: str, action: str) -> None:
    w = require_workspace()
    _set_root(w)
    from .hub.collectors import registry as hub_registry
    try:
        p = hub_registry.get_project(project_id)
    except KeyError:
        sys.exit("Proyecto '%s' no existe en este workspace (boiler list)." % project_id)
    run = os.path.join(p["abs_path"], "run.sh")
    if not os.path.isfile(run):
        sys.exit("ERROR: %s no tiene run.sh" % project_id)
    os.chdir(p["abs_path"])
    os.execv(run, [run, action])


def cmd_workspaces() -> None:
    reg = load_registry()
    if not reg["workspaces"]:
        print("Sin workspaces registrados. Usa `boiler init` en una carpeta.")
        return
    print("%-18s %-10s %-12s %s" % ("NOMBRE", "HUB", "CREADO", "RUTA"))
    for w in reg["workspaces"]:
        print("%-18s :%-9s %-12s %s" % (w["name"], w["hub_port"], w.get("created", "?"), w["path"]))


def cmd_ports() -> None:
    """Vista GLOBAL de puertos: hubs + entradas de cada proyecto de cada workspace."""
    reg = load_registry()
    rows = []
    for w in reg["workspaces"]:
        rows.append((w["hub_port"], "hub", w["name"], "hub de " + w["name"]))
        os.environ["BOILER_ROOT"] = w["path"]
        from .hub.collectors import registry as hub_registry
        for p in hub_registry.load_projects(force=True):
            if p.get("port"):
                rows.append((p["port"], p.get("type", "?"), w["name"], p["id"]))
    rows.sort()
    print("%-8s %-10s %-16s %s" % ("PUERTO", "TYPE", "WORKSPACE", "PROYECTO"))
    dup = None
    for port, typ, ws, pid in rows:
        flag = "  ⚠ DUPLICADO" if port == dup else ""
        print("%-8s %-10s %-16s %s%s" % (port, typ, ws, pid, flag))
        dup = port


def cmd_add(args: List[str]) -> None:
    """Adopta un proyecto EXISTENTE: lo analiza, genera su boiler.yml y
    entrega el informe de la mejor estructura según su schema."""
    from . import schemas
    from .generator import next_free_port, load_config
    target = Path(args[0]).resolve() if args else Path.cwd()
    if not target.is_dir():
        sys.exit("No existe: %s" % target)
    w = find_workspace(target)
    if not w:
        sys.exit("La carpeta no está dentro de un workspace Boiler.\n"
                 "Registra su raíz primero: cd <carpeta-raíz> && boiler init")
    if (target / "boiler.yml").is_file():
        sys.exit("Ya tiene boiler.yml — ya es un proyecto Boiler.")

    print("Analizando %s …\n" % target.name)
    a = schemas.analyze(target)
    cfg = load_config()
    port = a["port_detected"] or next_free_port(cfg["ports"]["block_size"], cfg["ports"]["search_from"])
    pid = target.name.lower().replace(" ", "-").replace(".", "").replace("_", "-")
    empresa = ask_flag(args, "--empresa") or cfg["defaults"]["empresa"]
    domain = "%s.%s.localhost" % (pid, empresa)

    m = {
        "boiler": 1, "id": pid, "name": target.name, "empresa": empresa,
        "type": a["type"],
        "local": {"domain": domain, "port": port, "run": "./run.sh",
                  "compose": (str(a["compose"].relative_to(target)) if a["compose"] else None),
                  "compose_project": pid if a["compose"] else None},
        "stack": a["stacks"] + ([a["db"]] if a["db"] != "none" else []),
        "db": ({"engine": a["db"]} if a["db"] != "none" else {"engine": "none"}),
        "backup": "./backup.sh" if (target / "backup.sh").is_file() else None,
        "tasks": "tasks.yml",
        "repo": {"provider": "none", "url": None},
        "prod": {"provider": "pending", "url": None},
    }
    if a["apps"]:
        m["apps"] = [{"name": x["name"], "path": x["path"], "role": x["role"], "stack": x["stack"]}
                     for x in a["apps"]]
    (target / "boiler.yml").write_text(
        "# boiler.yml — generado por `boiler add` (revisar puerto/dominio)\n"
        + yaml.safe_dump(m, sort_keys=False, allow_unicode=True))
    if not (target / "tasks.yml").is_file():
        (target / "tasks.yml").write_text("# Tareas del proyecto (hub de Boiler)\ntasks: []\n")

    print("✓ Adoptado como '%s' — type=%s · stacks=%s · db=%s · puerto %s%s" % (
        pid, a["type"], ",".join(a["stacks"]) or "?", a["db"], port,
        " (detectado del compose)" if a["port_detected"] else " (asignado del pool global)"))
    print("  boiler.yml creado — ya visible en el hub y en `boiler list`.\n")
    print("Estructura recomendada por el schema '%s':" % a["type"])
    for level, msg in a["recommendations"]:
        print("  %s %s" % (level, msg))


def ask_flag(args: List[str], flag: str) -> Optional[str]:
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def cmd_update() -> None:
    """Actualiza Boiler: git pull en su repo, dependencias y reinicio del servicio."""
    boiler_dir = Path(__file__).resolve().parents[1]
    print("Boiler v%s en %s" % (__version__, boiler_dir))
    if not (boiler_dir / ".git").is_dir():
        sys.exit("El repo de Boiler no tiene git inicializado.")
    remote = subprocess.run(["git", "-C", str(boiler_dir), "remote"],
                            capture_output=True, text=True).stdout.strip()
    if not remote:
        print("⚠ Sin remoto configurado — nada desde dónde actualizar.")
        print("  Configura uno: git -C %s remote add origin <url> && git push -u origin main" % boiler_dir)
    else:
        print("→ git pull --ff-only…")
        r = subprocess.run(["git", "-C", str(boiler_dir), "pull", "--ff-only"],
                           capture_output=True, text=True)
        print(" ", (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else "")
        if r.returncode != 0:
            sys.exit("git pull falló — revisa cambios locales sin commitear en el repo de Boiler.")
    print("→ Dependencias…")
    subprocess.run([str(boiler_dir / ".venv" / "bin" / "pip"), "install", "-q", "-r",
                    str(boiler_dir / "requirements.txt")])
    # nueva versión tras el pull
    out = subprocess.run([str(boiler_dir / ".venv" / "bin" / "python"), "-c",
                          "import boiler; print(boiler.__version__)"],
                         capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(boiler_dir)})
    new_v = out.stdout.strip() or __version__
    if PLIST.is_file():
        print("→ Reiniciando el servicio del hub…")
        subprocess.run(["launchctl", "kickstart", "-k", "gui/%d/cl.boiler.hub" % os.getuid()],
                       capture_output=True)
    print("✓ Boiler v%s listo." % new_v)


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "list"
    if cmd == "init":
        cmd_init(args[1:])
    elif cmd == "new":
        from .generator import cmd_new
        cmd_new(args[1:])
    elif cmd == "config":
        from .generator import load_config, CONFIG
        load_config()
        print("Configuración global: %s" % CONFIG)
        print(CONFIG.read_text())
    elif cmd == "hub":
        cmd_hub()
    elif cmd == "add":
        cmd_add(args[1:])
    elif cmd == "service":
        cmd_service(args[1:])
    elif cmd == "list":
        cmd_list()
    elif cmd in ("up", "down", "status") and len(args) >= 2:
        cmd_run_sh(args[1], cmd)
    elif cmd == "workspaces":
        cmd_workspaces()
    elif cmd == "ports":
        cmd_ports()
    elif cmd in ("version", "-v", "--version"):
        print("boiler v%s" % __version__)
    elif cmd == "update":
        cmd_update()
    elif cmd == "audit":
        os.environ["BOILER_GLOBAL"] = "1"
        from .hub.collectors import registry as hub_registry, security
        print("Escaneando dependencias de todos los workspaces (OSV.dev)…")
        snap = security.scan(hub_registry.load_projects(force=True))
        t = snap["totals"]
        print("\n%d dependencias únicas · críticas %d · altas %d · moderadas %d · bajas/otras %d" % (
            snap["deps_total"], t["critical"], t["high"], t["moderate"], t["low"] + t["unknown"]))
        for pid, data in sorted(snap["projects"].items()):
            c2 = data["counts"]
            print("  %-14s crit %d · alta %d · mod %d" % (pid, c2["critical"], c2["high"], c2["moderate"]))
        print("\nDetalle: http://localhost:8500/security")
    else:
        print(__doc__.strip())
        sys.exit(0 if cmd in ("help", "-h", "--help") else 1)


if __name__ == "__main__":
    main()
