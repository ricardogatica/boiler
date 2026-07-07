# Hub reSTART — Plan del servicio de estado de proyectos

> Servicio en Python que muestra todos los proyectos y su avance: estado local (Docker/dev),
> git (commits, diffs), tareas por proyecto, y producción (deploy al día, health).
>
> Fecha del plan: 2026-07-04

## 1. Ubicación, nombre y contrato

- **Carpeta**: `/Users/ricardogatica/Projects/reSTART_Labs/hub/` (herramienta meta a nivel del workspace, junto a `reSTART/`, `Minicatalogo/`, `Aplicate/`).
- **Cumple el contrato Boiler** como cualquier proyecto: `run.sh` (up|down|status|logs), `.env.example`, README, CLAUDE.md.
- **Puerto/dominio**: bloque **8500** → `http://hub.restart.localhost:8500`.
- **Stack**: Python 3.12 + **FastAPI** + Uvicorn. Frontend: Jinja2 + HTMX (una página, sin build de JS). **SQLite** solo para cache/histórico (los datos maestros viven en archivos versionados, ver §3).
- Local primero (lee el filesystem y el socket de Docker — por eso NO va dockerizado: corre con `uvicorn` en el host vía `run.sh`). Deploy a producción del hub queda para una fase posterior si se quiere.

## 2. Estructura de archivos

```txt
hub/
├── run.sh                    # contrato Boiler: up (uvicorn :8500) | down | status | logs
├── README.md
├── CLAUDE.md
├── .env.example              # RAILWAY_TOKEN, GITHUB/BITBUCKET tokens (fase 3)
├── requirements.txt          # fastapi, uvicorn, jinja2, pyyaml, httpx
├── projects.yml              # ⭐ REGISTRO MAESTRO (ver abajo)
├── app/
│   ├── main.py               # FastAPI: rutas web + API JSON (/api/projects, /api/projects/{id})
│   ├── models.py             # dataclasses/pydantic: Project, GitStatus, TaskList, ProdStatus…
│   ├── collectors/
│   │   ├── registry.py       # carga projects.yml, valida rutas
│   │   ├── git.py            # branch, dirty (archivos sin commitear), ahead/behind, diff --stat, últimos commits
│   │   ├── docker_state.py   # contenedores por proyecto (labels com.docker.compose.project)
│   │   ├── homolog.py        # checklist estructura: run.sh, backup.sh, .docs/, compose en raíz, .env.example, .data/
│   │   ├── tasks.py          # lee/escribe tasks.yml de cada proyecto + cruza con git log
│   │   └── prod.py           # health checks a URLs prod + Railway API (fase 3)
│   └── web/
│       ├── templates/        # dashboard.html, project.html (Jinja + HTMX)
│       └── static/
├── data/                     # hub.db (SQLite: cache de colectores + histórico) — gitignored
└── tests/
```

### `projects.yml` — el registro maestro

Convierte en datos vivos la tabla de PLAN.md (una entrada por proyecto):

```yaml
projects:
  - id: podium
    name: Podium
    path: reSTART/podium.restart.cl        # relativo a reSTART_Labs/
    empresa: restart
    local_url: http://podium.restart.localhost:8386
    stack: [nextjs, laravel, postgres, redis]
    prod:
      provider: railway
      url: https://podium.restart.cl
      health: /api/health                  # endpoint a chequear (si existe)
    excluded: false
  # … los 18+ proyectos
```

## 3. Tareas por proyecto — diseño clave

**Las tareas viven en un archivo versionado DENTRO de cada proyecto** (`tasks.yml` en la raíz), no en una DB central: viajan con el repo, se editan también a mano o con Claude, y el hub las lee/escribe.

```yaml
# <proyecto>/tasks.yml
tasks:
  - id: POD-12
    title: Confirmación de coincidencias por el competidor
    status: doing            # todo | doing | review | done
    assignee: ricardo
    created: 2026-07-04
    notes: …
```

**Integración con el código** (lo que pediste de "revisar su integración"): convención de mencionar el ID en los commits (`POD-12: agrega endpoint de feedback`). El colector cruza `git log --grep <ID>` y muestra por tarea:

1. **Sin código** — ningún commit la menciona.
2. **En código, sin commitear** — hay diff local que la menciona o commits en rama de trabajo.
3. **Comiteada** — commits en la rama principal local.
4. **En producción** — el commit está en el deploy vigente (fase 3, vía Railway API o tag de deploy).

El avance del proyecto = tareas done/total + ese pipeline por tarea.

## 4. Qué muestra el dashboard

**Vista general** (tabla, un proyecto por fila):

| Columna | Fuente |
|---|---|
| 🟢/⚪ Local | Docker (labels compose) + puerto respondiendo |
| Git | rama · ✚N sin commitear · ↑ahead ↓behind del remoto · último commit hace X |
| Diferencias | `git diff --stat` resumido (archivos/+/-) con detalle al hacer clic |
| Tareas | done/total + cuántas en cada estado del pipeline |
| Homologación | % del checklist (run.sh, backup.sh, .docs, compose raíz, .env.example) |
| Producción | health del URL prod (up/down/latencia) · ¿deploy al día vs main? |

**Vista por proyecto**: detalle de tareas con su estado de integración, últimos commits, diff pendiente, contenedores, URLs, y botones de acción (fase 4).

## 5. Fases

1. **F1 — Núcleo (primera versión útil)**: `projects.yml` con los 18 homologados + colectores `git`, `docker_state`, `homolog` + dashboard tabla + API JSON. Sin tokens, todo local.
   > ✅ Construida 2026-07-04: `reSTART_Labs/hub/` corriendo en `hub.restart.localhost:8500`. Verificada con datos reales: 18 proyectos, detección en vivo de petsit corriendo (7 contenedores), 14 proyectos con cambios sin commitear, homologación promedio 76%.
2. **F2 — Tareas**: `tasks.yml` por proyecto (se crea vacío en cada uno), UI para crear/editar/mover tareas, cruce con `git log` (estados 1-3 del pipeline).
   > ✅ Construida 2026-07-04: `tasks.yml` sembrado en los 18 proyectos (13 arrancan con la tarea "Revisar y commitear la homologación Boiler"); crear/mover tareas desde la UI del proyecto (escriben al archivo versionado); pipeline de integración por tarea: sin código → en código sin commitear (ID en git diff) → comiteada (ID en git log). IDs automáticos por prefijo (POD-1, ENR-1…).
3. **F3 — Producción**: health checks a URLs prod + integración **Railway API** (RAILWAY_TOKEN) para saber deploy vigente y compararlo con main (estado 4 del pipeline). Bitbucket/GitHub tokens para ahead/behind sin fetch manual.
2b. **Kanban local** (✅ 2026-07-04): tablero en `/kanban` con columnas Por hacer / En curso / En revisión / Listas, global o filtrado por proyecto, drag & drop entre columnas (escribe al `tasks.yml` del proyecto), cada tarjeta con ID, proyecto e integración en el código.

2c. **Sync a Trello (diseñado, pendiente de credenciales)**: variables reservadas en `.env` (`TRELLO_API_KEY`, `TRELLO_TOKEN`, `TRELLO_BOARD_ID`). Diseño: push unidireccional primero — cada tarea gana `trello_card_id` en su `tasks.yml`; el hub crea/actualiza la tarjeta vía API REST de Trello (listas del board mapeadas a los 4 estados; el ID del hub va en el nombre de la tarjeta). Bidireccional (webhooks) se evalúa después. Para activarlo: API key en https://trello.com/app-key + token de usuario + ID del board destino.

4. **F4 — Acciones y extras**: botones "levantar/bajar" (invocan `./run.sh up|down`), "respaldar" (`backup.sh --auto`), histórico de snapshots en SQLite (avance en el tiempo), y evaluar deploy del hub mismo.
   > ✅ Parcial 2026-07-04 — **botón RUN** operativo: en dashboard y vista de proyecto (solo si está detenido), lanza `./run.sh up` como proceso independiente (sobrevive al hub) con salida a `data/logs/<id>.log`, visible en `/project/{id}/runlog` (auto-refresco 3s). Verificado end-to-end con liveness: RUN → build de imagen → corriendo → health 200. Pendiente de F4: STOP, backup desde UI, histórico.

## 6. Decisiones tomadas (2026-07-04)

1. **Carpeta `hub/`** en la raíz de reSTART_Labs, puerto **8500**, dominio `hub.restart.localhost`.
2. **Tareas en `tasks.yml` versionado por proyecto** — viajan con el repo; IDs referenciables en commits.
3. **Alcance v1: solo reSTART_Labs** (los 18 homologados); los personales se suman cuando se homologuen.
4. **Solo lectura en v1** — las acciones (run.sh up/down, backup) llegan en F4.
5. **Producción heterogénea**: Railway (incluye front.cl, que YA NO usa Netlify — referencia eliminada de su README), VPS/droplet propio y EC2. La F3 combina health checks por URL (funciona para todos) + Railway API donde aplique; VPS/EC2 quedan con health check y opcionalmente SSH después.
