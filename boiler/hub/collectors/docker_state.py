"""Contenedores corriendo por proyecto (label com.docker.compose.project) + puertos locales."""
import socket
import subprocess
from typing import Dict, List


def docker_running_by_project() -> Dict[str, List[Dict]]:
    """Un solo `docker ps` para todos: {compose_project: [contenedores]}."""
    try:
        out = subprocess.run(
            ["docker", "ps", "--format",
             '{{.Label "com.docker.compose.project"}}\t{{.Names}}\t{{.Status}}'],
            capture_output=True, text=True, timeout=6,
        )
        if out.returncode != 0:
            return {"__docker_down__": []}
    except (subprocess.TimeoutExpired, OSError):
        return {"__docker_down__": []}

    grouped: Dict[str, List[Dict]] = {}
    for line in out.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        project, name, status = parts
        grouped.setdefault(project or "_sin_label_", []).append(
            {"name": name, "status": status}
        )
    return grouped


def port_listening(port: int, timeout: float = 0.3) -> bool:
    # Los dev servers de Node suelen escuchar solo en ::1 (IPv6), así que se prueban ambos loopbacks.
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            continue
    return False
