# Manifiesto Boiler (`boiler.yml`) — especificación v1

Todo proyecto gestionado por Boiler lleva un **`boiler.yml` en su raíz**: el manifiesto
que lo describe de forma máquina-legible. Es la evolución del registro central
(`hub/projects.yml`): en vez de una lista en el hub, **cada proyecto se declara a sí
mismo** y Boiler/el hub los descubren escaneando la carpeta raíz de proyectos.

## Esquema

```yaml
boiler: 1                      # versión del esquema del manifiesto
id: learningpath               # identificador único (kebab/flat, sin espacios)
name: LearningPath             # nombre para humanos
empresa: restart               # marca/organización (define el dominio local)
type: multi-app                # ver "Tipos" abajo
description: Campus de estudios online

local:
  domain: learningpath.restart.localhost
  port: 8787                   # puerto de ENTRADA; el proyecto reserva port..port+9
  run: ./run.sh                # contrato: up|down|restart|status|logs [svc]|backup
  compose: docker-compose.yml  # null → corre en host (sin docker)
  compose_project: learningpath  # label de docker compose (null si no aplica)

# Solo para type: multi-app — las aplicaciones internas del repo
apps:
  - { name: frontend,   path: frontend,   role: frontend,   stack: nuxt }
  - { name: backoffice, path: backoffice, role: backoffice, stack: laravel }
  - { name: lms,        path: lms,        role: lms,        stack: laravel }

stack: [laravel, nuxt, mysql, redis]   # resumen tecnológico

db:
  engine: mysql                # mysql | postgres | shared | external | none
  data: ./.data/mysql          # persistencia SIEMPRE dentro del proyecto
  shared_with: null            # ej: minicatalogo (petsit usa mc-mysql vía red mc_shared)

backup: ./backup.sh            # contrato: guiado | --auto | --list | --restore
tasks: tasks.yml               # tareas del proyecto (kanban del hub / Boiler)
task_prefix: LEA               # prefijo de IDs (default: 3 primeras letras del id)

repo:
  provider: github             # github | bitbucket | gitlab | none
  url: null                    # remoto (se completa al crear el repo)

prod:
  provider: railway            # railway | aws | digitalocean | vps | none | pending
  url: null                    # URL pública (health check de la F3 del hub)
```

## Tipos (`type`) y qué exige cada uno

| type | Qué es | Docker | Ejemplos reales |
|---|---|---|---|
| `landing` | Sitio informativo/marketing de una sola app. Stack libre: **Astro, Next.js, Nuxt, Vite+SSR**, etc. | Opcional (normalmente no) | front.cl, restart.cl, learni |
| `app` | Aplicación única full-stack (un framework, una DB) | `docker-compose.yml` en raíz si tiene servicios (DB/redis) | enregla, vacunapp, docs360, galaxa, petsit |
| `multi-app` | Repo con varias aplicaciones que se instalan juntas — **obligatorio `docker-compose.yml`** que las orquesta; cada app puede tener gestión propia (perfiles, run standalone) | Sí, con nginx como entrada única | Minicatalogo, LearningPath, cube360, podium, taller |
| `api` | Servicio de API puro, sin frontend | Según necesidad | liveness, api.restart.cl |
| `mobile` | App móvil (Expo/React Native) | No | petsit.app |
| `lib` | Librería compartida, no se "levanta" | No | lambdas |

## Reglas que el manifiesto hace verificables

1. **Docker por repo**: cada repo define su propio docker (uno simple para `app`,
   compose multi-servicio para `multi-app`). Compose SIEMPRE en la raíz; `.docker/`
   solo Dockerfiles y configs.
2. **Puertos por bloque**: `local.port` es la entrada; todo otro puerto publicado es
   mayor y consecutivo. Sin `restart: unless-stopped` en local.
3. **Datos en el proyecto**: `db.data` apunta dentro del repo (`./.data/<motor>`),
   o declara `shared`/`external` explícitamente.
4. **Contratos**: `run.sh` y `backup.sh` según Boiler §5.1/§5.2 (README).
5. **Tareas versionadas**: `tasks.yml` con IDs `<PREFIX>-N` referenciables en commits.

## Ejemplos por tipo

**Landing (Astro/Nuxt/Next, sin docker):**
```yaml
boiler: 1
id: learni
name: Learni
empresa: restart
type: landing
local: { domain: learni.restart.localhost, port: 8470, run: ./run.sh, compose: null, compose_project: null }
stack: [nuxt]
db: { engine: none }
prod: { provider: pending, url: null }
```

**App con DB compartida (petsit → MySQL de Minicatalogo):**
```yaml
boiler: 1
id: petsit
name: PetSit
empresa: petsit
type: app
local: { domain: petsit.localhost, port: 8010, run: ./run.sh, compose: docker-compose.yml, compose_project: petsit }
stack: [laravel, inertia, vue, reverb]
db: { engine: shared, shared_with: minicatalogo, data: null }   # thepets en mc-mysql (red mc_shared)
prod: { provider: pending, url: null }
```

**Multi-app (cada app con gestión propia):**
```yaml
boiler: 1
id: cube360
name: Cube360
empresa: cube360
type: multi-app
local: { domain: cube360.localhost, port: 36036, run: ./run.sh, compose: docker-compose.yaml, compose_project: cube360 }
apps:
  - { name: frontend,  path: apps/frontend,  role: frontend,   stack: nuxt }
  - { name: dashboard, path: apps/dashboard, role: backoffice, stack: laravel }
  - { name: crm,       path: apps/crm,       role: backoffice, stack: laravel, profile: crm }
  - { name: finance,   path: apps/finance,   role: backoffice, stack: laravel, profile: finance }
  - { name: desk,      path: apps/desk,      role: backoffice, stack: laravel, profile: desk }
  - { name: docs,      path: apps/docs,      role: docs,       stack: nuxt,    profile: docs, standalone: true }
  - { name: api,       path: api,            role: api,        stack: nestjs }
db: { engine: mysql, data: ./.data/mysql }
prod: { provider: railway, url: null }
```
