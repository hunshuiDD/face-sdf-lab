import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import contact_sheet as cs  # noqa: E402


class ContactSheetTests(unittest.TestCase):
    def test_grid_missing_and_black_frames_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            Image.new("RGB", (160, 90), (120, 100, 90)).save(d / "LM_day__yaw000.png")
            Image.new("RGB", (160, 90), (110, 90, 80)).save(d / "LM_day__yaw090.png")
            Image.new("RGB", (160, 90), (0, 0, 0)).save(d / "LM_night__yaw000.png")
            Image.new("RGB", (160, 90), (9, 9, 9)).save(d / "unrelated.png")
            r = cs.build(d, d / "out" / "sheet.png", cell=160)
            self.assertEqual(r["rows"], ["day", "night"])
            self.assertEqual(r["cols"], ["yaw000", "yaw090"])
            self.assertEqual(r["images"], 3)
            self.assertIn("night/yaw000: 全黑", r["problems"])
            self.assertIn("night/yaw090: 缺图", r["problems"])
            self.assertTrue((d / "out" / "sheet.png").exists())

    def test_row_labels_with_underscores(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            Image.new("RGB", (32, 18), (128, 128, 128)).save(d / "LM_street_dusk__yaw045_pitch20.png")
            rows, cols, _ = cs.parse(d)
            self.assertEqual(rows, ["street_dusk"])
            self.assertEqual(cols, ["yaw045_pitch20"])


if __name__ == "__main__":
    unittest.main()
