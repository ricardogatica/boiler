"""Capturas de pantalla de los proyectos (Chrome headless del sistema).

- take(project): captura local_url → data/shots/<id>.png
- capture_when_up(project): hilo que espera a que el puerto responda tras un
  RUN y captura automáticamente (con margen de warm-up).
"""
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional

from . import docker_state

from .registry import ROOT
SHOTS_DIR = ROOT / ".boiler" / "shots"

_BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def browser_bin() -> Optional[str]:
    for b in _BROWSERS:
        if os.access(b, os.X_OK):
            return b
    return None


def take(project: Dict) -> Dict:
    """Captura la URL local del proyecto. Devuelve {ok, error?}."""
    binp = browser_bin()
    url = project.get("local_url")
    if not binp:
        return {"ok": False, "error": "No hay Chrome/Chromium instalado para capturar."}
    if not url:
        return {"ok": False, "error": "El proyecto no tiene local_url."}

    SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SHOTS_DIR / ("%s.png" % project["id"])
    tmp = SHOTS_DIR / ("%s.tmp.png" % project["id"])
    try:
        r = subprocess.run(
            [binp, "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--window-size=1280,800", "--virtual-time-budget=8000",
             "--screenshot=%s" % tmp, url],
            capture_output=True, text=True, timeout=45,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"ok": False, "error": "Chrome no respondió: %s" % e}
    if not tmp.is_file() or tmp.stat().st_size == 0:
        return {"ok": False, "error": (r.stderr or "captura vacía").strip()[-200:]}
    tmp.replace(out)
    return {"ok": True}


def info(project_id: str) -> Dict:
    f = SHOTS_DIR / ("%s.png" % project_id)
    if not f.is_file():
        return {"exists": False}
    mtime = int(f.stat().st_mtime)
    return {
        "exists": True,
        "url": "/shots/%s.png?v=%d" % (project_id, mtime),
        "taken": time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime)),
    }


def capture_when_up(project: Dict, max_wait: int = 180, warmup: int = 8) -> None:
    """Lanza un hilo: espera a que el puerto de entrada responda y captura."""
    port = project.get("port")
    if not port:
        return

    def _worker():
        waited = 0
        while waited < max_wait:
            if docker_state.port_listening(port):
                time.sleep(warmup)  # deja que el dev server termine de compilar
                take(project)
                return
            time.sleep(3)
            waited += 3

    threading.Thread(target=_worker, daemon=True).start()
