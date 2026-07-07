"""Hub reSTART — dashboard de estado de proyectos (F1 + F2 tareas + RUN)."""
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from .collectors import canvas, capture, diagrams, docker_state, docs, git, homolog, radar, registry, security, tasks

from .. import __version__

app = FastAPI(title="Hub de Boiler", version=__version__)

WEB = Path(__file__).parent / "web"
templates = Jinja2Templates(directory=str(WEB / "templates"))
templates.env.globals["boiler_version"] = __version__
app.mount("/static", StaticFiles(directory=str(WEB / "static")), name="static")
capture.SHOTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/shots", StaticFiles(directory=str(capture.SHOTS_DIR)), name="shots")

# Scheduler de seguridad: escaneo periódico de vulnerabilidades (OSV.dev)
try:
    import yaml as _yaml
    _cfg = _yaml.safe_load((Path.home() / ".boiler" / "config.yml").read_text()) or {}
    _scan_hours = float((_cfg.get("security") or {}).get("scan_hours", 24))
except Exception:
    _scan_hours = 24.0
security.start_scheduler(registry.load_projects, _scan_hours)

_CACHE: Dict = {"ts": 0.0, "snapshot": None}
CACHE_TTL = 10  # segundos


def _collect_one(project: Dict, docker_map: Dict) -> Dict:
    g = git.collect(project["abs_path"]) if project["exists"] else {"is_repo": False}
    h = homolog.collect(project) if project["exists"] else {"checks": {}, "passed": 0, "total": 0, "score": 0}

    containers = docker_map.get(project.get("compose_project") or "", [])
    port_up = docker_state.port_listening(project["port"]) if project.get("port") else False
    running = bool(containers) or port_up

    if not project["exists"]:
        local_state, local_label = "missing", "carpeta no existe"
    elif running and port_up:
        local_state, local_label = "up", "corriendo"
    elif running:
        local_state, local_label = "partial", "contenedores arriba, entrada sin responder"
    else:
        local_state, local_label = "down", "detenido"

    if not g.get("is_repo"):
        git_state, git_label = "none", "sin git"
    elif g.get("dirty", 0) > 0:
        git_state, git_label = "dirty", "%d sin commitear" % g["dirty"]
    elif g.get("ahead"):
        git_state, git_label = "ahead", "↑%d sin push" % g["ahead"]
    else:
        git_state, git_label = "clean", "limpio"

    return {
        "id": project["id"],
        "name": project["name"],
        "path": project["path"],
        "empresa": project.get("empresa"),
        "local_url": project.get("local_url"),
        "port": project.get("port") or 0,
        "workspace": project.get("workspace"),
        "stack": project.get("stack", []),
        "local": {"state": local_state, "label": local_label,
                  "containers": containers, "port_up": port_up},
        "git": dict(g, state=git_state, label=git_label),
        "homolog": h,
        "tasks": tasks.summary(project) if project["exists"] else {"exists": False, "total": 0, "done": 0, "open": 0, "by_status": {}},
        "shot": capture.info(project["id"]),
    }


def snapshot(force: bool = False) -> Dict:
    now = time.time()
    if not force and _CACHE["snapshot"] and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["snapshot"]

    projects = registry.load_projects()
    docker_map = docker_state.docker_running_by_project()
    docker_ok = "__docker_down__" not in docker_map

    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda p: _collect_one(p, docker_map), projects))

    snap = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "docker_ok": docker_ok,
        "totals": {
            "projects": len(rows),
            "running": sum(1 for r in rows if r["local"]["state"] in ("up", "partial")),
            "dirty": sum(1 for r in rows if r["git"]["state"] == "dirty"),
            "homolog_avg": round(sum(r["homolog"]["score"] for r in rows) / len(rows)) if rows else 0,
            "open_tasks": sum(r["tasks"]["open"] for r in rows),
        },
        "security": security.summary(),
        "projects": rows,
    }
    _CACHE["snapshot"] = snap
    _CACHE["ts"] = now
    return snap


@app.get("/api/projects")
def api_projects(refresh: bool = False):
    return snapshot(force=refresh)


@app.get("/api/projects/{project_id}")
def api_project(project_id: str):
    snap = snapshot()
    for r in snap["projects"]:
        if r["id"] == project_id:
            detail = dict(r)
            try:
                p = registry.get_project(project_id)
            except KeyError:
                raise HTTPException(404)
            detail["log"] = git.recent_log(p["abs_path"])
            detail["diff_stat"] = git.diff_stat(p["abs_path"])
            detail["tasks"] = tasks.collect(p)
            return detail
    raise HTTPException(404)


def _invalidate():
    _CACHE["ts"] = 0.0


LOG_DIR = registry.ROOT / ".boiler" / "logs"


def _is_running(row: Dict) -> bool:
    return row["local"]["state"] in ("up", "partial")


@app.post("/project/{project_id}/run")
def run_project(project_id: str):
    """Lanza ./run.sh up como proceso independiente (sobrevive al hub)."""
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    snap = snapshot(force=True)
    row = next((r for r in snap["projects"] if r["id"] == project_id), None)
    if row and _is_running(row):
        return RedirectResponse("/project/%s" % project_id, status_code=303)

    run_sh = Path(p["abs_path"]) / "run.sh"
    if not run_sh.is_file():
        raise HTTPException(400, "El proyecto no tiene run.sh")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / ("%s.log" % project_id), "w")
    subprocess.Popen(
        ["./run.sh", "up"],
        cwd=p["abs_path"], stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    # Captura automática cuando el puerto de entrada empiece a responder.
    capture.capture_when_up(p)
    _invalidate()
    return RedirectResponse("/project/%s" % project_id, status_code=303)


@app.post("/project/{project_id}/stop")
def stop_project(project_id: str):
    """Lanza ./run.sh down en segundo plano (append al mismo log)."""
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    run_sh = Path(p["abs_path"]) / "run.sh"
    if not run_sh.is_file():
        raise HTTPException(400, "El proyecto no tiene run.sh")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = open(LOG_DIR / ("%s.log" % project_id), "a")
    log.write("\n───── ./run.sh down (desde el hub) ─────\n")
    log.flush()
    subprocess.Popen(
        ["./run.sh", "down"],
        cwd=p["abs_path"], stdout=log, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, start_new_session=True,
    )
    _invalidate()
    return RedirectResponse("/project/%s" % project_id, status_code=303)


@app.post("/project/{project_id}/capture")
def capture_now(project_id: str):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    capture.take(p)
    _invalidate()
    return RedirectResponse("/project/%s" % project_id, status_code=303)


@app.get("/project/{project_id}/runlog", response_class=HTMLResponse)
def run_log(project_id: str, lines: int = 120):
    f = LOG_DIR / ("%s.log" % project_id)
    if not f.is_file():
        content = "(sin log — este proyecto aún no se ha lanzado desde el hub)"
    else:
        content = "\n".join(f.read_text(errors="replace").splitlines()[-lines:])
    return HTMLResponse(
        "<html><head><meta http-equiv='refresh' content='3'>"
        "<link rel='stylesheet' href='/static/style.css'></head>"
        "<body><header><h1><a class='muted' href='/project/%s'>%s</a> / log de arranque</h1>"
        "<div class='meta'><span class='muted small'>se refresca cada 3s</span></div></header>"
        "<pre>%s</pre></body></html>"
        % (project_id, project_id, content.replace("&", "&amp;").replace("<", "&lt;"))
    )


@app.post("/project/{project_id}/tasks")
def create_task(project_id: str, title: str = Form(...), notes: str = Form(""),
                back: str = Form("")):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    if title.strip():
        tasks.add(p, title, notes)
        _invalidate()
    dest = back if back.startswith("/") else "/project/%s" % project_id
    return RedirectResponse(dest, status_code=303)


@app.post("/project/{project_id}/tasks/{task_id}/status")
def move_task(project_id: str, task_id: str, status: str = Form(...)):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    tasks.update(p, task_id, status=status)
    _invalidate()
    return RedirectResponse("/project/%s" % project_id, status_code=303)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, refresh: bool = False):
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "snap": snapshot(force=refresh)}
    )


@app.get("/kanban", response_class=HTMLResponse)
def kanban(request: Request, project: Optional[str] = None):
    """Tablero kanban global (o filtrado por proyecto) sobre los tasks.yml."""
    projects = registry.load_projects()
    if project:
        projects = [p for p in projects if p["id"] == project]

    def _tasks_for(p: Dict) -> List[Dict]:
        if not p["exists"]:
            return []
        detail = tasks.collect(p)
        return [dict(t, project_id=p["id"], project_name=p["name"]) for t in detail["tasks"]]

    with ThreadPoolExecutor(max_workers=8) as pool:
        all_tasks = [t for ts in pool.map(_tasks_for, projects) for t in ts]

    columns = []
    for status in tasks.STATUSES:
        columns.append({
            "status": status,
            "title": {"todo": "Por hacer", "doing": "En curso",
                      "review": "En revisión", "done": "Listas"}[status],
            "tasks": [t for t in all_tasks if t.get("status", "todo") == status],
        })
    return templates.TemplateResponse(
        "kanban.html",
        {"request": request, "columns": columns, "filter_project": project,
         "total": len(all_tasks),
         "project_list": [{"id": p["id"], "name": p["name"]} for p in registry.load_projects()]},
    )


@app.get("/radar", response_class=HTMLResponse)
def radar_page(request: Request):
    projects = registry.load_projects()
    return templates.TemplateResponse("radar.html", {
        "request": request,
        "versions": radar.versions(projects),
        "backups": radar.backups(projects),
        "ports": radar.ports_map(projects),
    })


@app.get("/security", response_class=HTMLResponse)
def security_page(request: Request):
    snap = security.load_snapshot()
    projects = {p["id"]: p for p in registry.load_projects()}
    rows = []
    for pid, data in sorted(snap.get("projects", {}).items()):
        p = projects.get(pid)
        rows.append({"id": pid, "name": p["name"] if p else pid,
                     "counts": data["counts"], "vulns": data["items"]})
    rows.sort(key=lambda r: (-r["counts"]["critical"], -r["counts"]["high"],
                             -r["counts"]["moderate"], -r["counts"]["low"], r["id"]))
    clean = [p for pid, p in sorted(projects.items()) if pid not in snap.get("projects", {})]
    return templates.TemplateResponse("security.html", {
        "request": request, "snap": snap, "rows": rows, "clean": clean,
        "scanning": security.is_scanning(),
    })


@app.post("/security/scan")
def security_scan():
    security.scan_in_thread(registry.load_projects(force=True))
    return RedirectResponse("/security", status_code=303)


@app.post("/security/scan/{project_id}")
def security_scan_project(project_id: str):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    security.scan_project_in_thread(p)
    return RedirectResponse("/security", status_code=303)


@app.get("/security/report.md")
def security_report_md(download: bool = False):
    from fastapi.responses import PlainTextResponse
    names = {p["id"]: p["name"] for p in registry.load_projects()}
    md = security.full_markdown(names)
    headers = {"Content-Disposition": 'attachment; filename="vulnerabilidades-boiler.md"'} if download else {}
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8", headers=headers)


@app.get("/security/{project_id}.md")
def security_project_md(project_id: str, download: bool = False):
    from fastapi.responses import PlainTextResponse
    snap = security.load_snapshot()
    data = snap.get("projects", {}).get(project_id)
    if data is None:
        raise HTTPException(404, "Sin hallazgos para ese proyecto (o sin escaneos)")
    try:
        name = registry.get_project(project_id)["name"]
    except KeyError:
        name = project_id
    md = security.project_markdown(name, data, snap.get("scanned_at"))
    headers = {"Content-Disposition": 'attachment; filename="vulns-%s.md"' % project_id} if download else {}
    return PlainTextResponse(md, media_type="text/markdown; charset=utf-8", headers=headers)


@app.get("/api/security")
def api_security():
    return security.load_snapshot()


@app.get("/project/{project_id}/diagrams", response_class=HTMLResponse)
def diagrams_page(request: Request, project_id: str, ok: Optional[int] = None, err: Optional[int] = None):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    exported = {"ok": ok, "errors": err or 0} if ok is not None else None
    return templates.TemplateResponse("diagrams.html", {
        "request": request, "project": p,
        "diagrams": diagrams.list_diagrams(p), "exported": exported,
    })


@app.post("/project/{project_id}/diagrams/export")
def diagrams_export(project_id: str, path: str = Form(...)):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    if path == "__all__":
        res = diagrams.export_all(p)
        return RedirectResponse("/project/%s/diagrams?ok=%d&err=%d" % (project_id, res["ok"], res["errors"]),
                                status_code=303)
    res = diagrams.export_png(p, path)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "error de export"))
    return RedirectResponse("/project/%s/diagrams?ok=1&err=0" % project_id, status_code=303)


@app.get("/project/{project_id}/diagrams/png")
def diagrams_png(project_id: str, f: str):
    from fastapi.responses import FileResponse
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    root = Path(p["abs_path"]).resolve()
    target = (root / f).resolve()
    if not str(target).startswith(str(root) + "/") or target.suffix != ".png" or not target.is_file():
        raise HTTPException(404)
    return FileResponse(str(target))


@app.get("/project/{project_id}/canvas", response_class=HTMLResponse)
def canvas_page(request: Request, project_id: str):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    return templates.TemplateResponse("canvas.html", {
        "request": request, "project": p, "blocks": canvas.BLOCKS,
        "canvas": canvas.load(p), "summary": canvas.summary(p),
    })


@app.post("/project/{project_id}/canvas/add")
def canvas_add(project_id: str, block: str = Form(...), text: str = Form("")):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    canvas.add_item(p, block, text)
    return RedirectResponse("/project/%s/canvas" % project_id, status_code=303)


@app.post("/project/{project_id}/canvas/remove")
def canvas_remove(project_id: str, block: str = Form(...), index: int = Form(...)):
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    canvas.remove_item(p, block, index)
    return RedirectResponse("/project/%s/canvas" % project_id, status_code=303)


@app.get("/project/{project_id}/docs", response_class=HTMLResponse)
def project_docs(request: Request, project_id: str, f: Optional[str] = None):
    """Visor de Markdown del proyecto (como verlo en el repo)."""
    try:
        p = registry.get_project(project_id)
    except KeyError:
        raise HTTPException(404)
    files = docs.list_md(p)
    doc = None
    if f:
        doc = docs.read_md(p, f)
        if doc is None:
            raise HTTPException(404, "Documento no encontrado")
    elif files:
        doc = docs.read_md(p, files[0]["path"])
    return templates.TemplateResponse(
        "docs.html",
        {"request": request, "project": p, "files": files, "doc": doc},
    )


@app.get("/project/{project_id}", response_class=HTMLResponse)
def project_page(request: Request, project_id: str):
    detail = api_project(project_id)
    return templates.TemplateResponse(
        "project.html", {"request": request, "p": detail, "snap": snapshot()}
    )
