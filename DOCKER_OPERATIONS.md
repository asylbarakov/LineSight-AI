# LineSight AI — portable Docker operations

Run commands from the repository root with Docker Compose v2 and Python 3.10+.
No project name, image tag, container name, IP or workstation path is fixed by the
base Compose file. Services use the private DNS names `postgres` and `api`.
PostgreSQL has no host port; API/web bind only to loopback.

## Fresh developer installation

Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell).
Edit these values before starting:

- `POSTGRES_USER`, `POSTGRES_DB`, and a private `POSTGRES_PASSWORD`.
- Your own `ADMIN_PASSWORD` and a long random, persistent `SECRET_KEY`.
  For example, generate a key privately with
  `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Optionally `COMPOSE_PROJECT_NAME=linesight-alice`, `WEB_PORT=3004`,
  `API_PORT=8000`. Use unused ports for another independent installation.

Single-quote passwords containing `$` or `#` in `.env`; do not URL-encode them.
API and Worker construct the same escaped SQLAlchemy URL from `POSTGRES_*`.
Compose deliberately clears any stale `DATABASE_URL` from older `.env` files.
Explicit `DATABASE_URL` still works outside Compose for external DB/SQLite setups.
Do not put passwords into command arguments, shared logs or Git.

```sh
python scripts/preflight.py
docker compose build api worker web
docker compose up -d --no-build postgres
python scripts/preflight.py --check-db
docker compose up -d --no-build api worker web
docker compose ps
```

Stop if either preflight fails. It never changes records or passwords. The second
check actually authenticates over service DNS `postgres`, using a read-only SQL
transaction. `pg_isready` alone does not verify a password. Localhost SQL can also
pass through the official image's `trust` rule; it is not an adequate auth test.
Preflight suppresses raw errors/config output and rejects example credentials,
API/Worker configuration drift, and conflicting legacy URL overrides.

Default addresses: http://localhost:3004 and http://localhost:8000/docs.
`WEB_PORT`/`API_PORT` affect host bindings only. Frontend requests continue through
`API_INTERNAL_URL=http://api:8000` regardless of host ports or project name.
Shell environment variables take precedence over `.env`: remove obsolete exports
if your intended values do not take effect. Never share `compose config` output:
it contains resolved secrets. Use `config --quiet` for syntax checks.

Keep `DETECTOR=none`, `INSTALL_YOLO=0` for the lightweight pipeline. It can produce
visibility findings, not invented equipment defects. YOLO requires authorized
weights at `data/weights/best.pt`, `DETECTOR=yolo`, `INSTALL_YOLO=1` and a worker
build. The YOLO image also installs and validates ByteTrack's `lap` dependency at
build time; it must not be installed by the first inspection job.
GPU deployment requires its own runtime review. No model is downloaded by
preflight. Optional report/demo paths refer to paths INSIDE the container.

## Stable identity and existing installations

Without `COMPOSE_PROJECT_NAME` or `--project-name`, Compose derives the name from
the directory. Choose ONE stable name and reuse it. API/worker/web image tags,
network, `pgdata` and `media_data` names are scoped to that project automatically.
Changing project name selects different volumes; it does not migrate old data.
Never attach two PostgreSQL instances to one active data directory.

The local maintained installation may have an ignored `docker-compose.override.yml`
that pins restored external volumes and existing runtime images. Preserve it and
its `.env`; do not apply fresh-install steps over it. A legacy override with a
literal `DATABASE_URL` must match `POSTGRES_*`; preflight detects conflicts. When
upgrading from old images, rebuild BOTH API and Worker before relying on the new
component-based connection builder. Configuration checks do not deploy anything;
recreation must be an explicit operation against the intended existing project.

For base-file-only validation, use `--file docker-compose.yml`. This excludes
local overrides. For custom env/project/files, pass identical flags to EVERY
Compose invocation and to preflight, for example:

```sh
python scripts/preflight.py --project linesight-alice --env-file .env --file docker-compose.yml
python scripts/preflight.py --project linesight-alice --env-file .env --file docker-compose.yml --check-db
```

Do not remove an override or change an existing project's identity to fix login.
Keep workstation paths, rollback images and external volume identifiers outside
Git. Preserve `SECRET_KEY` across recreation so tokens remain valid.

## Existing-volume password mismatch: safe recovery

`POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` initialize an EMPTY data
directory only. Recreating PostgreSQL with new environment values does not alter
stored roles, databases or passwords. A healthcheck failure after such a change is
expected; do not reset the volume.

1. Identify the original project, actual PostgreSQL/media mounts and original
   role/database with the installation owner. Privately inspect configuration;
   do not paste credentials into chat or logs. Wait for active processing to finish.
2. Before changing credentials or stateful configuration, stop API/Worker writes
   and prepare protected, verified backups of PostgreSQL, media, models, `.env`
   and local overrides. Use a custom-format dump and verify a restore on separately
   approved storage; never restore over the active database. PowerShell text
   redirection can corrupt binary dumps: write inside the container then use
   `docker cp`. Retain the originals and roles/ownership information.
3. Preferred recovery: restore the KNOWN ORIGINAL user/database/password in `.env`
   (and any legacy URL override). Do not invent a new user or database. Run
   config preflight. If the postgres container has stale environment, an owner
   may recreate ONLY `postgres` in the SAME project with the SAME verified volume
   and same PostgreSQL major version. Never build/upgrade PostgreSQL for this fix.
4. Run `python scripts/preflight.py --check-db`. Only after successful authentication,
   build API/Worker if necessary and start them; check login, existing inspection
   history, KPI counts, video/PDF access. Keep backups and original images.
5. If a password change is necessary, obtain explicit owner approval after verified
   backups. An authorized DBA can open an interactive `psql` session using the
   EXISTING administrator's access and run `\password existing_role`. This prompts
   without writing a cleartext SQL password into shell history. Update `.env` and
   any legacy override consistently. If PostgreSQL still has the old container
   environment, recreate only that service with the verified SAME volume as in
   step 3; then repeat preflight. Do not assume the old
   administrator is named `postgres`: initialization may use a custom role.
6. If original credentials/administrator access cannot be established, stop and
   contact the owner. Do not enable `trust`, reset PGDATA, create a replacement
   database, or run automatic password-reset scripts.

Rollback configuration/images within the SAME project and retained volumes.
A database snapshot rollback can discard newer inspections/reviews and requires
separate approval and a preservation plan. Routine recovery never uses `down -v`,
volume deletion, pruning or database resets.

## Start, stop and rebuild

With the same project/env/override selection used at installation:

```sh
docker compose up -d --no-build --no-recreate
docker compose ps
# Wait for processing; allow an active worker job to finish.
docker compose stop --timeout 1800
# UI only (does not recreate API, Worker or PostgreSQL):
docker compose build web
docker compose up -d --no-deps --no-build web
```

Before a rebuild, identify the actual service container via `docker compose ps -q
web`, inspect its image ID privately and tag that ID with your own rollback tag.
Do not assume a fixed `:current` image name. For rollback, select that saved image
in an ignored local override, then recreate only the affected service. Keep its
previous override too. API/Worker changes require tests, idle processing and
consistent settings; database/ML upgrades require a separate review.

Data locations: `pgdata` contains records; `media_data` contains uploads, finding
frames and reports; `data/weights` is a read-only worker bind; `data/demo` is an
optional API bind. Keep runtime data, backups and proprietary weights outside Git.

## Opt-in isolated regression validation

The complete Backend suite can run during an image build, without starting a
service, mounting any data volumes, or installing tools in a running container.
First build the API image, then pass its actual tag/ID explicitly:

```sh
docker build --file backend/Dockerfile.test --build-arg RUNTIME_IMAGE=YOUR_BUILT_API_IMAGE .
```

This test stage installs `backend/requirements-test.txt` in the build image only.
API/upload/review/PDF tests use temporary SQLite records and synthetic media.
It also checks connection configuration and preflight secret redaction. Build
output contains test results; the image is not an application deployment.

No running application needs to be stopped. Requires Compose 2.24.4+ (`!override`)
and an existing compatible Backend runtime image with project dependencies:

```sh
python scripts/test_compose_portability.py --image YOUR_EXISTING_BACKEND_IMAGE --project linesight-portability-your-test
```

This creates ONE isolated test project, private random credentials and its own
PostgreSQL/media volumes. It publishes no ports and mounts current sources
read-only; it does not mount production data/models. It verifies two independent
project/port configurations without creating those projects, a fresh PostgreSQL
initialization, API login, KPI data, Worker connectivity, regression tests, then a
wrong configured password against the SAME populated volume. It verifies failure,
restores the known test password and checks the preserved row. No role password is
changed. Finally it STOPS its containers and retains volumes/artifacts, even on
failure. It never deletes them. The printed artifact path contains a PRIVATE env
file: do not share or commit it.

A failed run can be resumed using the printed directory and SAME test project:
`--resume-dir PRIVATE_ARTIFACT_DIRECTORY`. Ownership is checked against the test
API's Compose labels. Use resume only after the initial fixture was created; an
earlier failure needs investigation, not a volume reset. This source-mounted test
validates runtime/configuration, not a clean rebuild of every heavyweight image.

See [Frontend checks](docs/frontend.md) and the
[KPI contract](frontend/DASHBOARD_KPI_API_REQUIREMENTS.md).
