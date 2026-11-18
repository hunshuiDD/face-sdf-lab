"""用合成序列验证闪烁指标的单调性：同一个缓慢平移的硬边圆盘，
- 点采样（每像素 1 个样本，走样）→ 闪烁大；
- 按像素宽度做解析式平滑（模拟 fwidth 抗锯齿）→ 闪烁小；
- 与参考完全相同 → 闪烁为 0。
参考序列用 8×8 超采样生成。"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import flicker_metric as fm  # noqa: E402

H = W = 64
R = 14.3


def disk(cx, cy, mode, ss=8):
    if mode == "ref":
        o = (np.arange(ss) + 0.5) / ss
        ys = (np.arange(H)[:, None, None, None] + o[None, None, :, None])
        xs = (np.arange(W)[None, :, None, None] + o[None, None, None, :])
        d = np.hypot(xs - cx, ys - cy)
        return (d < R).mean(axis=(2, 3)).astype(np.float64)
    y, x = np.mgrid[0:H, 0:W] + 0.5
    d = np.hypot(x - cx, y - cy)
    if mode == "point":
        return (d < R).astype(np.float64)
    if mode == "aa":  # 1 像素宽的线性过渡，相当于 saturate((R-d)/fwidth(d)+0.5)
        return np.clip(R - d + 0.5, 0.0, 1.0)
    raise ValueError(mode)


def seq(mode, n=24):
    return [disk(32.0 + 0.37 * i, 31.6 + 0.11 * i, mode) for i in range(n)]


class FlickerMetricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = seq("ref")
        cls.point = fm.compute(seq("point"), cls.ref)
        cls.aa = fm.compute(seq("aa"), cls.ref)

    def test_identical_sequence_has_zero_error(self):
        r = fm.compute(self.ref, self.ref)
        self.assertEqual(r["flicker"], 0.0)
        self.assertEqual(r["static_error"], 0.0)

    def test_point_sampling_flickers_more_than_analytic_aa(self):
        self.assertGreater(self.point["flicker"], 3 * self.aa["flicker"])
        self.assertGreater(self.point["static_error"], self.aa["static_error"])

    def test_aa_is_not_perfect(self):
        self.assertGreater(self.aa["flicker"], 0.0)

    def test_heatmap_concentrates_on_edges(self):
        heat, mask = self.point["heatmap"], self.point["mask"]
        self.assertGreater(heat[mask].mean(), 10 * (heat[~mask].mean() + 1e-12))

    def test_mismatched_lengths_rejected(self):
        with self.assertRaises(ValueError):
            fm.compute(seq("point", 5), self.ref)

    def test_cli_roundtrip_with_png_files(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name, frames in (("test", seq("point", 6)), ("ref", self.ref[:6])):
                (d / name).mkdir()
                for i, f in enumerate(frames):
                    Image.fromarray((f * 65535).astype(np.uint16)).save(d / name / f"f{i:04d}.png")
            rc = fm.main(["--test", str(d / "test"), "--ref", str(d / "ref"), "--out", str(d / "out")])
            self.assertEqual(rc, 0)
            self.assertTrue((d / "out" / "flicker_heatmap.png").exists())
            self.assertIn('"flicker"', (d / "out" / "flicker.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
