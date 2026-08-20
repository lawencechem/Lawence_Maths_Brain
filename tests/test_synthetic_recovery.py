import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "references"
    / "roles"
    / "编程手"
    / "scripts"
    / "synthetic_recovery.py"
)
SPEC = importlib.util.spec_from_file_location("synthetic_recovery", MODULE_PATH)
sr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sr)


class DiscordanceTriggerTests(unittest.TestCase):
    def test_paired_covariance_changes_difference_uncertainty(self):
        _, independent_threshold = sr.discordance_trigger(0, 1, 3, 1)
        _, paired_threshold = sr.discordance_trigger(0, 1, 3, 1, covariance=0.5)

        self.assertAlmostEqual(independent_threshold, 2 * (2 ** 0.5))
        self.assertAlmostEqual(paired_threshold, 2.0)
        self.assertLess(paired_threshold, independent_threshold)


if __name__ == "__main__":
    unittest.main()
