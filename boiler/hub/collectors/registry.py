"""Descubrimiento de proyectos por manifiesto boiler.yml (Boiler B2).

Escanea la carpeta raíz buscando `boiler.yml` en cada proyecto (con poda de
directorios pesados). `projects.yml` queda solo como fallback si no se
encuentra ningún manifiesto.
"""
import time
from pathlib import Path
from typing import Dict, List, Optional

import yaml

import os


def get_root() -> Path:
    """Workspace activo — se lee del entorno en cada llamada (la CLI itera workspaces)."""
    return Path(os.environ.get("BOILER_ROOT", os.getcwd())).resolve()


# Compat para el proceso del hub (ROOT fijo durante toda su vida)
ROOT = get_root()

MAX_DEPTH = 5
PRUNE = {
    "node_modules", "vendor", ".git", ".data", ".backups", ".venv", "data",
    ".nuxt", ".next", ".output", "dist", "storage", "__pycache__", ".yarn",
    ".docker", ".docs", "public", "resources", "database", "app", "src",
}

_CACHE: Dict = {}  # por workspace: {str(root): {"ts", "projects"}}
SCAN_TTL = 15  # segundos


def _scan_manifests(root: Path) -> List[Path]:
    found: List[Path] = []

    def walk(d: Path, depth: int) -> None:
        mf = d / "boiler.yml"
        if mf.is_file():
            found.append(mf)
            # los proyectos anidados (ej. cube360/apps/docs) también declaran
            # manifiesto: seguimos bajando solo un par de niveles más
            if depth >= MAX_DEPTH:
                return
        if depth >= MAX_DEPTH:
            return
        try:
            for child in d.iterdir():
                if child.is_dir() and not child.is_symlink() and child.name not in PRUNE \
                        and not child.name.startswith("."):
                    walk(child, depth + 1)
        except OSError:
            pass

    walk(root, 0)
    return found


def _from_manifest(mf: Path, root: Path) -> Optional[Dict]:
    try:
        m = yaml.safe_load(mf.read_text()) or {}
    except yaml.YAMLError:
        return None
    if not m.get("id"):
        return None
    local = m.get("local") or {}
    db = m.get("db") or {}
    engine = db.get("engine", "none")
    port = local.get("port")
    domain = local.get("domain")
    project_dir = mf.parent
    return {
        "id": m["id"],
        "name": m.get("name", m["id"]),
        "empresa": m.get("empresa"),
        "type": m.get("type", "app"),
        "path": str(project_dir.relative_to(root)),
        "abs_path": str(project_dir),
        "exists": True,
        "local_url": "http://%s:%s" % (domain, port) if domain and port else None,
        "port": port,
        "compose_project": local.get("compose_project"),
        "stack": m.get("stack", []),
        "apps": m.get("apps", []),
        "task_prefix": m.get("task_prefix"),
        # backup exigible: DB propia, o compartida con backup declarado
        "has_db": engine in ("mysql", "postgres") or (engine == "shared" and bool(m.get("backup"))),
        "db_engine": engine,
        "prod": m.get("prod") or {},
        "manifest": True,
    }


def _registry_workspaces() -> List[Dict]:
    reg = Path.home() / ".boiler" / "registry.yml"
    if not reg.is_file():
        return []
    data = yaml.safe_load(reg.read_text()) or {}
    return data.get("workspaces", [])


def load_projects_global(force: bool = False) -> List[Dict]:
    """Vista GLOBAL: proyectos de TODOS los workspaces registrados."""
    projects: List[Dict] = []
    seen = set()
    for ws in _registry_workspaces():
        wroot = Path(ws["path"])
        if not wroot.is_dir():
            continue
        for mf in sorted(_scan_manifests(wroot)):
            p = _from_manifest(mf, wroot)
            if p and p["id"] not in seen:
                seen.add(p["id"])
                p["workspace"] = ws["name"]
                projects.append(p)
    projects.sort(key=lambda p: p["id"])
    return projects


def load_projects(force: bool = False) -> List[Dict]:
    if os.environ.get("BOILER_GLOBAL") == "1":
        key = "__global__"
        now = time.time()
        c = _CACHE.get(key)
        if not force and c and now - c["ts"] < SCAN_TTL:
            return c["projects"]
        projects = load_projects_global(force)
        _CACHE[key] = {"projects": projects, "ts": now}
        return projects
    root = get_root()
    key = str(root)
    now = time.time()
    c = _CACHE.get(key)
    if not force and c and now - c["ts"] < SCAN_TTL:
        return c["projects"]

    projects = []
    seen = set()
    for mf in sorted(_scan_manifests(root)):
        p = _from_manifest(mf, root)
        if p and p["id"] not in seen:
            seen.add(p["id"])
            projects.append(p)

    projects.sort(key=lambda p: p["id"])
    _CACHE[key] = {"projects": projects, "ts": now}
    return projects


def get_project(project_id: str) -> Dict:
    for p in load_projects():
        if p["id"] == project_id:
            return p
    raise KeyError(project_id)
