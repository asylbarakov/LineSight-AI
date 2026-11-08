"""YOLO images must include tracking dependencies before handling a real job."""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec("ultralytics"), "API image intentionally excludes YOLO")
class WorkerRuntime(unittest.TestCase):
    def test_bytetrack_imports_without_installing_packages_at_runtime(self):
        self.assertIsNotNone(importlib.util.find_spec("lap"),
                             "Install lap with the YOLO image, not on the first inspection.")
        from ultralytics.trackers.byte_tracker import BYTETracker
        self.assertTrue(callable(BYTETracker))
