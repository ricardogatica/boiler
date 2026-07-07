# Boiler

**Sistema para crear, levantar y gestionar todos tus proyectos desde un solo lugar.**

Boiler es una CLI global + un hub web. Se inicia en cualquier carpeta (vacía o con
proyectos existentes), estandariza cada proyecto con un manifiesto (`boiler.yml`), y
levanta un **hub** que muestra todos tus proyectos y su estado real: git, Docker,
tareas, documentación, diagramas, vulnerabilidades y versiones — todo en vivo.

- **Repo:** https://github.com/ricardogatica/boiler
- **Versión:** 0.0.5

---

## Instalación

```sh
git clone https://github.com/ricardogatica/boiler.git
cd boiler
./install.sh          # crea el venv, instala deps y enlaza `boiler` en el PATH
```

Si `~/.local/bin` no está en tu PATH, agrégalo a `~/.zshrc`:
`export PATH="$HOME/.local/bin:$PATH"`.

Actualizar más adelante: **`boiler update`** (git pull + deps + reinicia el hub).

## Inicio rápido

```sh
cd ~/Projects/MiEmpresa    # cualquier carpeta, vacía o con proyectos
boiler init               # registra el workspace
boiler add .              # adopta proyectos existentes (o crea con: boiler new)
boiler service install    # el hub queda corriendo siempre (macOS LaunchAgent)
open http://localhost:8500
```

## Comandos

| Comando | Qué hace |
|---|---|
| `boiler init [nombre]` | Registra la carpeta actual como **workspace** en `~/.boiler/`. |
| `boiler new <nombre>` | **Wizard**: crea un proyecto nuevo. Pregunta lo esencial (¿multi-app?, ¿base de datos?) y arma la estructura — front simple (Vue/React/Vite, Astro, Nuxt, Next), app con DB (compose + `.docker/` + `backup.sh`), o multi-app (frontend + backoffice + nginx). |
| `boiler add [ruta]` | **Adopta** un proyecto existente: detecta su stack, genera su `boiler.yml` y recomienda la mejor estructura. |
| `boiler list` | Proyectos del workspace actual con su estado. |
| `boiler up\|down\|status <id>` | Delega en el `run.sh` del proyecto. |
| `boiler hub` | Levanta el hub en primer plano (global: todos los workspaces). |
| `boiler service install\|uninstall\|status` | El hub como servicio de macOS (arranca al iniciar sesión). |
| `boiler workspaces` | Todos los workspaces registrados. |
| `boiler ports` | Mapa global de puertos, con detección de solapes. |
| `boiler audit` | Escaneo de vulnerabilidades (OSV.dev) de todos los proyectos. |
| `boiler version` / `boiler update` | Versión instalada / actualiza desde el repo. |

## El hub (`http://localhost:8500`)

Un solo servicio que agrega **todos** los workspaces registrados. Secciones:

- **Tablero** — cada proyecto anclado por su puerto: estado local (Docker + puerto),
  git (rama, sin commitear, último commit enlazado al repo), tareas, homologación,
  captura. Botones **Run / Stop** (invocan `run.sh`) y captura automática al levantar.
  Filtros y orden por columna.
- **Kanban** — tareas de todos los proyectos (`tasks.yml` versionado), drag & drop,
  alta directa, con el estado de integración en el código por tarea.
- **Canvas** — Business Model Canvas por proyecto (`canvas.yml`), grilla editable.
- **Docs** — visor de todos los `.md` del proyecto, como en el repo.
- **Diagramas** — render de Mermaid (`.mmd` y bloques en `.md`) + export a PNG.
- **Seguridad** — vulnerabilidades vía [OSV.dev](https://osv.dev) (GitHub Advisories,
  npm, Packagist, PyPI): por severidad, con versión que corrige, export a Markdown,
  re-escaneo por proyecto y escaneo periódico automático.
- **Radar** — versiones de frameworks entre proyectos, estado de respaldos y mapa de puertos.

## El contrato de un proyecto

Boiler no impone un stack; impone una **interfaz**. Un proyecto gestionable tiene:

```txt
<proyecto>/
├── boiler.yml      # manifiesto: id, empresa, type, dominio/puerto, apps, db, repo, prod
├── run.sh          # up | down | restart | status | logs [svc] | backup
├── backup.sh       # (si tiene DB) respaldo guiado + --auto + --restore
├── tasks.yml       # tareas del proyecto (IDs referenciables en commits)
├── docker-compose.yml   # en la RAÍZ; .docker/ solo Dockerfiles y configs
└── .data/          # datos de la DB, dentro del proyecto (gitignored)
```

Convenciones: puerto de entrada P con bloque `P…P+9`; sin `restart: unless-stopped`
en local; dominio `<proyecto>.<empresa>.localhost`. Detalle en **`MANIFEST.md`**.

## Configuración global (`~/.boiler/`)

- `registry.yml` — workspaces registrados.
- `config.yml` — defaults del wizard (empresa, DB, git, deploy, puertos) y `security.scan_hours`.
- `security.json` — último snapshot de vulnerabilidades. · `hub.log` — log del servicio.

## Documentación

| Archivo | Contenido |
|---|---|
| `MANIFEST.md` | Especificación del manifiesto `boiler.yml` y los tipos de proyecto. |
| `SISTEMA.md` | Diseño del sistema, fases y bitácora de lo construido. |
| `PLAN.md` | Homologación del ecosistema reSTART Labs (origen del proyecto). |
| `HUB.md` | Diseño y fases del hub. |
