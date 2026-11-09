"""CI-only fixture/persistence probe. Refuses local/production project namespaces."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("seed", "verify", "stop"))
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("CI fixture refused: this command is only for an isolated GitHub Actions runner.")
    state = json.loads((ROOT / ".linesight/deployment.json").read_text())
    project = state["project"]
    if not project.startswith("linesight-ci-") or any(not v["name"].startswith(project + "_") for v in state["volumes"].values()):
        raise SystemExit("CI fixture refused: project/volumes are not in the isolated CI namespace.")
    def run(*parts):
        result = subprocess.run(["docker", *parts], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if result.returncode:
            raise SystemExit("CI deployment probe failed; secret-bearing command output suppressed.")
        return result.stdout
    ids = run("ps", "-aq", "--filter", "label=com.docker.compose.project=" + project).split()
    items = json.loads(run("inspect", *ids)) if ids else []
    containers = {i["Config"]["Labels"]["com.docker.compose.service"]: i for i in items}
    if args.action == "stop":
        if ids:
            run("stop", "--time", "30", *ids)
        return
    if set(containers) != {"api", "worker", "web", "postgres"}:
        raise SystemExit("CI expected exactly four services.")
    volumes = json.loads(run("volume", "inspect", *[v["name"] for v in state["volumes"].values()]))
    snapshot = {"project": project, "postgres": containers["postgres"]["Id"],
                "volumes": {v["Name"]: v["CreatedAt"] for v in volumes},
                "env": hashlib.sha256((ROOT / ".env").read_bytes()).hexdigest()}
    snapshot_path = ROOT / ".linesight/ci-snapshot.json"
    if args.action == "verify" and snapshot != json.loads(snapshot_path.read_text()):
        raise SystemExit("CI persistence check failed: environment/PostgreSQL/volumes changed.")
    # Fixture writes are restricted above to a disposable CI project, never live data.
    code = '''import os,json,urllib.request
from app.config import Settings
from app.db import make_engine,make_session_factory,Inspection
from app import repository as repo
settings=Settings.from_env(); engine=make_engine(settings.database_url)
with make_session_factory(engine)() as session:
 if SEED and session.get(Inspection,"11111111-1111-4111-8111-111111111111") is None:
  repo.create_inspection(session,"11111111-1111-4111-8111-111111111111","Installer CI sentinel","ci-only.mp4",None)
  repo.mark_done(session,"11111111-1111-4111-8111-111111111111",1,1,{})
engine.dispose()
body=json.dumps({"login":settings.admin_login,"password":settings.admin_password}).encode()
req=urllib.request.Request("http://api:8000/api/login",data=body,headers={"Content-Type":"application/json"})
token=json.load(urllib.request.urlopen(req))["token"]
for origin in ["http://api:8000","http://web:3000"]:
 req=urllib.request.Request(origin+"/api/metrics",headers={"Authorization":"Bearer "+token})
 m=json.load(urllib.request.urlopen(req))
 assert (m["inspections_total"],m["detected_defects_total"],m["confirmed_defects_total"])==(1,0,0)
assert urllib.request.urlopen("http://web:3000/login").status==200
print("CI login, proxy and persisted KPI sentinel verified.")
'''.replace("SEED", "True" if args.action == "seed" else "False")
    run("exec", containers["api"]["Id"], "python", "-B", "-c", code)
    if args.action == "seed":
        snapshot_path.write_text(json.dumps(snapshot))
    print("CI persistence and authentication probe passed.")


if __name__ == "__main__":
    main()
