"""Tareas por proyecto: tasks.yml versionado en la raíz de cada repo.

Pipeline de integración por tarea (cruce con git):
  none      → ningún commit ni diff menciona el ID
  wip       → el ID aparece en cambios SIN commitear (git diff)
  committed → hay commits que mencionan el ID
  (prod     → F3: el commit está en el deploy vigente)
"""
import datetime
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

import yaml

TASKS_FILE = "tasks.yml"
STATUSES = ["todo", "doing", "review", "done"]

HEADER = (
    "# Tareas del proyecto — las lee y edita el Hub reSTART (hub.restart.localhost:8500).\n"
    "# Convención: menciona el ID en tus commits (ej. \"%s-1: agrega endpoint X\")\n"
    "# para que el hub detecte la integración en el código.\n"
)


def prefix_for(project: Dict) -> str:
    return project.get("task_prefix") or project["id"][:3].upper()


def _path(project: Dict) -> Path:
    return Path(project["abs_path"]) / TASKS_FILE


def load(project: Dict) -> List[Dict]:
    f = _path(project)
    if not f.is_file():
        return []
    try:
        data = yaml.safe_load(f.read_text()) or {}
    except yaml.YAMLError:
        return []
    return [t for t in (data.get("tasks") or []) if isinstance(t, dict) and t.get("id")]


def save(project: Dict, tasks: List[Dict]) -> None:
    body = yaml.safe_dump({"tasks": tasks}, sort_keys=False, allow_unicode=True)
    _path(project).write_text(HEADER % prefix_for(project) + body)


def summary(project: Dict) -> Dict:
    """Resumen liviano para el dashboard (solo lee el archivo, sin git)."""
    tasks = load(project)
    by_status = {s: 0 for s in STATUSES}
    for t in tasks:
        s = t.get("status", "todo")
        by_status[s if s in by_status else "todo"] += 1
    return {
        "exists": _path(project).is_file(),
        "total": len(tasks),
        "done": by_status["done"],
        "open": len(tasks) - by_status["done"],
        "by_status": by_status,
    }


def _git_out(path: str, *args: str, timeout: int = 8) -> str:
    try:
        out = subprocess.run(["git", "-C", path] + list(args),
                             capture_output=True, text=True, timeout=timeout)
        return out.stdout if out.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def collect(project: Dict) -> Dict:
    """Detalle con integración git por tarea (para la vista de proyecto)."""
    tasks = load(project)
    path = project["abs_path"]
    diff_text = ""
    if tasks:
        diff_text = _git_out(path, "diff") + _git_out(path, "diff", "--cached")

    enriched = []
    for t in tasks:
        tid = str(t["id"])
        log = _git_out(path, "log", "--grep", tid, "--format=%h|%cr|%s", "-5")
        commits = []
        for line in log.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                commits.append({"hash": parts[0], "when": parts[1], "subject": parts[2]})
        in_diff = tid in diff_text
        if commits:
            integration, integration_label = "committed", "comiteada (%d commits)" % len(commits)
        elif in_diff:
            integration, integration_label = "wip", "en código, sin commitear"
        else:
            integration, integration_label = "none", "sin código"
        enriched.append(dict(t, commits=commits,
                             integration=integration, integration_label=integration_label))

    s = summary(project)
    s["tasks"] = enriched
    return s


def add(project: Dict, title: str, notes: str = "") -> Dict:
    tasks = load(project)
    pre = prefix_for(project)
    max_n = 0
    for t in tasks:
        tid = str(t.get("id", ""))
        if tid.startswith(pre + "-"):
            try:
                max_n = max(max_n, int(tid.split("-", 1)[1]))
            except ValueError:
                pass
    task = {
        "id": "%s-%d" % (pre, max_n + 1),
        "title": title.strip(),
        "status": "todo",
        "created": datetime.date.today().isoformat(),
    }
    if notes.strip():
        task["notes"] = notes.strip()
    tasks.append(task)
    save(project, tasks)
    return task


def update(project: Dict, task_id: str, status: Optional[str] = None,
           title: Optional[str] = None, notes: Optional[str] = None) -> bool:
    tasks = load(project)
    changed = False
    for t in tasks:
        if str(t.get("id")) == task_id:
            if status in STATUSES:
                t["status"] = status
            if title is not None and title.strip():
                t["title"] = title.strip()
            if notes is not None:
                if notes.strip():
                    t["notes"] = notes.strip()
                else:
                    t.pop("notes", None)
            changed = True
            break
    if changed:
        save(project, tasks)
    return changed
