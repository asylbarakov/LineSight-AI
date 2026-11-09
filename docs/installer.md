# Installation and safe application updates

Prerequisites: Git, a running Docker Engine/Desktop with Linux containers and
Compose v2, Python 3.10+ (tested with 3.12), and registry/network access for the
first image build. Full CPU YOLO has been validated on Linux amd64, including
Windows Docker Desktop's Linux VM. Other architectures require separate ML tests.
No host Node, pip dependencies, local database or proprietary font is required.
Proxima Nova uses the browser machine's installed font; the licensed bundled
Onest font is the fallback on machines without it.

## New computer

Linux:

```sh
git clone --branch feature/linesight-frontend-ui --single-branch https://github.com/asylbarakov/LineSight-AI.git
cd LineSight-AI
sh ./start.sh
```

Windows PowerShell, with Docker Desktop running in Linux-container mode:

```powershell
git clone --branch feature/linesight-frontend-ui --single-branch https://github.com/asylbarakov/LineSight-AI.git
Set-Location LineSight-AI
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

The execution-policy option applies only to that PowerShell process. The Windows
wrapper selects a suitable Python through `py -3` or `python`, rejecting versions
older than 3.10. `LINESIGHT_PYTHON` can select a specific executable on either OS.
It must be an executable path, not a shell command with arguments.

The installer generates a private `.env` from `.env.example` on the first run,
including a random database password, administrator password and persistent token
signing key. Open the LOCAL `.env` to read `ADMIN_LOGIN` / `ADMIN_PASSWORD`; never
paste it into chat, issue trackers, CI artifacts or Git. Linux permissions are
0600; Windows generated files have restricted ACLs. Valid existing secrets are
never rotated by the installer. An untouched example copy can be completed only
before any associated data exists.

Default full mode requires `data/weights/best.pt`, already tracked by this branch.
It builds CPU PyTorch, YOLO and ByteTrack dependencies; the first build can take
many minutes. To deliberately install capture-quality checks without equipment
detection, use `sh ./start.sh --ml none` (Windows: append `--ml none`). That mode
is explicitly reported and does not invent defect findings. Existing ML settings
are preserved; change the existing `.env` deliberately to change mode.

The final message gives the URL (default http://localhost:3004). New computers
start with an empty database and zero KPIs, not another developer's inspections.
On a fresh installation, optional custom ports can be set in a copied `.env`
before invoking the installer. Existing data credentials must not be replaced.
Host port conflicts stop setup rather than stopping another application.

## Check without changes

```sh
sh ./start.sh --check
```

Windows: append `--check` to the PowerShell command above. This validates Docker,
configuration, mounts, ports, model availability and (if already running) actual
PostgreSQL authentication through service DNS. It does not write `.env`/state,
start services or create volumes. If PostgreSQL is stopped, the check reports
that authentication could not be verified without starting it.

## Existing installation: adopt once

First inspect `docker compose ls --all` and confirm the project containing the
inspection data. Do not create a new project just to bypass a password failure.
Preserve the original `.env` and any ignored `docker-compose.override.yml`.

```sh
sh ./start.sh --check --project YOUR_EXISTING_PROJECT
sh ./start.sh --adopt --project YOUR_EXISTING_PROJECT
```

Windows: pass the same arguments to `start.ps1`. Replace the example project name
with the actual existing name. Adoption verifies running mounts and DB access,
records the actual volume names/creation identities and PostgreSQL image, then
builds/checks application updates. It does not reset records, replace credentials
or attach another PostgreSQL instance to the data directory. If the original `.env`
has placeholder secrets or the password does not match the old volume, adoption
stops BEFORE updating services. Follow [credential recovery](../DOCKER_OPERATIONS.md#existing-volume-password-mismatch-safe-recovery).

`.linesight/deployment.json` stores the project, database name, volume identities,
PostgreSQL image and model schema contract. `.linesight/compose.runtime.json`
pins those volumes as external and retains the original PostgreSQL image. These
files are local and ignored by Git/Docker build contexts. Keep them with `.env`
and local overrides when moving/renaming the folder. A lost/replaced volume or
conflicting project name stops updates; the installer never silently supplies an
empty replacement. If state is lost, restore its backup or explicitly adopt the
verified original project with the original configuration.

An intentional second independent installation needs a separate checkout and
`--new --project DIFFERENT_NAME` plus unused host ports. This flag does not bypass
saved identities or allow resetting data in an existing installation.

## Update after a code change

With a clean working tree, pull the intended feature branch without merging other
branches, then repeat the SAME start command:

```sh
git pull --ff-only origin feature/linesight-frontend-ui
sh ./start.sh
```

Windows: use the PowerShell start command. The installer builds cached images,
compares their IDs and Compose configuration hashes, and updates changed
application services only. An unchanged deployment is not restarted. A web-only
change leaves API/Worker running. Backend/Worker updates require an idle queue;
the installer checks it read-only, quiesces API writes, checks again, then stops
the old Worker before starting its replacement. A job arriving during this window
causes the old API to resume and the update to stop. Retry after processing ends.
Failed queued jobs are not deleted or rewritten by setup.

Running PostgreSQL is never recreated for application updates. A stopped original
container is started with its existing configuration; recreation, if necessary,
uses the pinned image and verified existing volumes. Missing volumes stop setup.
Passwords and signing key remain unchanged. Registry/download or build failures
stop the sequence; subsequent commands are not executed automatically.

Changes to mapped model declarations in `backend/app/db.py` stop application
updates for a separately reviewed backup/migration. Comments/connection helpers
do not trigger that guard. This is a conservative schema-contract check, not a
migration engine. There is no automatic password reset, database reset, migration,
`down -v`, pruning, image/volume deletion or Git commit/push operation.

## Failure and rollback

Keep the local state and volumes. Errors never print resolved `.env` values or raw
secret-bearing Docker errors. Check Docker/registry connectivity and inspect the
selected project's logs PRIVATELY; do not publish `docker compose config` output.
Before changing application containers, when all previous services are healthy,
the installer records their image IDs in `.linesight/rollback.json`; the images
are not deleted. An unchanged or unhealthy deployment does not replace an older
rollback snapshot. If deployment health fails,
stop further updates, retain this file and diagnose the failed service.

For a reviewed manual rollback, use the same project, `.env`, base file and local
override, then append `.linesight/compose.runtime.json` and
`.linesight/rollback.json` as the LAST Compose files. With the queue idle, recreate
only `api worker web` using `up -d --no-deps --no-build`; never recreate PostgreSQL
or restore an old database snapshot to roll back application code. An actual data
restore or migration requires separately verified backups and approval.

## Repeatable dependencies and tests

The base Python/Node/PostgreSQL image digests are pinned to the verified
multi-platform manifests. `backend/requirements.lock.txt` pins the API/common
runtime; `requirements-torch.lock.txt` pins CPU Torch/torchvision, and
`requirements-yolo.lock.txt` pins the remaining ML runtime, including `lap`.
The GUI OpenCV wheel required by YOLO is installed at the pinned version, then
replaced with pinned headless OpenCV as in the existing image. Frontend uses
`package-lock.json` and `npm ci`. Distribution OS security packages remain fetched
from their repositories: image builds are repeatable application environments,
not byte-identical offline archives. GPU libraries need a separately validated
lock/profile rather than reusing the CPU lock with a different index.

Run host installer tests without extra pip dependencies:

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_installer*.py' -v
```

Full API/Worker suites run with `backend/Dockerfile.test` against temporary SQLite
and synthetic media. CI additionally starts a disposable installation on the CI
runner, verifies login/proxy/KPIs, persists a CI-only sentinel inspection, repeats
setup and checks that its project, data volumes, `.env` and PostgreSQL container
are unchanged. These CI steps do not run against the maintained local stack.
