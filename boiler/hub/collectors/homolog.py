"""Checklist de homologación (contrato Boiler) por proyecto."""
import os
from pathlib import Path
from typing import Dict


def collect(project: Dict) -> Dict:
    p = Path(project["abs_path"])
    is_docker = project.get("compose_project") is not None
    has_db = project.get("has_db", False)

    checks = {}
    run_sh = p / "run.sh"
    checks["run.sh"] = {"ok": run_sh.is_file() and os.access(run_sh, os.X_OK),
                        "label": "run.sh ejecutable"}
    if has_db:
        checks["backup.sh"] = {"ok": (p / "backup.sh").is_file(), "label": "backup.sh"}
    checks[".env.example"] = {"ok": (p / ".env.example").is_file() or (p / ".env.docker").is_file(),
                              "label": ".env.example"}
    if is_docker:
        checks["compose"] = {
            "ok": (p / "docker-compose.yml").is_file() or (p / "docker-compose.yaml").is_file(),
            "label": "compose en la raíz"}
    checks["docs"] = {"ok": (p / ".docs").is_dir(), "label": ".docs/"}
    checks["claude"] = {"ok": (p / "CLAUDE.md").is_file(), "label": "CLAUDE.md"}
    if has_db and is_docker:
        checks[".data"] = {"ok": (p / ".data").is_dir(), "label": "datos en ./.data/"}

    total = len(checks)
    passed = sum(1 for c in checks.values() if c["ok"])
    return {
        "checks": checks,
        "passed": passed,
        "total": total,
        "score": round(100 * passed / total) if total else 0,
    }
