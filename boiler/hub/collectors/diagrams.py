"""Diagramas Mermaid de un proyecto: archivos .mmd + bloques ```mermaid en .md.

- Visor: se renderizan en el navegador con mermaid.js embebido (static/vendor).
- Export a PNG: página temporal + Chrome headless (mismo motor de las capturas).
  Convención de destino: si el .mmd vive en .../mermaid/, el PNG va al hermano
  .../png/ (convención podium); si no, junto al fuente.
"""
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from . import capture

PRUNE = {"node_modules", "vendor", ".git", ".data", ".backups", ".venv",
         ".nuxt", ".next", ".output", "dist", "storage", "__pycache__", ".yarn"}
MAX_DEPTH = 5
MMD_MAX = 60_000  # bytes por diagrama

_MD_BLOCK = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)


def list_diagrams(project: Dict) -> List[Dict]:
    root = Path(project["abs_path"])
    out: List[Dict] = []

    def walk(d: Path, depth: int) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            entries = sorted(d.iterdir(), key=lambda e: (e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            if e.is_dir() and not e.is_symlink() and e.name not in PRUNE:
                walk(e, depth + 1)
            elif e.is_file() and e.suffix.lower() == ".mmd":
                try:
                    code = e.read_text(errors="replace")[:MMD_MAX]
                except OSError:
                    continue
                rel = str(e.relative_to(root))
                png = _png_target(root, e)
                out.append({"kind": "file", "path": rel, "name": e.stem, "code": code,
                            "png": str(png.relative_to(root)) if png.is_file() else None})
            elif e.is_file() and e.suffix.lower() == ".md" and depth <= 4 \
                    and any(seg in (".docs", "docs") for seg in e.parts[len(root.parts):]):
                try:
                    text = e.read_text(errors="replace")
                except OSError:
                    continue
                for n, m in enumerate(_MD_BLOCK.finditer(text), 1):
                    rel = str(e.relative_to(root))
                    out.append({"kind": "embed", "path": rel, "name": "%s · #%d" % (e.stem, n),
                                "code": m.group(1)[:MMD_MAX], "png": None})

    walk(root, 0)
    out.sort(key=lambda d: (d["kind"] != "file", d["path"]))
    return out


def _png_target(root: Path, mmd: Path) -> Path:
    if mmd.parent.name == "mermaid":
        return mmd.parent.parent / "png" / (mmd.stem + ".png")
    return mmd.with_suffix(".png")


_EXPORT_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>body{margin:24px;background:#ffffff;font-family:-apple-system,sans-serif}</style>
</head><body>
<pre class="mermaid">%s</pre>
<script src="file://%s"></script>
<script>mermaid.initialize({startOnLoad:true, theme:"neutral"});</script>
</body></html>"""


def export_png(project: Dict, rel_path: str) -> Dict:
    """Exporta un .mmd a PNG con Chrome headless. Devuelve {ok, png?|error?}."""
    root = Path(project["abs_path"]).resolve()
    src = (root / rel_path).resolve()
    if not str(src).startswith(str(root) + "/") or src.suffix.lower() != ".mmd" or not src.is_file():
        return {"ok": False, "error": "fuente inválida"}
    binp = capture.browser_bin()
    if not binp:
        return {"ok": False, "error": "No hay Chrome/Chromium para exportar."}

    mermaid_js = Path(__file__).resolve().parents[1] / "web" / "static" / "vendor" / "mermaid.min.js"
    code = src.read_text(errors="replace")
    target = _png_target(root, src)
    target.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(_EXPORT_HTML % (code.replace("&", "&amp;").replace("<", "&lt;"), mermaid_js))
        page = f.name
    try:
        import subprocess
        r = subprocess.run(
            [binp, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--allow-file-access-from-files", "--window-size=1600,1200",
             "--virtual-time-budget=8000", "--force-device-scale-factor=2",
             "--screenshot=%s" % target, "file://%s" % page],
            capture_output=True, text=True, timeout=60)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        Path(page).unlink(missing_ok=True)
    if not target.is_file() or target.stat().st_size == 0:
        return {"ok": False, "error": (r.stderr or "export vacío").strip()[-160:]}
    return {"ok": True, "png": str(target.relative_to(root))}


def export_all(project: Dict) -> Dict:
    ok = err = 0
    for d in list_diagrams(project):
        if d["kind"] == "file":
            res = export_png(project, d["path"])
            ok += 1 if res["ok"] else 0
            err += 0 if res["ok"] else 1
    return {"ok": ok, "errors": err}
