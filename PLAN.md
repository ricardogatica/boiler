# Plan de homologación — /Users/ricardogatica/Projects/

> Objetivo de esta etapa: **ordenar los proyectos y que cada uno tenga su `run.sh`**
> homologado para levantarse fácil, respondiendo en `http://<proyecto>.<empresa>.localhost:<puerto>`.
> El script Boiler NO se construye por ahora (queda para una etapa posterior).
>
> Fecha: 2026-07-04 · Basado en el diagnóstico de `README.md`

## Alcance

**Incluidos** (por empresa → dominio local):

| Empresa | Dominio | Proyectos |
|---|---|---|
| reSTART Labs | `<p>.restart.localhost` | podium, inertia, enregla, screening, bogy, IndicadoresDelDia, sau, auditapp, business360, LearningPath, taller, vacunapp, liveness, docs360, galaxa, front.cl, restart.cl (+ por inventariar: Zhen-CRM, sales360.cl, lambdas, carpeta `enregla` duplicada) |
| Aplicate / PetSit | `petsit.localhost` | petsit.cl, petsit.app, prospect |
| Ricardo Gatica | `<p>.ricardogatica.localhost` / `ricardogatica.localhost` | Bahia, arcade, atlas, books, cuantofaltapp, dividapp, morse, nolearriendes, ricardogatica.com |

**EXCLUIDOS — no tocar en esta actualización**: `reSTART_WORKS/`, `MineClass/`, `MinePass/`, `eClass/`, y **todo el ecosistema Minicatalogo** (Minicatalogo, MinicatalogoPOS, MinicatalogoThemes, MinicatalogoTools, MinicatalogoMCP, MinicatalogoChromeExt) — decisión 2026-07-04.

`extracurriculapp.restart.cl` (carpeta vacía en RicardoGatica/) fue **eliminada** el 2026-07-04.

Proyectos sin código quedan solo registrados (cunde, sgd44, minenode).

---

## Fase 0 — Preparación (mínima, sin construir Boiler)

> Decisión 2026-07-04: **el script Boiler no se hace por ahora**. Esta etapa es solo ordenar
> proyectos y homologar sus `run.sh`. Tampoco hay proxy central: cada proyecto se accede por
> su dominio + puerto propio (`podium.restart.localhost:8386`).

1. **Tabla de puertos y dominios** (sección "Registro" al final de este PLAN.md): conservar los puertos que hoy funcionan; reasignar solo colisiones (ej. podium publica `5432:5432` pelado → mover a puerto propio).
2. **Plantilla de referencia de `run.sh`** (contrato §5.1 del README) validada en el piloto y replicada en cada proyecto.

## Fase 1 — Respaldo + oxígeno para Docker (antes de tocar cualquier compose con DB)

1. En cada proyecto cuyo compose se vaya a modificar, `backup.sh` + primer respaldo verificado ANTES del cambio. Regla de oro: ningún compose con DB se modifica sin respaldo previo.
2. Subir RAM de Docker Desktop a 16 GB (manual, Settings → Resources; el Mac tiene 48 GB).
3. Limpieza segura de disco: `docker image prune -a` + `docker builder prune` (~85 GB recuperables). **Nunca** `volume prune` / `--volumes` / `down -v`.

## Fase 2 — Piloto: podium

Ya cumple casi todo el contrato. Ajustes: agregar `backup.sh`, corregir `5432:5432`, validar `./run.sh up` end-to-end. El piloto valida la plantilla antes de replicarla.

## Fase 3 — reSTART_Labs por olas

Cada proyecto recibe el mismo paquete: `run.sh` contrato + `backup.sh` + dominio `<p>.restart.localhost` en nginx + tuning MySQL/mem_limit + fila en el Registro (al final de este documento).

- **Ola A — ya casi cumplen** (tienen run.sh y docker; se normaliza al contrato): inertia, enregla, screening, bogy, IndicadoresDelDia, sau, auditapp, business360.
- **Ola B — tienen docker, falta run.sh**: LearningPath (migrar dominios `*.local` → `*.restart.localhost`), taller, vacunapp, liveness.
- **Ola C — sin docker**: docs360, galaxa, front.cl, restart.cl. Su `run.sh up` envuelve `yarn dev`/`dev:server` y sirve en su puerto asignado (`localhost:<puerto>`; sin proxy el subdominio requiere un vhost que estos proyectos no tienen — su URL queda documentada en el Registro).
- **Ola D — inventariar y decidir**: Zhen-CRM, sales360.cl, lambdas, `enregla` (¿duplicado de enregla.restart.cl? verificar y archivar), Aplicate/prospect.
- **PetSit**: dominio `petsit.localhost`. petsit.cl (run.sh ya existe, sin Docker por Herd — se respeta su flujo, solo se normaliza la interfaz), petsit.app (móvil: `up` = Expo, sin dominio).

## Fase 4 — Proyectos personales (RicardoGatica/)

Inventario rápido (no están relevados) + mismo paquete. Dominios: `ricardogatica.localhost` para el sitio principal y `<p>.ricardogatica.localhost` para el resto.

## Fase 4.6 — Mover ecosistema Minicatalogo a reSTART_Labs/ (plan 2026-07-04)

**Objetivo**: agrupar tal cual (sin renombrar) todo `Projects/Minicatalogo*` bajo `Projects/reSTART_Labs/Minicatalogo/`:

```txt
reSTART_Labs/Minicatalogo/
├── Minicatalogo/            ← monorepo (con .data/mysql: DBs minicatalogo + thepets de petsit)
├── MinicatalogoChromeExt/
├── MinicatalogoMCP/
├── MinicatalogoPOS/
├── MinicatalogoThemes/
├── MinicatalogoTools/
└── Minicatalogo Corporate.pdf   (matchea el patrón — confirmar si va)
```

**Impacto relevado** (todo verificado antes de escribir este plan):

1. **Datos MySQL a salvo**: bind mount relativo `./.data/mysql` — viajan con la carpeta.
2. **Project name de compose NO cambia**: deriva del nombre final de carpeta (`Minicatalogo`), que se conserva. Igual se fija `name: minicatalogo` (1 línea) como seguro.
3. **Contenedores `mc-*` existentes guardan rutas absolutas viejas** → se recrean con `docker compose down` + `up` desde la nueva ruta (compose los encuentra por label de proyecto, no por ruta). Docker está apagado ahora = momento ideal.
4. **petsit.cl**: actualizar `MINICATALOGO_DIR` en `run.sh` y `backup.sh` (2 líneas — única referencia externa con ruta absoluta).
5. **`Minicatalogo.code-workspace`** referencia `../MinicatalogoMCP` — sigue válida porque los hermanos se mueven juntos.
6. **`~/.claude.json`**: solo historial de sesiones por ruta; queda obsoleto sin romper nada.
7. **Red `mc_shared`**: vive en Docker, independiente de rutas.

**Pasos**: (1) fijar `name: minicatalogo` en el compose del monorepo → (2) `mkdir` + `mv` de las 6 carpetas → (3) actualizar rutas en petsit → (4) al encender Docker: `down` de restos viejos, `up -d mysql`, verificar `thepets` (50 tablas) y `petsit.localhost:8010` HTTP 200 → (5) actualizar registro.

> ✅ Ejecutada 2026-07-04 (incluido el PDF): las 6 carpetas + PDF viven en `reSTART_Labs/Minicatalogo/`. Verificado: mc-mysql monta desde la ruta nueva, `thepets` 50 tablas + `minicatalogo` 29 tablas intactas, petsit HTTP 200. Contenedores con rutas viejas eliminados y recreados.

## Fase 5 — Limpieza del nivel Projects/ (opcional, al final)

~10 PDFs/DOCX/PNG sueltos en `/Projects/` → mover a una carpeta `_docs/` (o al vault Obsidian que ya existe ahí). `DiegoGatica/`, `FranciscaGatica/`, `ChromeExt/` están vacías o casi → confirmar y decidir.

---

## Reglas de seguridad (aplican a todas las fases)

1. Respaldo verificado **antes** de modificar cualquier compose con DB.
2. Jamás `down -v`, `docker volume prune`, `system prune --volumes`.
3. Un proyecto se migra completo y se prueba (`./run.sh up` → URL responde → `./run.sh down`) antes de pasar al siguiente.
4. Los run.sh existentes no se borran: se reemplazan manteniendo compatibilidad de lo que ya se usa (ej. `./run.sh` sin args en screening seguirá levantando).
5. Proyectos excluidos (reSTART_WORKS, MineClass, MinePass, eClass, ecosistema Minicatalogo) no se tocan ni se registran.

## Fase 3.5 — Compose en la raíz del repo (decisión 2026-07-04)

**Estándar**: `docker-compose.yml` (y sus overlays) viven en la **raíz** del repositorio; `.docker/` contiene SOLO configuraciones complementarias y Dockerfiles (nginx/, mysql/my.cnf, php/Dockerfile, initdb/, etc.).

Afectados (los otros 11 homologados ya cumplen):

1. **podium**: mover `.docker/docker-compose.yml` → `./docker-compose.yml`. Las rutas internas (`./.docker/nginx/…`, `./.data/postgres`) ya son relativas a la raíz (el run.sh usaba `--project-directory .`), así que el archivo se mueve sin editar. Simplificar `run.sh` y `backup.sh`: `docker compose -f .docker/docker-compose.yml --project-directory .` → `docker compose` a secas. El project name no cambia (deriva de la carpeta). Verificar: config, up, 43 tablas, HTTP 200.
2. **enregla**: mover el compose a la raíz + cambiar dentro del archivo `../.data/postgres` → `./.data/postgres` (era relativo a `.docker/`). Simplificar `run.sh`/`backup.sh` (quitar `-f .docker/docker-compose.yml`). `name: enregla` ya está fijado → volúmenes y contenedores intactos. Verificar: config, up, 6 tablas.

Riesgo bajo: mover el compose no toca datos (ya persisten en `./.data/`), y ambos proyectos tienen respaldo verificado en `.backups/`.

> ✅ Ejecutada 2026-07-04: podium movido sin recrear contenedores (config resuelta idéntica; HTTP 200 verificado) y enregla movido con el ajuste `../.data/postgres` → `./.data/postgres` (6 tablas verificadas). Referencias en CLAUDE.md/.docs actualizadas en ambos. **Los 13 proyectos homologados cumplen ahora: compose en raíz, `.docker/` solo configs/Dockerfiles.**

## Decisiones tomadas (2026-07-04)

0. **Compose en la RAÍZ del repo**; `.docker/` solo para Dockerfiles y configs complementarias (ver Fase 3.5). Aplica también a todos los proyectos futuros (olas C/D, personales).
1. **El script Boiler no se construye por ahora** — esta etapa es solo ordenar proyectos + `run.sh` homologado por proyecto.
2. **Sin proxy central** — cada proyecto se accede por dominio + puerto propio.
3. **PetSit** → `petsit.localhost` (marca propia, sin nivel empresa).
4. **Minicatalogo y todo su ecosistema quedan FUERA de esta actualización.**
5. **Backups** → solo `.backups/` local dentro de cada proyecto (gitignored).
6. `extracurriculapp.restart.cl` (vacía) → eliminada.

## Decisiones pendientes

1. Puerto/bloque definitivo para bogy, liveness (colisión 8011) y ola C — se asignan al ejecutar cada ola.

> Resuelto 2026-07-04: la carpeta `enregla` duplicada solo contenía un `.DS_Store` → eliminada.

## Esquema de puertos (regla acordada 2026-07-04)

1. **Cada proyecto tiene un puerto de entrada P** (el de su dominio, ej. podium = 8386), **único** en toda la máquina.
2. **Todo otro puerto que el proyecto publique en el host debe ser MAYOR que P y consecutivo**: P+1, P+2, … El proyecto reserva el bloque `P … P+9`.
3. **Prohibido publicar puertos default de servicios** en el host (`5432`, `3306`, `6379`, `3000`, `8080`): son los que chocan entre proyectos y con instalaciones locales. Solo cambia el lado izquierdo del mapeo (`host:contenedor`) — dentro del contenedor el servicio sigue en su puerto normal.

> Nota: inertia (3232→3234) y enregla (3235→3236) ya siguen este patrón de forma natural; la regla lo generaliza.

> **Estructura de carpetas (2026-07-04)**: los 15 proyectos `*.restart.cl` viven en `reSTART_Labs/reSTART/`; el ecosistema Minicatalogo en `reSTART_Labs/Minicatalogo/`; petsit en `reSTART_Labs/Aplicate/`. En la raíz de reSTART_Labs quedan además LearningPath, front.cl, restart.cl, lambdas (librería AWS), y los excluidos/no-código (Zhen-CRM, cunde.cl, sales360.cl, minenode.cl, sgd44 dentro de reSTART/).

## Registro de proyectos (dominios y bloques de puertos)

Se conservan los puertos de entrada que hoy funcionan; los puertos internos se renumeran al bloque del proyecto durante su ola.

| Proyecto | Dominio local | Bloque | Detalle / cambios |
|---|---|---|---|
| taller | taller.restart.localhost | 8383-8385 | ✅ 2026-07-04: mysql 33083→8384, tuning, datos → ./.data/mysql (19 tablas restauradas), run.sh nuevo, backup.sh, respaldo verificado |
| podium | podium.restart.localhost | 8386-8395 | ✅ 2026-07-04: postgres 5432→8390, redis 6380→8391, backup.sh + status/backup en run.sh, respaldo verificado |
| inertia | inertia.restart.localhost | 3232-3234 | ✅ 2026-07-04: run.sh a subcomandos (compat `./run.sh`=up), backup.sh, respaldo verificado |
| enregla | enregla.restart.localhost | 3235-3237 | ✅ 2026-07-04: run.sh a subcomandos, backup.sh (DB + uploads), respaldo verificado |
| screening | screening.restart.localhost | 3335-3344 | ✅ 2026-07-04: mysql 33306→3337, minio 9000/9001→3338/3339, perf_schema OFF, dominio en nginx, run.sh subcomandos (compat flags), backup.sh, respaldo verificado |
| bogy | bogy.restart.localhost | 8480-8489 | ✅ 2026-07-04: nginx 3000→8480, postgres 54328→8481, minio console 9011→8482, dominio en nginx y URLs .env, run.sh subcomandos, backup.sh, respaldo verificado |
| **api.restart.cl** (ex IndicadoresDelDia, carpeta renombrada 2026-07-04) | api.restart.localhost | 51745-51749 | ✅ mysql 33075→51746, tuning, dominio, run.sh, backup.sh, respaldo verificado. Project name fijado (`name: marketdata`); datos ya persistían en `./.data/mysql` y viajaron con el rename; contenedores huérfanos del nombre viejo eliminados |
| sau | sau.restart.localhost | 54354-54363 | ✅ 2026-07-04: dominios sau/app.sau.restart.localhost, nuxt 3000→54355, vite 5173→54356, tuning MySQL, run.sh subcomandos (compat flags), backup.sh, respaldo verificado |
| auditapp | auditapp.restart.localhost | 30005-30014 | ✅ 2026-07-04: web 30015→30005 (entrada), api 30005→30006, postgres 54325→30007, redis 63795→30008, run.sh subcomandos, backup.sh, respaldo verificado. Sin nginx: el dominio resuelve directo al puerto |
| **cube360** (ex business360) | cube360.localhost (multi-tenant) | 36036-36067 | ✅ 2026-07-04: tuning MySQL, run.sh subcomandos, backup.sh multi-tenant (--all-databases, 872K verificado), **vites 5151-5154 → 36037-36040** (run.sh + 4 vite.config.ts + 4 .env). Datos ya persistían en `./.data/mysql` |

### Persistencia de datos en carpeta (regla 2026-07-04)

Toda base de datos persiste en `./.data/<motor>/` DENTRO del proyecto (gitignored), no en volúmenes con nombre de Docker. Migrado y verificado: podium (43 tablas), enregla (6), inertia (5), bogy (32), auditapp (15) por copia de volumen; screening (31) y sau (29) por dump+reinicialización — **lección macOS**: un datadir MySQL creado en volumen Linux no arranca en bind mount APFS (case-insensitive, `lower_case_table_names` incompatible); hay que inicializar fresco en la carpeta e importar el dump. Postgres no tiene ese problema. Los volúmenes originales se conservan como red de seguridad adicional a `.backups/`. |
| **learningpath.cl** (ex LearningPath, reestructurado 2026-07-04) | learningpath.restart.localhost (+ lms.learningpath) | 8787-8796 | ✅ mysql 8788, tuning, datos ./.data/mysql (57 tablas lms verificadas post-reestructura), run.sh, backup.sh --all-databases. **Estructura interna: `frontend/` (ex learningpath.cl, Nuxt) + `backoffice/` (ex admin.learningpath.cl) + `lms/` (ex lms.learningpath.cl)**; compose con `name: learningpath` fijado; es el proyecto de campus de estudios |
| **learni.cl** (extraído de LearningPath 2026-07-04) | learni.restart.localhost | 8470+ | ✅ Unidad de diseño instruccional — sitio informativo Nuxt independiente, con repo git propio (anidado que ya existía). run.sh estilo Ola C (yarn dev :8470), sin Docker ni DB. Registrado en el hub con prefijo de tareas LRN |
| vacunapp | vacunapp.restart.localhost | 8089-8092 | ✅ 2026-07-04: mysql 33062→8090, redis 63792→8091, vite 51732→8092, dominio en nginx y APP_URL, perf_schema OFF, persistencia ./.data/mysql (DB estaba vacía, sin datos que migrar), run.sh nuevo, backup.sh |
| liveness | liveness.restart.localhost | 8020-8029 | ✅ 2026-07-04: **8011→8020** (resuelta colisión con petsit.app), docs actualizadas, run.sh nuevo (sin DB — backup no aplica) |
> Movida 2026-07-04: carpeta `business360.restart.cl` → **`cube360.restart.cl`** (name: cube360 ya estaba fijado; datos y compose intactos). **docs360** vive ahora en `cube360.restart.cl/apps/docs` — app del ecosistema Cube360 que también corre por sí sola (conserva su run.sh :8450, su repo git propio anidado y su entrada en el hub). Integración al compose/nginx de cube360: pendiente de definir (¿docs.cube360.localhost?).

| restart.cl | restart.localhost | 8430+ | ✅ 2026-07-04: run.sh nuevo (envuelve `yarn dev:server` SSR+api con PORT=8430), sin DB |
| front.cl | front.restart.localhost | 8440+ | ✅ 2026-07-04: run.sh nuevo (`yarn dev:server` con PORT=8440), sin DB |
| docs360 | docs360.restart.localhost | 8450+ | ✅ 2026-07-04: **puerto dev 8386→8450** (chocaba con podium), run.sh nuevo (+prisma generate). DB MySQL externa — backup donde viva |
| galaxa | galaxa.restart.localhost | 8460+ | ✅ 2026-07-04: run.sh nuevo (`yarn dev --port 8460`). DB MySQL externa — backup donde viva |
| petsit.cl | petsit.localhost | 8010-8019 (compartido con petsit.app) | ✅ 2026-07-04: **dockerizado, adiós Herd** — nginx 8010, redis 8014, vite 51733→8015, reverb 8016; app/queue/scheduler/reverb en PHP 8.3. **DB compartida**: usa `thepets` en mc-mysql (Minicatalogo) vía red externa `mc_shared` (DNS interno, sin puertos de host); run.sh levanta mc-mysql si está apagado; backup.sh respalda `thepets` (120K verificado, 50 tablas). `.env` Herd respaldado en `.env.herd.backup`; `run-tunnel.sh` quedó con el flujo antiguo |
| petsit.app | — (móvil) | 8011-8012, Metro 8081 | run.sh ya existe |

> **Red compartida `mc_shared`** (2026-07-04): `docker network create mc_shared`. Minicatalogo expone SOLO su servicio mysql en esa red (cambio mínimo autorizado en su compose); cualquier proyecto que necesite esa DB se une a la red y llega por `mc-mysql:3306` sin consumir puertos del host.

> **Exclusiones adicionales** (2026-07-04): `Aplicate/prospect` (extractor de contactos, no es proyecto) y `sales360.cl` (facturación Chile) quedan fuera. `lambdas/` se registra como **librería compartida** de funciones AWS genéricas — sin run.sh ni docker; se consume desde otros proyectos.
| personales (RicardoGatica/) | `<p>.ricardogatica.localhost` | por asignar | fase 4 (inventario pendiente) |
