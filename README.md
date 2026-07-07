# Boiler — Sistema de gestión de proyectos

> **Boiler es un sistema a nivel de SO**: administra la carpeta raíz de proyectos, los
> estandariza mediante un **manifiesto por proyecto** (`boiler.yml`, ver `MANIFEST.md`),
> genera proyectos nuevos con la estructura correcta, y gestiona tareas, usuarios y el
> ciclo comercial (presupuestos → facturas → pagos → contabilidad). Su interfaz de
> consulta y operación es el **hub** (`reSTART_Labs/hub`, :8500).
>
> Documentos: `MANIFEST.md` (spec del manifiesto) · `SISTEMA.md` (diseño del sistema y fases B1-B5) · `PLAN.md` (homologación ejecutada) · `HUB.md` (fases del hub)
>
> Fecha del relevamiento original: 2026-07-03

---

## 1. Objetivo

Que todos los proyectos compartan una misma estructura homologada, para que Boiler pueda levantarlos sin saber nada de su stack:

- **Arranque único**: `boiler up <proyecto>` → delega en `<proyecto>/run.sh up`.
- **Respaldo estandarizado**: `boiler backup <proyecto>` → delega en `<proyecto>/backup.sh`.
- **Docker con nginx como proxy**: un solo punto de entrada por proyecto (`<proyecto>.restart.localhost:<puerto>`), enrutando a frontend / backoffice / api.
- **Optimizado por defecto**: MySQL con tuning de memoria, `mem_limit` en servicios de app, puertos sin colisiones (registro central).
- **Documentación estandarizada**: `.docs/` numerada + diagramas MermaidJS como fuente de verdad.
- **Separación clara** de frontend, backoffice y APIs cuando el proyecto lo requiera.

## 2. Modelo de referencia: `podium.restart.cl`

Es el proyecto más completo y el patrón a replicar:

```txt
podium.restart.cl/
├── run.sh                  # subcomandos: up|down|restart|build|logs|migrate|seed|queue|shell
├── README.md
├── DESIGN.md
├── .docker/
│   ├── docker-compose.yml  # nginx + postgres + redis + frontend + backoffice + vite + queue-worker
│   ├── nginx/default.conf  # proxy único :8386 → enruta por path
│   ├── php/Dockerfile
│   ├── node/Dockerfile
│   ├── postgres/init.sql
│   ├── redis/redis.conf
│   └── supervisor/queue-worker.conf
├── .docs/
│   ├── README.md           # índice navegable + resumen ejecutivo
│   ├── 01-product/         # visión, BMC, historias de usuario, MVP, glosario
│   ├── 02-architecture/
│   ├── 03-database/
│   ├── 04-flows/
│   ├── 05-backoffice/
│   ├── 06-frontend/
│   ├── 07-infrastructure/
│   ├── 08-security-privacy/
│   ├── 09-backlog/
│   ├── diagrams/
│   │   ├── README.md       # índice de diagramas
│   │   ├── mermaid/*.mmd   # fuente de verdad (14 diagramas)
│   │   └── png/            # exportados con @mermaid-js/mermaid-cli
│   └── exports/
├── frontend/               # Next.js + TypeScript (sitio público)
└── backoffice/             # Laravel 12 + Inertia + React + TS (/backoffice, /api)
```

Claves del patrón:

- **`run.sh` con subcomandos** — todo pasa por `docker compose -f .docker/docker-compose.yml`; `up` autocrea el `.env` desde `.env.docker` en el primer arranque.
- **nginx como gateway único** en `podium.restart.localhost:8386`, enrutando por path: `/` → frontend (Next.js), `/api` + `/backoffice` + `/sanctum` → Laravel. Un solo puerto expuesto al usuario.
- **`.docs/` numerada 01→09** con README índice, y `diagrams/mermaid/*.mmd` como fuente + `png/` exportado.
- Servicios con **healthchecks** y `depends_on: condition: service_healthy`.

## 3. Inventario de los 24 proyectos

| # | Proyecto | Stack principal | Layout | run.sh | Docker / nginx local | `.docs/` + diagramas |
|---|----------|----------------|--------|--------|----------------------|---------------------|
| 1 | **podium** ⭐ | Next.js + Laravel/Inertia/React | frontend + backoffice | ✅ subcomandos | ✅ `.docker/`, nginx `podium.restart.localhost:8386` | ✅ numerada 01-09 + 14 `.mmd` |
| 2 | Minicatalogo | Laravel ×5 + Nuxt ×2 + Next.js | monorepo por dominio | ✅ subcomandos (`-production`) | ✅ compose raíz + `.docker/`, nginx wildcard `*.local/.test` | temática (architecture/modules/operations), sin `.mmd` |
| 3 | petsit.cl | Laravel 11 + Inertia + Vue 3 | app única | ✅ lineal, **sin Docker** (Herd + procesos locales) | ❌ sin compose | ✅ numerada 01-09 + **74 `.mmd`** |
| 4 | petsit.app | React Native + Expo 54 | app móvil | ✅ por plataforma (ios/android) | N/A (móvil) | ✅ numerada 01-09 |
| 5 | auditapp | Express + React/Vite + Expo | backend + frontend + mobile | ✅ lineal docker | ✅ compose raíz, **nginx vacío** (puertos directos) | plana MAYÚSCULAS, mermaid embebido en `.md` |
| 6 | bogy | NestJS 11 + Prisma + Vue ×2 + RN | api + web + dashboard + mobile | ✅ wrapper compose | ✅ compose raíz, nginx por path (`server_name _`) | ✅ numerada 01-09 + 8 `.mmd` |
| 7 | IndicadoresDelDia | NestJS + Nuxt + scraper Puppeteer | api + frontend + scraper | ✅ subcomandos | ✅ compose raíz, nginx por path | temática + 9 `.mmd` |
| 8 | LearningPath | Laravel ×2 + Nuxt ×2 | monorepo 4 apps por dominio | ❌ compose directo | ✅ compose raíz + `.docker/`, nginx `*.local:8787` | temática rica, ER en `.md` |
| 9 | screening | Laravel/Inertia + Next.js 16 | dashboard + frontend | ✅ lineal con flags + Makefile | ✅ compose raíz, nginx `localhost:3335` (sin dominio) | numerada por archivo (00-07) + `.mmd` |
| 10 | inertia | NestJS + FastAPI (OCR) + Next.js | api + ocr-service + frontend | ✅ lineal (backend docker, front en host) | ✅ nginx `inertia.restart.localhost:3232` | ✅ numerada 01-09 + `.mmd` |
| 11 | enregla | Nuxt 3 full-stack + Drizzle | app única | ✅ lineal (solo pg en docker, app en host) | ⚠️ compose en `.docker/` solo Postgres, sin nginx | ✅ numerada 01-08 + `.mmd` |
| 12 | business360 | NestJS + Laravel ×4 + Nuxt | apps/ + packages/ + services/ + api/ | ✅ elaborado (flags + compose profiles) | ✅ nginx multi-tenant `*.cube360.localhost:36036` | temática + `.mmd` → svg |
| 13 | sau | Laravel/Inertia + Nuxt 4 | dashboard + frontend | ✅ subcomandos/flags | ✅ nginx por host `sau.localhost` / `app.sau.localhost:54354` | temática + mermaid en `.md` |
| 14 | taller | NestJS + Laravel + Nuxt + Expo | api + dashboard + frontend + mobile | ❌ compose directo | ✅ nginx por path `taller.restart.localhost:8383` | MAYÚSCULAS, mermaid embebido |
| 15 | vacunapp | Laravel 12 + Inertia + Vue | app única | ❌ compose directo | ✅ nginx `localhost:8089` (sin dominio) | ❌ solo README (431 líneas) |
| 16 | screening (dup) | — | — | — | — | (mismo que #9) |
| 17 | docs360 | Nuxt 3 + Prisma + MySQL | app única | ❌ `yarn dev` | ❌ sin Docker | ❌ sin docs (CLAUDE.md detallado) |
| 18 | galaxa | Nuxt 4 + Knex + OpenAI | app única | ❌ `yarn dev` | ❌ sin Docker | ❌ sin docs (CLAUDE.md detallado) |
| 19 | liveness | Python FastAPI + InsightFace | app única (main.py) | ❌ compose directo | ⚠️ compose raíz 1 servicio, sin nginx | ❌ sin docs (README excelente) |
| 20 | front.cl | Vue 3 + Vite + Express SSR | app única | ❌ `yarn dev:server` | ❌ sin Docker | ❌ sin docs |
| 21 | restart.cl | Vue 3 + Vite + Express SSR | app única | ❌ `yarn dev:server` | ❌ sin Docker | ❌ sin docs (CLAUDE.md muy completo) |
| 22 | cunde.cl | — (fase idea) | vacío | ❌ | ❌ | `.docs/` vacía |
| 23 | sgd44 | — (placeholder) | vacío | ❌ | ❌ | ❌ |
| 24 | minenode | — (solo PDFs de referencia) | no es proyecto de código | ❌ | ❌ | ❌ |

## 4. Hallazgos — dónde está la dispersión

### 4.1 `run.sh` — existe en 12 proyectos, pero con 3 escuelas distintas

1. **Subcomandos** (`up|down|logs|migrate|...`): podium, Minicatalogo, IndicadoresDelDia, sau — el estilo objetivo.
2. **Lineal con trap/cleanup** (levanta todo, Ctrl+C limpia): inertia, enregla, screening, auditapp, business360.
3. **Sin Docker** (procesos locales con Herd/nvm/Expo): petsit.cl, petsit.app.

Y 7 proyectos con código **no tienen run.sh** (LearningPath, taller, vacunapp, docs360, galaxa, liveness, front.cl, restart.cl) — arrancan con `docker compose up` directo o `yarn dev`.

### 4.2 Docker — 13 proyectos con compose, pero sin convención única

- **Ubicación del compose**: en `.docker/` (podium, enregla) vs. raíz del proyecto (todos los demás). Los Dockerfiles/config sí van consistentemente en `.docker/` (o `docker/` en taller).
- **nginx como proxy**: presente en 9 proyectos, pero con **4 convenciones de dominio distintas**:
  - `*.restart.localhost` (podium, inertia, taller) ← la más limpia, resuelve sin tocar `/etc/hosts`
  - `*.localhost` propio (sau, business360/cube360)
  - `*.local` / `*.test` (LearningPath, Minicatalogo) ← requieren `/etc/hosts` o dnsmasq
  - `localhost:puerto` sin dominio (screening, vacunapp) o `server_name _` (bogy, IndicadoresDelDia)
- **Puertos**: cada proyecto inventa los suyos (8386, 8383, 8787, 3232-3236, 3335, 8089, 36036, 54354, 51745…). Solo inertia+enregla coordinan puertos entre sí. **No existe un registro central de puertos** → riesgo de colisión al levantar 2 proyectos a la vez.
- **DB**: mitad MySQL 8, mitad Postgres 15/16 — decisión por proyecto, no hay estándar.

### 4.3 Documentación — la plantilla numerada ya es el estándar de facto en los proyectos nuevos

- **Plantilla `01-product … 09-backlog` + `diagrams/` + `exports/`**: podium, inertia, enregla, petsit.cl, petsit.app, bogy (6 proyectos, los más recientes). Es claramente la convención ganadora.
- **Temática sin numerar**: Minicatalogo, LearningPath, IndicadoresDelDia, sau, business360.
- **Plana en MAYÚSCULAS**: auditapp, taller.
- **Sin docs** (solo README o CLAUDE.md): vacunapp, docs360, galaxa, liveness, front.cl, restart.cl.

### 4.4 Diagramas Mermaid — dos formatos conviviendo

- **`.mmd` sueltos** en `diagrams/mermaid/` + export a `png/` con `@mermaid-js/mermaid-cli` (podium, inertia, enregla, petsit, bogy, screening, business360). Varios ya incluyen `mermaid-cli` como devDependency y un script `docs:generate` / `diagrams`.
- **Embebidos en `.md`** (sau, taller, auditapp, LearningPath, IndicadoresDelDia parcial).
- El export a PNG es manual en todos — nadie lo tiene automatizado en CI.

### 4.5 Otros

- **CLAUDE.md**: presente en ~10 proyectos, con calidad variable; varios proyectos solo tienen `.claude/settings.local.json`.
- **`.env.example`**: inconsistente — algunos lo tienen, otros solo `.env`, otros `.env.docker` o `config/env.example`.
- **README raíz**: desde excelente (vacunapp 431 líneas, liveness, taller) hasta vacío (sau) o boilerplate de Nuxt (galaxa).
- **Deploy**: Railway es el target dominante (screening, inertia, enregla, business360, bogy, IndicadoresDelDia); excepciones: Minicatalogo (Bitbucket Pipelines + droplet), auditapp (GitHub Actions), front.cl (Netlify).

## 5. Propuesta de estructura homologada

Tomando podium como base y corrigiendo la dispersión detectada:

```txt
<proyecto>/
├── run.sh                    # CONTRATO Boiler: up|down|restart|build|logs [svc]|status (+migrate|seed|shell|diagrams)
├── backup.sh                 # CONTRATO Boiler: respaldo guiado de DB + archivos del proyecto
├── README.md                 # qué es + quickstart (./run.sh up) + tabla de URLs/puertos
├── CLAUDE.md                 # contexto para agentes (stack, convenciones, comandos)
├── .env.example              # SIEMPRE presente; run.sh up lo copia a .env en primer arranque
├── .backups/                 # destino de backup.sh (gitignored)
├── .data/                    # persistencia de DB en la carpeta del proyecto (gitignored)
├── docker-compose.yml        # SIEMPRE en la raíz del repo (+ overlays: docker-compose.dev.yml…)
├── .docker/                  # SOLO configuraciones complementarias y Dockerfiles
│   ├── nginx/default.conf    # gateway único del proyecto
│   └── <servicio>/           # Dockerfile + config por servicio (php/, node/, mysql/, redis/…)
├── .docs/
│   ├── README.md             # índice navegable + resumen ejecutivo
│   ├── 01-product/  02-architecture/  03-database/  04-flows/
│   ├── 05-backoffice/  06-frontend/  07-infrastructure/
│   ├── 08-security-privacy/  09-backlog/
│   ├── diagrams/
│   │   ├── README.md         # índice de diagramas
│   │   ├── mermaid/*.mmd     # fuente de verdad
│   │   └── png/              # ./run.sh diagrams los regenera con mermaid-cli
│   └── exports/
├── frontend/                 # sitio público (si aplica)
├── backoffice/               # panel administración (si aplica)
└── api/                      # API standalone (si aplica; si el backoffice ya expone /api, no existe)
```

### 5.1 Contrato de `run.sh` (lo que Boiler invoca)

Subcomandos **obligatorios** — misma interfaz en todos los proyectos; por dentro cada uno hace lo que su stack necesite (compose, Herd, Expo):

| Subcomando | Comportamiento exigido |
|---|---|
| `up` | Levanta todo. Idempotente. Autocrea `.env` desde `.env.example` en primer arranque. Espera healthchecks. Corre migraciones pendientes. Termina imprimiendo la URL de entrada. |
| `down` | Baja todo lo del proyecto. **NUNCA usa `-v`** (jamás borra volúmenes). |
| `restart` | `down` + `up` sin rebuild. |
| `status` | Estado de los servicios del proyecto (corriendo/parado, puertos, memoria). Exit code 0 si todo arriba. |
| `logs [svc]` | Sigue logs de todos o de un servicio. |

Opcionales según stack: `build`, `migrate`, `seed`, `shell [svc]`, `queue`, `diagrams`.

Reglas: bash 3.2 compatible (macOS), `set -euo pipefail`, `cd "$(dirname "$0")"` al inicio, salida no-interactiva por defecto (Boiler lo llama sin TTY).

### 5.2 Contrato de `backup.sh` (respaldo guiado por proyecto)

Cada proyecto respalda **sus propios datos** — solo él sabe qué DB usa y qué carpetas importan (uploads, storage, minio):

| Invocación | Comportamiento |
|---|---|
| `./backup.sh` | **Modo guiado**: muestra qué va a respaldar (DBs detectadas, carpetas de archivos), pide confirmación, ejecuta. |
| `./backup.sh --auto` | Sin preguntas (para que Boiler/cron lo invoque). |
| `./backup.sh --list` | Lista los respaldos existentes con fecha y tamaño. |
| `./backup.sh --restore <archivo>` | Restauración guiada: SIEMPRE pide confirmación explícita, incluso con `--auto`. |

Reglas:
- Dump con el cliente del contenedor (`docker compose exec db mysqldump…` / `pg_dump`) — no requiere clientes instalados en el host.
- Si la DB está apagada, levanta **solo** el servicio de DB, respalda, y la deja como estaba.
- Destino: `.backups/<YYYY-MM-DD_HHMMSS>/` dentro del proyecto (gitignored) — `db-<nombre>.sql.gz` + `files-<carpeta>.tar.gz`.
- Retención: conserva los últimos N (default 7), avisa antes de borrar antiguos.
- Verificación: tras el dump, chequea que el archivo no esté vacío y que el gzip sea válido antes de reportar éxito.

### 5.3 Optimización por defecto (lecciones del diagnóstico Docker)

Todo compose homologado incluye:

1. **MySQL 8 con tuning**: `command: --innodb-buffer-pool-size=256M --performance-schema=OFF` (baja de ~1 GB a ~300 MB por instancia). Postgres 16 preferido en proyectos nuevos (~50 MB idle).
2. **`mem_limit` en servicios de app** (node dev servers son los más glotones: Next dev llega a 700+ MB).
3. **Healthchecks** en db/redis + `depends_on: condition: service_healthy`.
3b. **Política de restart — local vs producción**: en LOCAL nada lleva `restart: unless-stopped` (un reinicio de Docker no debe levantar proyectos que nadie pidió; todo se levanta explícito con `./run.sh up`). En PRODUCCIÓN sí corresponde. Cómo se materializa según el repo:
   - **Compose solo-local** (el deploy real es Railway/Nixpacks): un único `docker-compose.yml` SIN restart. (podium, inertia, enregla, screening, cube360, api.restart.cl, sau, auditapp, taller, vacunapp, LearningPath, petsit)
   - **Compose que también es el deploy de producción**: base `docker-compose.yml` CON `unless-stopped` + overlay `docker-compose.dev.yml` que lo anula con `restart: "no"`; `run.sh` local siempre usa `-f docker-compose.yml -f docker-compose.dev.yml`. (bogy, liveness; Minicatalogo usa la variante equivalente con `docker-compose.production.yml` separado)
4. **Puertos por bloque**: cada proyecto tiene un puerto de entrada P único y publica sus demás puertos como P+1, P+2… (bloque `P…P+9`, ver registro en `PLAN.md`). Nunca publicar puertos default pelados tipo `5432:5432` o `3306:3306` en el host.
5. **Volúmenes con nombre** para todo dato persistente (DB, uploads) — nunca datos en capa de contenedor.

### 5.4 Reglas transversales

1. **Dominio local único**: `http://<proyecto>.restart.localhost:<puerto>` — `*.localhost` resuelve sin tocar `/etc/hosts`. nginx enruta por path (`/` → frontend, `/backoffice` + `/api` → backoffice/api).
2. **Registro central de puertos**: `PORTS.md` en Boiler asigna a cada proyecto su puerto de entrada y rango interno.
3. **`run.sh`/`backup.sh` = contrato, no implementación**: un proyecto móvil implementa `up` como `expo start`; uno sin DB implementa `backup.sh` como no-op que lo declara.
4. **Diagramas**: `.mmd` como fuente + `./run.sh diagrams` regenera los PNG con mermaid-cli.

## 6. El script Boiler (diseño)

```txt
boiler list                  # proyectos registrados: estado (🟢/⚪), puerto, URL
boiler up <proyecto>         # delega a <proyecto>/run.sh up
boiler down <proyecto|all>   # baja uno o todos
boiler switch <proyecto>     # baja todo lo demás y levanta ese (RAM limitada)
boiler status                # docker ps agrupado por proyecto + memoria
boiler backup <proyecto|all> # delega a <proyecto>/backup.sh --auto
boiler doctor                # chequea Docker: RAM VM, disco/prune seguro, colisiones de puertos
```

- **Registro**: `projects.conf` en Boiler (`nombre|ruta|puerto|url`).
- **Fallback**: si un proyecto aún no tiene `run.sh`, Boiler usa `docker compose up -d` con el compose que encuentre (raíz o `.docker/`). Así sirve desde el día uno; a medida que se homologan los `run.sh`, el fallback deja de usarse.
- **Seguridad de datos**: Boiler jamás ejecuta `down -v`, `volume prune` ni `system prune --volumes`. `doctor` solo sugiere limpiezas seguras (imágenes/build cache).

## 7. Temas a decidir (conversación pendiente)

1. **¿Compose en `.docker/` o en raíz?** — Propongo `.docker/` (como podium/enregla) para dejar la raíz limpia; `run.sh` lo abstrae.
2. **DB estándar**: ¿Postgres 16 como default para proyectos nuevos y MySQL solo por legacy?
3. **Esquema de puertos**: ¿asignación por rangos (ej. proyecto N → 8N00-8N09) o registro manual en `PORTS.md`?
4. **Destino de backups**: ¿`.backups/` dentro de cada proyecto (propuesto), `~/Backups/<proyecto>/` centralizado, o ambos (local + copia central)?
5. **Migración de proyectos existentes**: orden sugerido — primero los que ya casi cumplen (podium, inertia, enregla, bogy, screening), después los que no tienen nada (docs360, galaxa, front.cl, restart.cl, vacunapp), y al final los monorepos grandes (Minicatalogo, LearningPath, business360).
