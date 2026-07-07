# Boiler — Sistema de gestión de proyectos (diseño)

> Boiler es un sistema **a nivel de sistema operativo**: administra una carpeta raíz
> de proyectos, genera proyectos nuevos dentro de ella con la estructura estándar,
> los gestiona (tareas, usuarios, seguimiento) y maneja el ciclo comercial
> (presupuestos, facturas, pagos, contabilidad). El **hub** es su interfaz de consulta
> y operación local.
>
> Fecha del diseño: 2026-07-04

## 1. Arquitectura general

```txt
Boiler (sistema)
├── Carpeta raíz de proyectos: /Users/ricardogatica/Projects/reSTART_Labs   (configurable)
│   └── cada proyecto se autodeclara con boiler.yml (MANIFEST.md)
├── Generador de proyectos ("boiler new") — crea estructura según type
├── Hub (reSTART_Labs/hub, :8500) — dashboard, kanban, RUN/STOP, capturas
└── Núcleo de gestión — usuarios, tareas, presupuestos, facturas, pagos, contabilidad
```

**Fuentes de verdad, por diseño:**

| Dato | Dónde vive | Por qué |
|---|---|---|
| Identidad del proyecto | `boiler.yml` en su raíz (versionado) | El proyecto se describe a sí mismo; Boiler descubre escaneando |
| Tareas / sub-tareas | `tasks.yml` del proyecto (versionado) | Viajan con el código; IDs en commits |
| Usuarios, asignaciones | SQLite de Boiler (`data/boiler.db`) | Transversal a proyectos |
| Presupuestos, facturas, pagos, contabilidad | SQLite de Boiler | Datos comerciales, no van en repos |
| Capturas, logs, snapshots | `hub/data/` (no versionado) | Efímero/regenerable |

## 2. Descubrimiento por manifiesto

El hub deja de depender de `projects.yml` central: **escanea la carpeta raíz buscando
`boiler.yml`** (profundidad ≤ 3 para paraguas como `reSTART/`, `LearningPath/`,
`Minicatalogo/`). El registro central queda solo como override/exclusiones.
✅ Los 19 proyectos actuales ya tienen su manifiesto sembrado.

## 3. Generador de proyectos (`boiler new`)

```sh
boiler new <nombre> --empresa restart --type landing --stack astro
```

1. Crea la carpeta en la raíz configurada (respetando paraguas por empresa).
2. Scaffolding según `type`:
   - **landing** → elige stack (astro | nextjs | nuxtjs | vite-ssr); sin docker.
   - **app** → framework + `docker-compose.yml` (DB propia en `./.data/`) + nginx si aplica.
   - **multi-app** → estructura `frontend/ backoffice/ api/` (roles a elección) + compose
     orquestador con nginx de entrada + perfiles por app (patrón cube360/LearningPath).
   - **api** / **mobile** / **lib** → variantes mínimas.
3. Genera SIEMPRE: `boiler.yml`, `run.sh` (contrato §5.1), `backup.sh` si hay DB (§5.2),
   `tasks.yml`, `.env.example`, `.gitignore` (.data/.backups), `README.md`, `git init`.
4. Asigna puerto: siguiente bloque libre según los manifiestos existentes.
5. El hub lo muestra de inmediato (descubrimiento automático).

## 4. Módulos de gestión (el "ERP" de proyectos)

| Módulo | Entidades | Notas |
|---|---|---|
| **Proyectos** | proyecto (desde boiler.yml) + metadatos de gestión (cliente, estado comercial, fechas) | seguimiento = tareas + git + deploys (ya en el hub) |
| **Tareas** | tarea, **sub-tarea** (nuevo campo `subtasks:` en tasks.yml), asignado (`assignee`), estimación | kanban ya operativo; se agrega asignación y jerarquía |
| **Usuarios** | usuario, rol (admin/dev/cliente-lector) | SQLite; login simple del hub |
| **Presupuestos** | presupuesto → ítems (horas/monto), estado (borrador/enviado/aprobado) | por proyecto/cliente; exportable a PDF |
| **Facturas** | factura ← presupuesto o manual; estado (emitida/pagada/vencida) | correlativo por empresa; integrable a SII después (existe experiencia libredte en cube360) |
| **Pagos** | pago ← factura (parcial/total), medio | |
| **Contabilidad** | libro simple: ingresos (pagos) / egresos (gastos por proyecto), reportes por período | |
| **Reportes** | avance por proyecto (tareas+commits+deploys), horas/valor por cliente, flujo de caja | el hub ya provee la mitad técnica |

## 5. Fases de construcción

1. **B1 — Manifiestos** ✅ (2026-07-04): spec `MANIFEST.md` + `boiler.yml` sembrado en los 19.
2. **B2 — Descubrimiento** ✅ (2026-07-04): el hub escanea `boiler.yml` (walk con poda, profundidad ≤5 — encuentra anidados como cube360/apps/docs; projects.yml quedó solo de fallback). CLI `hub/boiler`: `list` (tabla con estado en vivo), `hub`, `up|down|status <id>` (delegan al run.sh del proyecto). Alias sugerido: `alias boiler=/Users/ricardogatica/Projects/reSTART_Labs/hub/boiler`.
3. **B3 — Generador** ✅ (2026-07-06): `boiler new <nombre>` — wizard interactivo (o por flags) cuyas **preguntas clave son ¿multi-app? y ¿base de datos?**:
   - *Front simple (sin DB)* → vue-vite | react-vite | astro | nuxt | next; sin docker; run.sh host + instrucción de scaffold.
   - *Con DB (php/node)* → laravel | node-api | nuxt-fullstack; genera `docker-compose.yml` + `.docker/` (Dockerfile PHP con pdo según motor, nginx con la lección `$http_host`, MySQL con tuning u opción Postgres), datos en `./.data/`, `backup.sh` §5.2.
   - *Multi-app* → `frontend/` + `backoffice/` + compose orquestador con nginx de entrada (routing `/` → frontend, `/api|/backoffice` → Laravel); las apps se auto-explican el scaffold al primer `up`.
   - Siempre: `boiler.yml` (con **`repo:` github|bitbucket|gitlab y `prod:` railway|aws|digitalocean|vps**), run.sh, tasks.yml, .env.example, .gitignore, git init, y **puerto asignado del pool GLOBAL** (todos los workspaces, bloques de 10 desde 8600). Defaults en `~/.boiler/config.yml` (`boiler config`).
4. **B4 — Usuarios + asignación**: SQLite, login del hub, `assignee` y `subtasks` en tasks.yml, kanban por usuario.
5. **B5 — Comercial**: presupuestos → facturas → pagos → libro contable + reportes (módulo nuevo del hub, mismas tecnologías FastAPI/Jinja).

## 5b. Consolidación 2026-07-06 — Boiler global y multi-workspace ✅

Definición final de Ricardo: *"Boiler es un CLI que permite la creación en una carpeta de
uno o más proyectos de diferentes lenguajes que se levantan con un wizard; levanta un hub
dentro de esa carpeta para ver los proyectos/repos e iniciarlos; el hub muestra los .md
como en el repo; Boiler se inicia en distintas carpetas con centralización de puertos,
URLs y proyectos."* Implementado:

- **Boiler es ahora el software** (este repo): paquete `boiler/` (CLI + hub generalizado
  por `BOILER_ROOT`), launcher `bin/boiler`, `install.sh` → instalación global
  (`~/.local/bin/boiler` o `/usr/local/bin`).
- **Multi-workspace**: `boiler init` en CUALQUIER carpeta (vacía o con proyectos) la
  registra en `~/.boiler/registry.yml` con su puerto de hub (8500, 8501, …). Comandos:
  `init · hub · list · up/down/status <id> · workspaces · ports` (vista global de
  puertos entre workspaces, con detección de duplicados).
- **Visor de Markdown en el hub**: `/project/{id}/docs` — árbol de todos los `.md` del
  proyecto (podado, README primero) renderizados como en el repo (fenced code, tablas).
- **Datos por workspace** en `<workspace>/.boiler/` (shots, logs).
- `reSTART_Labs/hub` quedó como wrapper legacy (`./run.sh` = `boiler hub`); una sola
  fuente de código.

## 5c. Hub global + adopción por schemas ✅ (2026-07-06)

- **El hub es ahora UN servicio global** (`:8500`) que agrega los proyectos de TODOS los
  workspaces del registro (`BOILER_GLOBAL`), con columna/filtro de workspace en el tablero.
  Los puertos por-workspace del registro quedaron obsoletos.
- **Servicio de macOS**: `boiler service install` crea el LaunchAgent `cl.boiler.hub`
  (RunAtLoad + KeepAlive) — el hub arranca solo al iniciar sesión. Log en `~/.boiler/hub.log`.
- **`boiler/schemas.py`**: la forma canónica de cada tipo — detección de stack
  (laravel, nestjs, nuxt±fullstack, next, astro, express±ssr, expo, vue/react-vite,
  fastapi, django, cakephp, php legacy), detección de DB/compose/puerto de entrada, y
  **composición multi-app** (convenciones de comunicación: nginx único de entrada,
  DNS interno de compose, UNA DB compartida con database por app).
- **`boiler add [ruta]`**: adopta un proyecto EXISTENTE — lo analiza contra los schemas,
  genera su `boiler.yml` (+tasks.yml), asigna puerto del pool global si no detecta uno
  en su compose, y entrega el **informe de la mejor estructura** (✓/→/⚠ por cada regla
  del contrato). Estreno real: **Zhen-CRM** adoptado (CakePHP legacy detectado, MySQL
  inferido, puerto 8600) — el hub pasó a 20 proyectos.

## 5d. Business Model Canvas ✅ (2026-07-06)

`canvas.yml` versionado en cada proyecto (9 bloques canónicos como listas) + vista
`/project/{id}/canvas` en el hub: **la grilla clásica del BMC** (Socios | Actividades/Recursos |
Propuesta de valor destacada al centro | Relación/Canales | Segmentos, y abajo
Costos | Ingresos), con agregar/quitar ítems inline que escriben directo al archivo del repo.
Botón "🗺 Canvas" en la vista de proyecto. El archivo se crea recién al primer ítem
(no se siembran 20 canvas vacíos). Estreno: podium con propuesta de valor y segmento reales.

## 5g. Radar macro ✅ (2026-07-07)

`/radar` (botón en el dashboard) con las tres herramientas técnicas de la lista aprobada:
1. **Versiones de frameworks**: matriz framework × proyecto leyendo package.json/composer.json
   (proyecto + apps internas). Referencia auto-contenida: "la versión más nueva que ya usas
   en casa" — marca en naranjo los proyectos con major inferior. Primer barrido: vite el más
   fragmentado (11 atrasados vs 8.x), nuxt 5 atrasados vs 4.4, laravel 2 bajo 12.
2. **Estado de respaldos**: último `.backups/` por proyecto con DB — verde <7 días, ámbar >7,
   rojo nunca. Hallazgo real: vacunapp y zhen-crm sin respaldo (vacunapp DB vacía; zhen-crm
   recién adoptado sin backup.sh).
3. **Mapa de puertos**: bloques de 10 ordenados con detección visual de solapes (hoy: cero).

También en 2026-07-07: bug de "Corrige en" arreglado (advisories multi-rama → upgrade mínimo
según versión instalada), /security ordenada por criticidad con filtros y colapsar todo,
export MD por proyecto (copiar/descargar) + informe completo, y alta de tareas desde el kanban.

## 5e. Seguridad de dependencias (plan 2026-07-07)

**Objetivo**: el hub revisa periódicamente las vulnerabilidades de las librerías de todos
los proyectos y las muestra por severidad.

**Fuente de datos — decisión**: **OSV.dev** (api.osv.dev, de Google/OpenSSF) como fuente
única de la fase 1:
- **Agrega GitHub Advisories** (GHSA) — exactamente la fuente que se quería — más los
  advisories nativos de npm, Packagist (composer) y PyPI.
- API gratuita, sin API key, con endpoint **batch** (hasta 1000 paquetes por llamada).
- Cada vulnerabilidad trae sus alias **CVE**, así que NVD queda cubierto como referencia
  cruzada (link al CVE) sin integrar su API (NVD trabaja con CPEs de productos, no con
  paquetes npm/composer — es la herramienta equivocada para librerías de aplicación).
- El **Debian tracker** aplica a paquetes del sistema operativo (imágenes base de Docker),
  no a librerías de app → queda para la fase 2 con `trivy` (escaneo de imágenes).

**Arquitectura (fase 1)**:

1. **Colector `security.py`**:
   - Inventario: parsea lockfiles de cada proyecto (y de cada app en los multi-app):
     `composer.lock` (Packagist), `package-lock.json` (npm), `yarn.lock` v1/berry (npm),
     `requirements.txt` (PyPI). Lockfiles = versiones exactas instaladas.
   - Dedupe global (la misma librería en 10 proyectos se consulta UNA vez) → consulta
     `POST /v1/querybatch` de OSV → mapea vulnerabilidades de vuelta a cada proyecto.
   - Severidad: CVSS/severity del advisory → critical | high | moderate | low
     (colores de estado ya reservados en el design system).
   - Snapshot con timestamp en `~/.boiler/security.json` (no en los repos).
2. **Periodicidad**: el hub YA es un servicio siempre vivo (LaunchAgent) → un hilo
   scheduler escanea cada 24 h (configurable: `security.scan_hours` en `~/.boiler/config.yml`),
   más botón **"Escanear ahora"** en la UI y comando **`boiler audit`** en la CLI.
3. **UI `/security`**: resumen por proyecto (conteo por severidad con punto+texto),
   detalle por proyecto: `paquete@versión` → advisory (link a GHSA/OSV/CVE), rango
   afectado y **versión que corrige**. En el dashboard: gauge "vulns críticas" en el
   masthead con link a la sección.

**Fase 2 (después)**: `trivy` para imágenes Docker (cubre la capa Debian/Alpine del
tracker), y sugerencia de comandos de arreglo (`composer update x`, `npm audit fix`).

> ✅ Fase 1 construida 2026-07-07. Primer escaneo real: **6.457 dependencias únicas** en
> los 20 proyectos → 17 críticas, 540 altas, 663 moderadas. Los homologados recientes
> (podium, screening, enregla) casi limpios; los peores: cube360 (4 crit), docs360 (3 crit).
> `/security` con detalle por proyecto (advisory GHSA/CVE + versión que corrige), gauge
> "vulns crít+altas" en el masthead, `boiler audit` en CLI, scheduler cada 24 h en el servicio.
> Lección Jinja: nunca llamar `items` a una clave de dict usada en template (colisiona con .items()).

## 5f. Diagramas mermaid ✅ (2026-07-07)

`/project/{id}/diagrams`: encuentra los **.mmd** del proyecto y los **bloques ```mermaid
embebidos en .md** de `.docs/`, los renderiza en el navegador (mermaid.js v11 embebido en
static/vendor — sin CDN en runtime, tema claro/oscuro), y **exporta a PNG** con el mismo
Chrome headless de las capturas (escala 2x): botón por diagrama + "Exportar todos".
Convención de destino: `…/mermaid/x.mmd → …/png/x.png` (podium), o junto al fuente.
Botón "◇ Diagramas" en la vista de proyecto. Verificado con los 14 diagramas de podium.

## 6. Decisiones pendientes

1. ¿La CLI `boiler` en Python (comparte código con el hub) o bash? → propongo Python, mismo venv del hub.
2. Carpeta raíz única (`reSTART_Labs/`) ¿o multi-raíz (sumar `RicardoGatica/` cuando se homologuen)?
3. Facturación Chile: ¿integración SII vía libredte (ya hay experiencia en cube360) o solo documentos internos al inicio?
4. Multi-usuario real (varias personas usando el hub) ¿o single-user con registro de asignados?
