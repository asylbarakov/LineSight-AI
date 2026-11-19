"""Run the CPU-only suite without importing optional depth dependencies."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
suite = unittest.TestSuite()
for file in sorted((ROOT / 'tests').glob('test_*.py')):
    if file.name != 'test_depth.py':
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=file.name))
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
