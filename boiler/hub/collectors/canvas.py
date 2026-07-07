"""Business Model Canvas por proyecto — canvas.yml versionado en el repo."""
from pathlib import Path
from typing import Dict, List

import yaml

CANVAS_FILE = "canvas.yml"

# Los 9 bloques canónicos, con su posición en la grilla clásica.
BLOCKS = [
    ("key_partners", "Socios clave"),
    ("key_activities", "Actividades clave"),
    ("key_resources", "Recursos clave"),
    ("value_propositions", "Propuesta de valor"),
    ("customer_relationships", "Relación con clientes"),
    ("channels", "Canales"),
    ("customer_segments", "Segmentos de clientes"),
    ("cost_structure", "Estructura de costos"),
    ("revenue_streams", "Fuentes de ingreso"),
]
BLOCK_KEYS = [k for k, _ in BLOCKS]

HEADER = (
    "# Business Model Canvas — lo lee y edita el Hub de Boiler.\n"
    "# 9 bloques canónicos; cada uno es una lista de ítems.\n"
)


def _path(project: Dict) -> Path:
    return Path(project["abs_path"]) / CANVAS_FILE


def load(project: Dict) -> Dict[str, List[str]]:
    f = _path(project)
    data = {}
    if f.is_file():
        try:
            data = yaml.safe_load(f.read_text()) or {}
        except yaml.YAMLError:
            data = {}
    return {k: [str(i) for i in (data.get(k) or [])] for k in BLOCK_KEYS}


def save(project: Dict, canvas: Dict[str, List[str]]) -> None:
    ordered = {k: canvas.get(k, []) for k in BLOCK_KEYS}
    _path(project).write_text(HEADER + yaml.safe_dump(ordered, sort_keys=False,
                                                      allow_unicode=True, width=100))


def add_item(project: Dict, block: str, text: str) -> bool:
    if block not in BLOCK_KEYS or not text.strip():
        return False
    c = load(project)
    c[block].append(text.strip())
    save(project, c)
    return True


def remove_item(project: Dict, block: str, index: int) -> bool:
    if block not in BLOCK_KEYS:
        return False
    c = load(project)
    if 0 <= index < len(c[block]):
        c[block].pop(index)
        save(project, c)
        return True
    return False


def summary(project: Dict) -> Dict:
    c = load(project)
    filled = sum(1 for k in BLOCK_KEYS if c[k])
    return {"exists": _path(project).is_file(), "filled_blocks": filled,
            "total_items": sum(len(v) for v in c.values())}
