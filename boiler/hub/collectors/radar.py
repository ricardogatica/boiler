"""Radar macro: versiones de frameworks, estado de respaldos y mapa de puertos."""
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

# Frameworks que vale la pena comparar entre proyectos
NPM_FRAMEWORKS = ["nuxt", "next", "vue", "react", "@nestjs/core", "express", "astro", "vite", "expo"]
COMPOSER_FRAMEWORKS = ["laravel/framework", "php"]


def _clean(v: str) -> str:
    return re.sub(r"^[\^~>=<\s]+", "", v or "").split("|")[0].strip()


def _ver_key(v: str):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:4]) or (0,)


def _versions_in(d: Path) -> Dict[str, str]:
    found: Dict[str, str] = {}
    pkg = d / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text())
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            for fw in NPM_FRAMEWORKS:
                if fw in deps:
                    found[fw] = _clean(str(deps[fw]))
        except (json.JSONDecodeError, OSError):
            pass
    comp = d / "composer.json"
    if comp.is_file():
        try:
            data = json.loads(comp.read_text())
            req = data.get("require") or {}
            for fw in COMPOSER_FRAMEWORKS:
                if fw in req:
                    found[fw] = _clean(str(req[fw]))
        except (json.JSONDecodeError, OSError):
            pass
    return found


def versions(projects: List[Dict]) -> Dict:
    """Matriz framework × proyecto, marcando los que están bajo la versión más nueva EN CASA."""
    rows: Dict[str, List[Dict]] = {}
    for p in projects:
        if not p.get("exists"):
            continue
        root = Path(p["abs_path"])
        dirs = [("", root)] + [(a.get("path", ""), root / a.get("path", ""))
                               for a in p.get("apps") or []]
        merged: Dict[str, Dict] = {}
        for app, d in dirs:
            if d.is_dir():
                for fw, v in _versions_in(d).items():
                    cur = merged.get(fw)
                    if not cur or _ver_key(v) > _ver_key(cur["version"]):
                        merged[fw] = {"version": v, "app": app or "."}
        for fw, info in merged.items():
            rows.setdefault(fw, []).append({"project": p["id"], "name": p["name"], **info})

    # referencia: la mayor versión mayor ya usada en el ecosistema
    out = []
    for fw in sorted(rows, key=lambda f: -len(rows[f])):
        entries = rows[fw]
        newest = max(entries, key=lambda e: _ver_key(e["version"]))["version"]
        newest_major = _ver_key(newest)[0:1]
        for e in entries:
            e["outdated"] = _ver_key(e["version"])[0:1] < newest_major
        out.append({"framework": fw, "newest": newest,
                    "entries": sorted(entries, key=lambda e: _ver_key(e["version"]), reverse=True),
                    "outdated_count": sum(1 for e in entries if e["outdated"])})
    return {"frameworks": out}


def backups(projects: List[Dict]) -> List[Dict]:
    """Último respaldo por proyecto con DB (lee .backups/ de cada repo)."""
    out = []
    now = time.time()
    for p in projects:
        if not p.get("exists") or not p.get("has_db"):
            continue
        bdir = Path(p["abs_path"]) / ".backups"
        last: Optional[str] = None
        last_ts = 0.0
        if bdir.is_dir():
            dirs = sorted([d for d in bdir.iterdir() if d.is_dir()])
            if dirs:
                last = dirs[-1].name
                last_ts = dirs[-1].stat().st_mtime
        age_days = (now - last_ts) / 86400 if last else None
        if last is None:
            state, label = "critical", "nunca respaldado"
        elif age_days > 7:
            state, label = "warning", "hace %d días" % int(age_days)
        else:
            state, label = "good", "hace %d día(s)" % max(int(age_days), 0)
        out.append({"id": p["id"], "name": p["name"], "engine": p.get("db_engine", "?"),
                    "last": last, "state": state, "label": label,
                    "age": age_days if age_days is not None else 9999})
    out.sort(key=lambda b: -b["age"])
    return out


def ports_map(projects: List[Dict]) -> List[Dict]:
    """Bloques de puertos ordenados, con detección de solapes."""
    blocks = []
    for p in projects:
        if p.get("port"):
            blocks.append({"id": p["id"], "name": p["name"], "port": p["port"],
                           "end": p["port"] + 9, "workspace": p.get("workspace"),
                           "overlap": False})
    blocks.sort(key=lambda b: b["port"])
    for i in range(1, len(blocks)):
        if blocks[i]["port"] <= blocks[i - 1]["end"]:
            blocks[i]["overlap"] = blocks[i - 1]["overlap"] = True
    return blocks
