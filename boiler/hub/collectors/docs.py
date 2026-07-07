"""Documentos Markdown de un proyecto — listado y lectura segura (visor del hub)."""
from pathlib import Path
from typing import Dict, List, Optional

import markdown

PRUNE = {
    "node_modules", "vendor", ".git", ".data", ".backups", ".venv", "data",
    ".nuxt", ".next", ".output", "dist", "storage", "__pycache__", ".yarn",
}
MAX_DEPTH = 4
MAX_FILES = 300

_MD = markdown.Markdown(extensions=["fenced_code", "tables", "toc", "sane_lists"])


def list_md(project: Dict) -> List[Dict]:
    """Todos los .md del proyecto (poda de directorios pesados), README primero."""
    root = Path(project["abs_path"])
    found: List[Dict] = []

    def walk(d: Path, depth: int) -> None:
        if depth > MAX_DEPTH or len(found) >= MAX_FILES:
            return
        try:
            entries = sorted(d.iterdir(), key=lambda e: (e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            if len(found) >= MAX_FILES:
                return
            if e.is_dir() and not e.is_symlink() and e.name not in PRUNE:
                walk(e, depth + 1)
            elif e.is_file() and e.suffix.lower() == ".md":
                rel = str(e.relative_to(root))
                found.append({"path": rel, "name": e.name,
                              "dir": str(e.parent.relative_to(root)) or "."})

    walk(root, 0)
    found.sort(key=lambda f: (f["name"].upper() != "README.MD" or f["dir"] != ".",
                              f["dir"], f["name"].lower()))
    return found


def read_md(project: Dict, rel_path: str) -> Optional[Dict]:
    """Lee y renderiza un .md, protegido contra path traversal."""
    root = Path(project["abs_path"]).resolve()
    target = (root / rel_path).resolve()
    if not str(target).startswith(str(root) + "/") or target.suffix.lower() != ".md" \
            or not target.is_file():
        return None
    raw = target.read_text(errors="replace")
    _MD.reset()
    return {"path": rel_path, "html": _MD.convert(raw), "raw": raw}
