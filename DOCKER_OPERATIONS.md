# LineSight AI — Docker setup

Run commands from the repository root. The default Compose project is
`linesight-ai-frontend-ui`; reuse that name for subsequent commands.
Frontend: http://localhost:3004. Backend: http://localhost:8000. PostgreSQL is
internal-only. Host bindings are limited to loopback.

## New developer environment

1. Copy `.env.example` to `.env`. Choose your own admin/database passwords,
   update `DATABASE_URL` to match, and set a long random persistent `SECRET_KEY`.
   Never commit `.env` or print resolved credentials into shared logs.
2. Keep `DETECTOR=none` and `INSTALL_YOLO=0` for the lightweight pipeline without
   a neural detector. This mode can produce capture-quality findings; it does not
   fabricate equipment defects. YOLO requires your own authorized weights.
3. Build and start:

```sh
docker compose --project-name linesight-ai-frontend-ui config --quiet
docker compose --project-name linesight-ai-frontend-ui build api worker web
docker compose --project-name linesight-ai-frontend-ui up -d --no-build
docker compose --project-name linesight-ai-frontend-ui ps
```

For YOLO, place weights at `data/weights/best.pt`, set `DETECTOR=yolo` and
`INSTALL_YOLO=1`, then explicitly rebuild the worker. CPU PyTorch is the default;
GPU deployment needs a separately configured runtime. Model/runtime data are not
part of these feature changes. Preserve existing team fixtures.

`WEB_PORT` and `API_PORT` configure host bindings. The frontend build rewrite must
remain `API_INTERNAL_URL=http://api:8000`: Compose DNS, not a host port/container IP.

## Existing environments and overrides

Do not run fresh-install instructions over an existing installation without
reviewing its volumes, images and environment. The portable base uses managed
`pgdata` and `media_data` volumes. Existing installations may use an ignored
`docker-compose.override.yml` for restored external volumes, pinned local runtimes
and build definitions. Compose loads this override automatically unless explicit
`--file` arguments select a different configuration.

Keep workstation paths, image/volume names and rollback snapshots outside Git.
Do not remove an existing override or replace `.env` with the example: that can
select different volumes or invalidate authentication. Never attach two PostgreSQL
containers to the same active PGDATA. Preserve `SECRET_KEY` across API recreations.

To validate only the portable base, without deploying or loading local overrides:

```sh
docker compose --file docker-compose.yml --env-file .env.example config --quiet
```

This checks syntax with example values. Never deploy placeholder credentials.

## Start, stop and inspect

```sh
docker compose --project-name linesight-ai-frontend-ui up -d --no-build --no-recreate
docker compose --project-name linesight-ai-frontend-ui ps
docker compose --project-name linesight-ai-frontend-ui logs --tail 100 api worker
```

Wait for processing to finish before stopping. The longer timeout permits an active
worker job to finish while keeping containers and data:

```sh
docker compose --project-name linesight-ai-frontend-ui stop --timeout 1800
```

## Rebuild only what changed

Save the previous image for rollback. For UI changes:

```sh
docker image tag linesight-ai-frontend-ui-web:current linesight-ai-frontend-ui-web:before-rebuild
docker compose --project-name linesight-ai-frontend-ui build web
docker compose --project-name linesight-ai-frontend-ui up -d --no-deps --no-build web
```

For Backend changes, use `api` in the corresponding image/build/up commands after
running Backend tests. Do not rebuild/recreate PostgreSQL or Worker for UI changes.
ML/database upgrades require a separate compatibility and backup review.

The portable base builds API/Worker with `backend/Dockerfile`. Local deployments
may select a verified runtime through an ignored override; that local image must
be retained or restored from its private backup before using the override.

## Data protection and rollback

- `pgdata`: persisted inspections and findings.
- `media_data`: uploaded videos, finding frames and generated PDFs under `/data`.
- `data/weights`: read-only worker model bind mount; keep an authorized local copy.
- `data/demo`: optional API demo bind, separate from the media volume.

Before stateful changes, quiesce writes/processing, create PostgreSQL custom-format
and media/model/config backups, and verify a restore on separate storage. Retain
roles/ownership and per-file SHA-256 manifests. Avoid redirecting binary dumps
through PowerShell text pipelines: write a container file and use `docker cp`.
Protect secret-bearing backups and keep them outside Git.

Rollback an application image within the same project, retaining current data:

```sh
docker image tag linesight-ai-frontend-ui-web:before-rebuild linesight-ai-frontend-ui-web:current
docker compose --project-name linesight-ai-frontend-ui up -d --no-deps --no-build web
```

An older database snapshot can lose new inspections/decisions. Returning to it
requires an explicit preservation plan; do not overwrite the live database.
Do not use `down -v`, volume/image pruning or database resets for routine work.

See [frontend features and checks](docs/frontend.md) and the
[KPI contract](frontend/DASHBOARD_KPI_API_REQUIREMENTS.md).
