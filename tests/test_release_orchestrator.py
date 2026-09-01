import datetime as dt
import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "release_orchestrator.py"
spec = importlib.util.spec_from_file_location("release_orchestrator", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class ReleaseOrchestratorTests(unittest.TestCase):
    def base_release(self):
        return {
            "id": "example-r1",
            "title": "Example R1",
            "source": "articles/example.qmd",
            "pr_number": 7,
            "state": "scheduled",
            "approved": True,
            "release_at": "2026-09-05T09:00:00+08:00",
            "channels": {"github_pages": True, "distribution_bundle": True, "x_direct": False},
        }

    def test_due_release_requires_time_to_arrive(self):
        queue = {"releases": [self.base_release()]}
        before = dt.datetime(2026, 9, 5, 0, 59, tzinfo=dt.timezone.utc)
        at_time = dt.datetime(2026, 9, 5, 1, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(module.due_releases(queue, before), [])
        self.assertEqual(len(module.due_releases(queue, at_time)), 1)

    def test_unapproved_scheduled_release_is_invalid(self):
        item = self.base_release()
        item["approved"] = False
        errors = module.validate_release(item)
        self.assertTrue(any("approved=true" in error for error in errors))

    def test_planned_release_may_have_no_date(self):
        item = self.base_release()
        item.update(state="planned", approved=False, release_at=None)
        self.assertEqual(module.validate_release(item), [])

    def test_timezone_is_mandatory(self):
        item = self.base_release()
        item["release_at"] = "2026-09-05T09:00:00"
        errors = module.validate_release(item)
        self.assertTrue(any("timezone" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
