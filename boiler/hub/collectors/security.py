"""Vulnerabilidades de dependencias vía OSV.dev (agrega GitHub Advisories/npm/Packagist/PyPI).

- Inventario: lockfiles con versiones exactas (composer.lock, package-lock.json,
  yarn.lock v1/berry, requirements.txt) del proyecto y de sus apps internas.
- Dedupe global → POST /v1/querybatch → detalles por vulnerabilidad (con cache).
- Snapshot en ~/.boiler/security.json. El hub lo refresca con un scheduler diario.
"""
import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple

OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/%s"
SNAPSHOT = Path.home() / ".boiler" / "security.json"

SEV_ORDER = ["critical", "high", "moderate", "low", "unknown"]
_LOCK = threading.Lock()
_STATE = {"scanning": False}


# ── Parseo de lockfiles ───────────────────────────────────────────────────────
def _parse_composer_lock(f: Path) -> List[Tuple[str, str, str]]:
    try:
        data = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for section in ("packages", "packages-dev"):
        for p in data.get(section) or []:
            v = (p.get("version") or "").lstrip("v")
            if p.get("name") and v:
                out.append(("Packagist", p["name"], v))
    return out


def _parse_package_lock(f: Path) -> List[Tuple[str, str, str]]:
    try:
        data = json.loads(f.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    pkgs = data.get("packages")
    if isinstance(pkgs, dict):  # lockfile v2/v3
        for path, meta in pkgs.items():
            if not path or not isinstance(meta, dict):
                continue
            name = meta.get("name") or path.split("node_modules/")[-1]
            if meta.get("version"):
                out.append(("npm", name, meta["version"]))
    else:  # v1
        def walk(deps):
            for name, meta in (deps or {}).items():
                if isinstance(meta, dict):
                    if meta.get("version"):
                        out.append(("npm", name, meta["version"]))
                    walk(meta.get("dependencies"))
        walk(data.get("dependencies"))
    return out


_YARN1_RE = re.compile(r'^"?((?:@[^/"]+/)?[^@/"]+)@.*?:\s*$')
_YARN_VER_RE = re.compile(r'^\s+version:?\s+"?([^"\s]+)"?\s*$')


def _parse_yarn_lock(f: Path) -> List[Tuple[str, str, str]]:
    out = []
    name = None
    try:
        lines = f.read_text(errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.startswith((" ", "\t", "#")) and line.rstrip().endswith(":"):
            m = _YARN1_RE.match(line.split(",")[0].rstrip(":") + ":")
            name = m.group(1) if m else None
            # yarn berry: "pkg@npm:^1.0" — limpiar el protocolo
            if name and name.endswith("@npm"):
                name = name[:-4]
        elif name:
            m = _YARN_VER_RE.match(line)
            if m:
                out.append(("npm", name, m.group(1)))
                name = None
    return out


def _parse_requirements(f: Path) -> List[Tuple[str, str, str]]:
    out = []
    try:
        for line in f.read_text(errors="replace").splitlines():
            m = re.match(r"^\s*([A-Za-z0-9_.-]+)\s*==\s*([A-Za-z0-9_.\-]+)", line)
            if m:
                out.append(("PyPI", m.group(1).lower(), m.group(2)))
    except OSError:
        pass
    return out


LOCKFILES = [
    ("composer.lock", _parse_composer_lock),
    ("package-lock.json", _parse_package_lock),
    ("yarn.lock", _parse_yarn_lock),
    ("requirements.txt", _parse_requirements),
]


def inventory(project: Dict) -> List[Dict]:
    """Dependencias exactas del proyecto (raíz + apps declaradas en el manifiesto)."""
    root = Path(project["abs_path"])
    dirs = [("", root)] + [(a.get("path", ""), root / a.get("path", ""))
                           for a in project.get("apps") or []]
    deps, seen = [], set()
    for app_path, d in dirs:
        if not d.is_dir():
            continue
        for fname, parser in LOCKFILES:
            f = d / fname
            if not f.is_file():
                continue
            # package-lock manda sobre yarn.lock si están ambos
            if fname == "yarn.lock" and (d / "package-lock.json").is_file():
                continue
            for eco, name, ver in parser(f):
                key = (eco, name, ver)
                if key not in seen:
                    seen.add(key)
                    deps.append({"ecosystem": eco, "name": name, "version": ver,
                                 "app": app_path or "."})
    return deps


# ── OSV ───────────────────────────────────────────────────────────────────────
def _post_json(url: str, payload: Dict, timeout: int = 60) -> Dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get_json(url: str, timeout: int = 30) -> Dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _severity_of(vuln: Dict) -> str:
    dbs = (vuln.get("database_specific") or {}).get("severity")
    if dbs:
        s = dbs.lower()
        return s if s in SEV_ORDER else "unknown"
    for sv in vuln.get("severity") or []:
        score = sv.get("score", "")
        m = re.search(r"/(?:AV|CVSS)", score)
        try:
            base = float(score) if not m else None
        except ValueError:
            base = None
        if base is None:
            continue
        if base >= 9: return "critical"
        if base >= 7: return "high"
        if base >= 4: return "moderate"
        return "low"
    return "unknown"


def _ver_key(v: str) -> Tuple[int, ...]:
    """Comparación tolerante de versiones (numérica por segmentos)."""
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:6]) or (0,)


def _fixed_version(vuln: Dict, eco: str, name: str, installed: str) -> Optional[str]:
    """La versión corregida CORRECTA para la versión instalada.

    Un advisory suele traer un rango por rama de release (ej. ws: 5.2.5, 6.2.4,
    7.5.11, 8.21.0). Se elige la menor versión fixed MAYOR que la instalada
    (el upgrade mínimo); si no hay ninguna mayor, la más alta del advisory.
    """
    fixes = []
    for aff in vuln.get("affected") or []:
        pkg = aff.get("package") or {}
        if pkg.get("ecosystem") == eco and pkg.get("name", "").lower() == name.lower():
            for rng in aff.get("ranges") or []:
                for ev in rng.get("events") or []:
                    if "fixed" in ev:
                        fixes.append(ev["fixed"])
    if not fixes:
        return None
    ik = _ver_key(installed)
    greater = [f for f in fixes if _ver_key(f) > ik]
    return min(greater, key=_ver_key) if greater else max(fixes, key=_ver_key)


def _advisory_url(vuln_id: str, aliases: List[str]) -> str:
    if vuln_id.startswith("GHSA-"):
        return "https://github.com/advisories/" + vuln_id
    return "https://osv.dev/vulnerability/" + vuln_id


def scan(projects: List[Dict]) -> Dict:
    """Escaneo completo. Devuelve y persiste el snapshot."""
    with _LOCK:
        if _STATE["scanning"]:
            return load_snapshot()
        _STATE["scanning"] = True
    try:
        return _scan(projects)
    finally:
        _STATE["scanning"] = False


def _scan(projects: List[Dict]) -> Dict:
    inv = {p["id"]: inventory(p) for p in projects if p.get("exists")}

    # Dedupe global de (eco, name, version)
    unique: Dict[Tuple[str, str, str], List[Tuple[str, str]]] = {}
    for pid, deps in inv.items():
        for d in deps:
            unique.setdefault((d["ecosystem"], d["name"], d["version"]), []).append((pid, d["app"]))

    keys = list(unique.keys())
    hits: Dict[Tuple[str, str, str], List[str]] = {}
    for i in range(0, len(keys), 950):
        chunk = keys[i:i + 950]
        payload = {"queries": [
            {"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in chunk]}
        try:
            res = _post_json(OSV_BATCH, payload)
        except Exception:
            continue
        for key, r in zip(chunk, res.get("results", [])):
            ids = [v["id"] for v in (r or {}).get("vulns") or []]
            if ids:
                hits[key] = ids

    # Detalles por vulnerabilidad única (cache por id en el snapshot previo)
    prev = load_snapshot()
    cache: Dict[str, Dict] = prev.get("vuln_cache") or {}
    todo = sorted({vid for ids in hits.values() for vid in ids if vid not in cache})

    def fetch(vid: str):
        try:
            v = _get_json(OSV_VULN % vid)
            cache[vid] = {"id": vid, "summary": v.get("summary") or (v.get("details") or "")[:140],
                          "aliases": v.get("aliases") or [], "severity": _severity_of(v),
                          "affected": v.get("affected") or []}
        except Exception:
            cache[vid] = {"id": vid, "summary": "", "aliases": [], "severity": "unknown", "affected": []}

    if todo:
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(fetch, todo))

    # Armar snapshot por proyecto
    per_project: Dict[str, Dict] = {}
    for key, vids in hits.items():
        eco, name, ver = key
        for pid, app in unique[key]:
            entry = per_project.setdefault(pid, {"counts": {s: 0 for s in SEV_ORDER}, "items": []})
            for vid in vids:
                meta = cache.get(vid) or {}
                sev = meta.get("severity", "unknown")
                entry["counts"][sev] += 1
                entry["items"].append({
                    "package": name, "version": ver, "ecosystem": eco, "app": app,
                    "vuln_id": vid, "severity": sev,
                    "summary": meta.get("summary", ""),
                    "url": _advisory_url(vid, meta.get("aliases", [])),
                    "cve": next((a for a in meta.get("aliases", []) if a.startswith("CVE-")), None),
                    "fixed": _fixed_version({"affected": meta.get("affected", [])}, eco, name, ver),
                })
    for entry in per_project.values():
        entry["items"].sort(key=lambda i: SEV_ORDER.index(i["severity"]))

    snap = {
        "scanned_at": time.strftime("%Y-%m-%d %H:%M"),
        "scanned_ts": time.time(),
        "deps_total": len(keys),
        "projects": per_project,
        "totals": {s: sum(e["counts"][s] for e in per_project.values()) for s in SEV_ORDER},
        "vuln_cache": cache,
    }
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False))
    return snap


def scan_project(project: Dict) -> Dict:
    """Re-escanea UN proyecto y fusiona el resultado en el snapshot global."""
    with _LOCK:
        if _STATE["scanning"]:
            return load_snapshot()
        _STATE["scanning"] = True
    try:
        snap = load_snapshot()
        cache: Dict[str, Dict] = snap.get("vuln_cache") or {}
        deps = inventory(project)

        unique: Dict[Tuple[str, str, str], List[str]] = {}
        for d in deps:
            unique.setdefault((d["ecosystem"], d["name"], d["version"]), []).append(d["app"])

        keys = list(unique.keys())
        hits: Dict[Tuple[str, str, str], List[str]] = {}
        for i in range(0, len(keys), 950):
            chunk = keys[i:i + 950]
            try:
                res = _post_json(OSV_BATCH, {"queries": [
                    {"package": {"ecosystem": e, "name": n}, "version": v} for e, n, v in chunk]})
            except Exception:
                continue
            for key, r in zip(chunk, res.get("results", [])):
                ids = [v["id"] for v in (r or {}).get("vulns") or []]
                if ids:
                    hits[key] = ids

        todo = sorted({vid for ids in hits.values() for vid in ids if vid not in cache})

        def fetch(vid: str):
            try:
                v = _get_json(OSV_VULN % vid)
                cache[vid] = {"id": vid, "summary": v.get("summary") or (v.get("details") or "")[:140],
                              "aliases": v.get("aliases") or [], "severity": _severity_of(v),
                              "affected": v.get("affected") or []}
            except Exception:
                cache[vid] = {"id": vid, "summary": "", "aliases": [], "severity": "unknown", "affected": []}

        if todo:
            with ThreadPoolExecutor(max_workers=12) as pool:
                list(pool.map(fetch, todo))

        entry = {"counts": {sv: 0 for sv in SEV_ORDER}, "items": [],
                 "scanned_at": time.strftime("%Y-%m-%d %H:%M")}
        for key, vids in hits.items():
            eco, name, ver = key
            for app in unique[key]:
                for vid in vids:
                    meta = cache.get(vid) or {}
                    sev = meta.get("severity", "unknown")
                    entry["counts"][sev] += 1
                    entry["items"].append({
                        "package": name, "version": ver, "ecosystem": eco, "app": app,
                        "vuln_id": vid, "severity": sev,
                        "summary": meta.get("summary", ""),
                        "url": _advisory_url(vid, meta.get("aliases", [])),
                        "cve": next((a for a in meta.get("aliases", []) if a.startswith("CVE-")), None),
                        "fixed": _fixed_version({"affected": meta.get("affected", [])}, eco, name, ver),
                    })
        entry["items"].sort(key=lambda i: SEV_ORDER.index(i["severity"]))

        pid = project["id"]
        if entry["items"]:
            snap.setdefault("projects", {})[pid] = entry
        else:
            snap.get("projects", {}).pop(pid, None)
        snap["totals"] = {sv: sum(e["counts"][sv] for e in snap["projects"].values())
                          for sv in SEV_ORDER}
        snap["vuln_cache"] = cache
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(snap, ensure_ascii=False))
        return snap
    finally:
        _STATE["scanning"] = False


def scan_project_in_thread(project: Dict) -> None:
    threading.Thread(target=scan_project, args=(project,), daemon=True).start()


def load_snapshot() -> Dict:
    if SNAPSHOT.is_file():
        try:
            return json.loads(SNAPSHOT.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"scanned_at": None, "scanned_ts": 0, "deps_total": 0,
            "projects": {}, "totals": {s: 0 for s in SEV_ORDER}, "vuln_cache": {}}


def summary() -> Dict:
    s = load_snapshot()
    return {"scanned_at": s["scanned_at"], "totals": s["totals"],
            "scanning": _STATE["scanning"]}


def is_scanning() -> bool:
    return _STATE["scanning"]


def scan_in_thread(projects: List[Dict]) -> None:
    threading.Thread(target=scan, args=(projects,), daemon=True).start()


def start_scheduler(get_projects, hours: float = 24.0) -> None:
    """Escaneo periódico — el hub es un servicio siempre vivo (LaunchAgent)."""
    def loop():
        while True:
            snap = load_snapshot()
            if time.time() - snap.get("scanned_ts", 0) > hours * 3600:
                try:
                    scan(get_projects())
                except Exception:
                    pass
            time.sleep(1800)  # re-chequea cada 30 min
    threading.Thread(target=loop, daemon=True).start()


# ── Export a Markdown ─────────────────────────────────────────────────────────
SEV_ES = {"critical": "Crítica", "high": "Alta", "moderate": "Moderada",
          "low": "Baja", "unknown": "Sin clasificar"}


def project_markdown(name: str, data: Dict, scanned_at: str) -> str:
    c = data["counts"]
    lines = [
        "# Vulnerabilidades — %s" % name,
        "",
        "> Escaneo Boiler del %s · fuente [OSV.dev](https://osv.dev) (GitHub Advisories, npm, Packagist, PyPI)" % (scanned_at or "—"),
        "",
        "**Resumen:** %d críticas · %d altas · %d moderadas · %d bajas/otras" % (
            c["critical"], c["high"], c["moderate"], c["low"] + c["unknown"]),
        "",
        "| Severidad | Paquete | Advisory | CVE | Corrige en | Detalle |",
        "|---|---|---|---|---|---|",
    ]
    for i in data["items"]:
        app = " (%s)" % i["app"] if i.get("app") and i["app"] != "." else ""
        cve = "[%s](https://nvd.nist.gov/vuln/detail/%s)" % (i["cve"], i["cve"]) if i.get("cve") else "—"
        lines.append("| %s | `%s@%s`%s | [%s](%s) | %s | %s | %s |" % (
            SEV_ES.get(i["severity"], i["severity"]), i["package"], i["version"], app,
            i["vuln_id"], i["url"], cve,
            "`%s`" % i["fixed"] if i.get("fixed") else "—",
            (i.get("summary") or "").replace("|", "\\|").replace("\n", " ")[:120]))
    lines.append("")
    return "\n".join(lines)


def full_markdown(projects_names: Dict[str, str]) -> str:
    snap = load_snapshot()
    t = snap["totals"]
    out = [
        "# Informe de vulnerabilidades — Boiler",
        "",
        "> Escaneo del %s · %d dependencias únicas · fuente OSV.dev" % (snap.get("scanned_at") or "—", snap.get("deps_total", 0)),
        "",
        "**Total:** %d críticas · %d altas · %d moderadas · %d bajas/otras" % (
            t["critical"], t["high"], t["moderate"], t["low"] + t["unknown"]),
        "",
    ]
    for pid, data in sorted(snap.get("projects", {}).items()):
        out.append(project_markdown(projects_names.get(pid, pid), data, snap.get("scanned_at")))
    return "\n".join(out)
