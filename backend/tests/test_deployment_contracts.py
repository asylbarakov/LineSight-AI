"""Release packaging checks; run inside the isolated Backend test build."""
import importlib.metadata
import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


def requirements(name):
    return [line.strip().split("==", 1) for line in (ROOT / "backend" / name).read_text().splitlines()
            if line.strip() and not line.startswith("#")]


class DeploymentContracts(unittest.TestCase):
    def test_common_lock_matches_runtime(self):
        for package, version in requirements("requirements.lock.txt"):
            self.assertEqual(importlib.metadata.version(package), version, package)

    @unittest.skipUnless(importlib.util.find_spec("ultralytics"), "API profile excludes YOLO")
    def test_ml_lock_matches_runtime(self):
        for filename in ("requirements-yolo.lock.txt", "requirements-torch.lock.txt"):
            for package, version in requirements(filename):
                if package == "opencv-python":
                    continue  # Deliberately replaced by the identical headless version.
                self.assertEqual(importlib.metadata.version(package), version, package)

    def test_ci_workflows_are_valid_yaml(self):
        for path in (ROOT / ".github/workflows").glob("*.yml"):
            config = yaml.safe_load(path.read_text())
            self.assertIsInstance(config["jobs"], dict)
            self.assertTrue(all(isinstance(job["steps"], list) for job in config["jobs"].values()))

    def test_shell_entrypoint_has_unix_line_endings(self):
        self.assertNotIn(b"\r", (ROOT / "start.sh").read_bytes())
