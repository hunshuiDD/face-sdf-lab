"""用合成的 csvprofile 风格 CSV 验证解析、分位数和 2% 噪声判定。"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import gpu_csv_report as g  # noqa: E402


def write_csv(path: Path, gpu_base: float, basepass: float, n: int = 200):
    rng = np.random.default_rng(1)
    lines = ["FrameTime,GameThreadTime,RenderThreadTime,GPUTime,GPU/BasePass,GPU/Lights,Unrelated"]
    for _ in range(n):
        bp = basepass + rng.normal(0, 0.01)
        lt = 1.5 + rng.normal(0, 0.01)
        gpu = gpu_base + bp + lt
        lines.append(f"{gpu + 0.5:.4f},4.0,5.0,{gpu:.4f},{bp:.4f},{lt:.4f},7")
    lines.append("[HasHeaderRowAtEnd],1")
    lines.append("[platform],Windows,[config],Development")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class GpuCsvTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        self.a, self.b, self.c = d / "a.csv", d / "b.csv", d / "c.csv"
        write_csv(self.a, 10.0, 3.0)
        write_csv(self.b, 10.0, 3.02)   # 只差 0.02 ms：测不出
        write_csv(self.c, 10.0, 2.0)    # BasePass 少 1 ms：变快

    def tearDown(self):
        self.tmp.cleanup()

    def test_metadata_rows_are_ignored(self):
        cols = g.load(self.a)
        self.assertEqual(len(cols["GPUTime"]), 200)

    def test_wildcard_selects_gpu_passes(self):
        rep = g.report(self.a, g.DEFAULT_COLUMNS)
        self.assertIn("GPU/BasePass", rep)
        self.assertIn("GPU/Lights", rep)
        self.assertNotIn("Unrelated", rep)

    def test_percentiles_are_ordered(self):
        s = g.report(self.a, ["GPUTime"])["GPUTime"]
        self.assertLessEqual(s["p50"], s["p95"])
        self.assertLessEqual(s["p95"], s["p99"])
        self.assertAlmostEqual(s["p50"], 14.5, delta=0.1)

    def test_small_difference_is_noise(self):
        cmp_ = g.compare(g.report(self.a, ["GPU/BasePass"]), g.report(self.b, ["GPU/BasePass"]))
        self.assertEqual(cmp_["GPU/BasePass"]["verdict"], "测不出")

    def test_real_difference_is_detected(self):
        cmp_ = g.compare(g.report(self.a, ["GPU/BasePass"]), g.report(self.c, ["GPU/BasePass"]))
        self.assertEqual(cmp_["GPU/BasePass"]["verdict"], "变快")
        self.assertAlmostEqual(cmp_["GPU/BasePass"]["delta_ms"], -1.0, delta=0.05)

    def test_cli_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = g.main([str(self.a), "--compare", str(self.c)])
        self.assertEqual(rc, 0)
        self.assertIn("变快", buf.getvalue())

    def test_ue_events_extended_header_and_short_rows(self):
        self.a.write_text("EVENTS,FrameTime,GPUTime\n,10,8\nCmd: csvprofile STOP##1,12,9,3\n"
                          "EVENTS,FrameTime,GPUTime,GPU/BasePass\n[HasHeaderRowAtEnd],1\n", encoding="utf-8")
        cols = g.load(self.a)
        self.assertEqual(cols["GPUTime"].tolist(), [8.0, 9.0])
        self.assertTrue(np.isnan(cols["GPU/BasePass"][0]))
        self.assertEqual(cols["GPU/BasePass"][1], 3.0)


if __name__ == "__main__":
    unittest.main()
