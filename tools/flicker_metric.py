"""NPR 时域闪烁指标（P0-3）。

把一段测试序列和同机位的超采样参考序列逐帧对比，输出：
- static_error：边缘区域内 |测试 - 参考| 的均值（静帧走样量）；
- flicker：边缘区域内 |err_t - err_{t-1}| 的均值，即误差在相邻帧之间的变化（闪烁量）。
  参考序列已经包含真实运动，所以这里只剩"抗锯齿/时域处理造成的跳变"；
- 热力图：逐像素的平均闪烁量，归一化后存成 PNG。

用法：
    python -I tools/flicker_metric.py --test <测试帧目录> --ref <参考帧目录> --out <输出目录>

两组帧按文件名排序后一一对应，分辨率必须一致。读取 PNG/JPG（8 或 16 位）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def load_luma(path: Path) -> np.ndarray:
    """读入图像并转成 0..1 的线性无关亮度（直接对编码值加权，不做 sRGB 解码）。"""
    img = Image.open(path)
    arr = np.asarray(img)
    if arr.dtype == np.uint16 or img.mode in ("I;16", "I;16B", "I"):
        scale = 65535.0
    else:
        scale = 255.0
    arr = arr.astype(np.float64) / scale
    if arr.ndim == 2:
        return arr
    return arr[..., :3] @ LUMA


def edge_mask(ref: np.ndarray, threshold: float = 0.02, dilate: int = 1) -> np.ndarray:
    """从参考帧的梯度求边缘区域，再按 dilate 像素膨胀。"""
    gy, gx = np.gradient(ref)
    mask = np.hypot(gx, gy) > threshold
    for _ in range(dilate):
        m = mask.copy()
        m[1:, :] |= mask[:-1, :]
        m[:-1, :] |= mask[1:, :]
        m[:, 1:] |= mask[:, :-1]
        m[:, :-1] |= mask[:, 1:]
        mask = m
    return mask


def compute(test_frames: list[np.ndarray], ref_frames: list[np.ndarray],
            threshold: float = 0.02, dilate: int = 1) -> dict:
    if len(test_frames) != len(ref_frames):
        raise ValueError(f"帧数不一致：测试 {len(test_frames)}，参考 {len(ref_frames)}")
    if len(test_frames) < 2:
        raise ValueError("至少需要 2 帧才能计算闪烁")
    shape = test_frames[0].shape
    for i, (t, r) in enumerate(zip(test_frames, ref_frames)):
        if t.shape != shape or r.shape != shape:
            raise ValueError(f"第 {i} 帧分辨率不一致")

    # 所有帧的边缘取并集，避免运动物体在某些帧没被统计
    mask = np.zeros(shape, dtype=bool)
    for r in ref_frames:
        mask |= edge_mask(r, threshold, dilate)
    n_mask = int(mask.sum())
    if n_mask == 0:
        raise ValueError("参考帧里没有检测到边缘，调低 --threshold")

    errs = [t - r for t, r in zip(test_frames, ref_frames)]
    static = float(np.mean([np.abs(e)[mask].mean() for e in errs]))
    deltas = [np.abs(errs[i] - errs[i - 1]) for i in range(1, len(errs))]
    flicker = float(np.mean([d[mask].mean() for d in deltas]))
    heat = np.mean(deltas, axis=0)
    per_frame = [float(d[mask].mean()) for d in deltas]
    return {
        "frames": len(test_frames),
        "edge_pixels": n_mask,
        "static_error": static,
        "flicker": flicker,
        "flicker_per_frame": per_frame,
        "heatmap": heat,
        "mask": mask,
    }


def save_heatmap(heat: np.ndarray, path: Path, vmax: float | None = None) -> float:
    vmax = float(vmax if vmax is not None else max(heat.max(), 1e-9))
    v = np.clip(heat / vmax, 0.0, 1.0)
    # 黑 → 红 → 黄 → 白
    rgb = np.stack([np.clip(v * 3, 0, 1), np.clip(v * 3 - 1, 0, 1), np.clip(v * 3 - 2, 0, 1)], axis=-1)
    Image.fromarray((rgb * 255).astype(np.uint8)).save(path)
    return vmax


def list_frames(folder: Path) -> list[Path]:
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not files:
        raise ValueError(f"{folder} 里没有图像")
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", required=True, type=Path)
    ap.add_argument("--ref", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--threshold", type=float, default=0.02, help="边缘梯度阈值（0..1 亮度）")
    ap.add_argument("--dilate", type=int, default=1, help="边缘膨胀像素数")
    ap.add_argument("--heat-max", type=float, default=None, help="热力图满量程；A/B 两次对比时用同一个值")
    a = ap.parse_args(argv)

    test = [load_luma(p) for p in list_frames(a.test)]
    ref = [load_luma(p) for p in list_frames(a.ref)]
    res = compute(test, ref, a.threshold, a.dilate)
    a.out.mkdir(parents=True, exist_ok=True)
    vmax = save_heatmap(res["heatmap"], a.out / "flicker_heatmap.png", a.heat_max)
    summary = {k: v for k, v in res.items() if k not in ("heatmap", "mask")}
    summary.update({"heat_max": vmax, "test": str(a.test), "ref": str(a.ref),
                    "threshold": a.threshold, "dilate": a.dilate})
    (a.out / "flicker.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"frames={res['frames']} edge_pixels={res['edge_pixels']} "
          f"static_error={res['static_error']:.5f} flicker={res['flicker']:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
