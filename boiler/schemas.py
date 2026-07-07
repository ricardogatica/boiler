"""Schemas de Boiler — la forma canónica de cada tipo de proyecto.

Un schema define: cómo DETECTAR que un proyecto existente es de ese tipo,
qué ESTRUCTURA de archivos le corresponde (el contrato Boiler), y cómo se
COMPONE con otros (multi-app = composición de schemas de rol que se comunican
por convenciones fijas: nginx de entrada, DNS interno de compose, DB compartida).

Lo usa `boiler add` para adoptar proyectos existentes: detecta el schema,
genera el boiler.yml y entrega el informe de estructura recomendada.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PRUNE = {"node_modules", "vendor", ".git", ".data", ".backups", ".venv",
         ".nuxt", ".next", ".output", "dist", "storage", "__pycache__", ".yarn"}


# ── Detección de stack en UNA carpeta de app ─────────────────────────────────
def detect_stack(d: Path) -> Optional[Dict]:
    """Detecta el stack de una carpeta que contiene UNA aplicación."""
    pkg = {}
    if (d / "package.json").is_file():
        try:
            pkg = json.loads((d / "package.json").read_text())
        except (json.JSONDecodeError, OSError):
            pkg = {}
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}

    if (d / "artisan").is_file() or ((d / "composer.json").is_file()
            and "laravel/framework" in (d / "composer.json").read_text()):
        return {"stack": "laravel", "lang": "php", "role": "backoffice", "needs_db": True}
    if "@nestjs/core" in deps:
        return {"stack": "nestjs", "lang": "node", "role": "api", "needs_db": True}
    if "nuxt" in deps:
        # Nuxt con server/api o un ORM → full-stack; si no, front
        fullstack = (d / "server").is_dir() or any(k in deps for k in ("prisma", "drizzle-orm", "knex", "@prisma/client"))
        return {"stack": "nuxt", "lang": "node", "role": "frontend", "needs_db": fullstack}
    if "next" in deps:
        return {"stack": "nextjs", "lang": "node", "role": "frontend", "needs_db": False}
    if "astro" in deps:
        return {"stack": "astro", "lang": "node", "role": "frontend", "needs_db": False}
    if "express" in deps:
        ssr = bool(deps.get("vite")) and (d / "server.js").is_file()
        return {"stack": "express-ssr" if ssr else "express", "lang": "node",
                "role": "frontend" if ssr else "api", "needs_db": not ssr}
    if "react-native" in deps or "expo" in deps:
        return {"stack": "expo", "lang": "node", "role": "mobile", "needs_db": False}
    if "vue" in deps and "vite" in deps:
        return {"stack": "vue-vite", "lang": "node", "role": "frontend", "needs_db": False}
    if "react" in deps and "vite" in deps:
        return {"stack": "react-vite", "lang": "node", "role": "frontend", "needs_db": False}
    if (d / "requirements.txt").is_file():
        req = (d / "requirements.txt").read_text().lower()
        if "fastapi" in req:
            return {"stack": "fastapi", "lang": "python", "role": "api", "needs_db": False}
        if "django" in req:
            return {"stack": "django", "lang": "python", "role": "backoffice", "needs_db": True}
        return {"stack": "python", "lang": "python", "role": "api", "needs_db": False}
    if (d / "Cake").is_dir() or ((d / "webroot").is_dir() and (d / "Controller").is_dir()):
        return {"stack": "cakephp", "lang": "php", "role": "backoffice", "needs_db": True}
    if (d / "composer.json").is_file() or ((d / "index.php").is_file() and (d / "webroot").is_dir()):
        return {"stack": "php", "lang": "php", "role": "backoffice", "needs_db": True}
    if pkg:
        return {"stack": "node", "lang": "node", "role": "frontend", "needs_db": False}
    return None


def detect_db(root: Path, compose_text: str) -> str:
    t = compose_text.lower()
    if "image: mysql" in t or "mysql:" in t and "image" in t:
        return "mysql"
    if "postgres" in t:
        return "postgres"
    return "none"


def find_compose(root: Path) -> Optional[Path]:
    for name in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"):
        if (root / name).is_file():
            return root / name
    # fuera de estándar (lección: debe vivir en la raíz)
    for name in (".docker/docker-compose.yml", ".docker/docker-compose.yaml"):
        if (root / name).is_file():
            return root / name
    return None


def detect_entry_port(compose_text: str) -> Optional[int]:
    ports = [int(m) for m in re.findall(r'["\s-](\d{4,5}):\d+', compose_text)]
    return min(ports) if ports else None


# ── Análisis del proyecto completo ────────────────────────────────────────────
def analyze(root: Path) -> Dict:
    """Analiza un proyecto existente y propone schema + manifiesto + informe."""
    root = root.resolve()
    top = detect_stack(root)

    # ¿Multi-app? — apps en subcarpetas de primer/segundo nivel
    apps: List[Dict] = []
    candidates = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name not in PRUNE and not child.name.startswith("."):
            candidates.append(child)
            if (child / "apps").is_dir() or child.name == "apps":
                candidates.extend(c for c in sorted(child.iterdir())
                                  if c.is_dir() and not c.name.startswith("."))
    for c in candidates:
        st = detect_stack(c)
        if st:
            apps.append({"name": c.name, "path": str(c.relative_to(root)), **st})

    compose = find_compose(root)
    compose_text = compose.read_text() if compose else ""
    db = detect_db(root, compose_text)
    port = detect_entry_port(compose_text)

    if len(apps) >= 2 and not top:
        ptype = "multi-app"
        needs_db = db != "none" or any(a["needs_db"] for a in apps)
        stacks = sorted({a["stack"] for a in apps})
    elif top:
        stacks = [top["stack"]]
        if top["role"] == "mobile":
            ptype = "mobile"
        elif top["role"] == "api":
            ptype = "api"
        elif top["needs_db"] or db != "none":
            ptype = "app"
        else:
            ptype = "landing"
        needs_db = top["needs_db"] or db != "none"
    else:
        ptype, stacks, needs_db = "app", [], db != "none"

    return {
        "type": ptype, "stacks": stacks, "apps": apps if ptype == "multi-app" else [],
        "db": db if db != "none" else ("mysql" if needs_db else "none"),
        "db_detected": db, "needs_db": needs_db,
        "compose": compose, "port_detected": port,
        "recommendations": recommend(root, ptype, apps, compose,
                                     db if db != "none" else ("mysql" if needs_db else "none"),
                                     needs_db),
    }


# ── Recomendaciones de estructura (el schema hablando) ────────────────────────
def recommend(root: Path, ptype: str, apps: List[Dict], compose: Optional[Path],
              db: str, needs_db: bool) -> List[Tuple[str, str]]:
    """[(nivel ✓|→|⚠, mensaje)] — la mejor estructura según el schema."""
    r: List[Tuple[str, str]] = []

    def check(ok: bool, okmsg: str, fixmsg: str, warn: bool = False):
        r.append(("✓", okmsg) if ok else (("⚠" if warn else "→"), fixmsg))

    check((root / "run.sh").is_file(), "run.sh presente",
          "Crear run.sh con el contrato up|down|restart|status|logs|backup (Boiler §5.1)")
    if needs_db:
        check((root / "backup.sh").is_file(), "backup.sh presente",
              "Crear backup.sh (guiado + --auto + --restore) — Boiler §5.2")
        data_ok = (root / ".data").is_dir()
        vol_warn = compose is not None and ":/var/lib/" in compose.read_text() and "./.data" not in compose.read_text()
        fix = ("Mover los datos de la DB a bind mount ./.data/<motor> (hoy en volumen con nombre)"
               if vol_warn else "Persistir los datos de la DB en ./.data/<motor> (bind mount dentro del proyecto)")
        check(data_ok and not vol_warn, "datos persistiendo en ./.data/", fix, warn=vol_warn)
    if ptype in ("app", "multi-app", "api") and needs_db:
        if compose is None:
            r.append(("⚠", "Sin docker-compose.yml: generar compose con DB (%s) + nginx de entrada" % db))
        elif ".docker" in str(compose):
            r.append(("→", "Mover el compose a la RAÍZ del repo (.docker/ es solo para Dockerfiles y configs)"))
        else:
            r.append(("✓", "compose en la raíz"))
        if compose is not None and "restart: unless-stopped" in compose.read_text():
            r.append(("→", "Quitar `restart: unless-stopped` del compose local (o moverlo a un overlay de producción)"))
    check((root / ".env.example").is_file() or (root / ".env.docker").is_file(),
          ".env.example presente", "Crear .env.example (run.sh lo copia a .env en el primer up)")
    check((root / ".docs").is_dir() or (root / "docs").is_dir(), "documentación presente",
          "Crear .docs/ (convención numerada 01-product…09-backlog + diagrams/)")
    check((root / ".git").is_dir(), "repo git propio",
          "git init + remoto (github/bitbucket/gitlab)")

    if ptype == "multi-app":
        roles = {a["role"] for a in apps}
        r.append(("✓" if apps else "⚠",
                  "Apps detectadas: %s" % ", ".join("%s (%s→%s)" % (a["name"], a["stack"], a["role"]) for a in apps)
                  if apps else "Multi-app sin apps reconocibles"))
        r.append(("→", "Comunicación entre apps (schema multi-app): nginx único de entrada enrutando "
                       "por path o subdominio; las apps se hablan por DNS interno de compose "
                       "(http://<servicio>:puerto); UNA base de datos compartida con una database por app "
                       "o prefijos — nunca motores duplicados"))
        if "frontend" not in roles:
            r.append(("→", "Falta una app con rol frontend (carpeta frontend/)"))
        if not ({"backoffice", "api"} & roles):
            r.append(("→", "Falta una app backoffice o api"))
    return r
