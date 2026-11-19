"""Measure the original face ROI and the black-background head silhouette."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

FACE = np.s_[145:323, 126:281]


def read_case(path, size):
    receipt = json.loads((path / "run.json").read_text(encoding="utf8"))
    assert receipt["status"] == "COMPLETE"
    assert [f["i"] for f in receipt["frames"]] == list(range(32))
    assert receipt["case"]["size"] == size and receipt["mid_scalars"]["SoftDegrees"] == 3
    hashes, frames = [], []
    for i in range(32):
        frame = path / f"frame_{i:03}.png"
        hashes.append(hashlib.sha256(frame.read_bytes()).hexdigest())
        with Image.open(frame) as source:
            assert source.size == (size, size)
            rgb = source.convert("RGB")
            if size != 384:
                rgb = rgb.resize((384, 384), Image.Resampling.BOX)
            frames.append(np.asarray(rgb))
    assert len(set(hashes)) == 32
    return receipt, frames, hashes


def measure(args):
    sys.path.insert(0, str(args.tools.resolve()))
    import flicker_metric as fm

    ref, images, ref_hashes = read_case(args.runs / "reference", 1536)
    assert ref["cvars"]["r.AntiAliasingMethod"] == ref["mid_scalars"]["EnableAA"] == 0
    reference = [(im.astype(float) / 255) @ fm.LUMA for im in images]
    # Background is black; the dark side of the opaque head is above 0.1.
    # Threshold only the reference. Measure residuals of the original luminance.
    outline = np.logical_or.reduce([fm.edge_mask((r > 0.1).astype(float)) for r in reference])
    assert 0 < outline.sum() < outline.size / 8
    metrics = {}
    hashes = {"reference": ref_hashes}
    for name in args.cases:
        receipt, frames, hashes[name] = read_case(args.runs / name, 384)
        assert receipt["cvars"]["r.AntiAliasingMethod"] == 4
        if name == "baseline":
            assert receipt["mid_scalars"]["EnableAA"] == 0
        cfg = receipt["case"]
        assert receipt["mid_scalars"]["EnableAA"] == min(cfg["analytic"], cfg.get("tsr_width", 1))
        assert all(receipt["cvars"][k] == v for k, v in ref["cvars"].items() if k != "r.AntiAliasingMethod")
        assert all(receipt["mid_scalars"][k] == v for k, v in ref["mid_scalars"].items() if k != "EnableAA")
        for key in ("mesh", "camera", "engine", "light_to_surface_opposite_direction"):
            assert receipt[key] == ref[key], key
        camera_error = float(np.max(np.abs(np.array([f["pov_camera_cm"] for f in receipt["frames"]])
                                           - [f["pov_camera_cm"] for f in ref["frames"]])))
        assert camera_error < 1e-5
        luma = [(im.astype(float) / 255) @ fm.LUMA for im in frames]
        face = fm.compute([a[FACE] for a in luma], [a[FACE] for a in reference])
        err = np.array(luma) - reference
        per_frame = np.abs(np.diff(err, axis=0))[:, outline].mean(axis=1)
        metrics[name] = {
            "weight": receipt["mid_scalars"]["EnableAA"], "max_camera_diff_cm": camera_error,
            "face": {k: v for k, v in face.items() if k not in ("heatmap", "mask")},
            "outline": {"flicker": float(per_frame.mean()), "edge_pixels": int(outline.sum()),
                        "static_error": float(np.abs(err[:, outline]).mean()), "flicker_per_frame": per_frame.tolist()}}
    for name, case in metrics.items():
        for region in ("face", "outline"):
            case[region]["change_pct"] = 100 * (case[region]["flicker"] / metrics["baseline"][region]["flicker"] - 1)
        case["png_identical_to_baseline"] = sum(a == b for a, b in zip(hashes[name], hashes["baseline"]))
        print(name, *(f"{case[k]['flicker']:.9f} ({case[k]['change_pct']:+.4f}%)" for k in ("face", "outline")),
              case["png_identical_to_baseline"])
    args.out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(outline).save(args.out / "silhouette_mask.png")
    for name, data in (("metrics", metrics), ("hashes", hashes)):
        (args.out / (name + ".json")).write_text(json.dumps(data, indent=2), encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for arg in ("runs", "tools", "out"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("cases", nargs="+", help="Include baseline; use a reference/ capture at 1536 square.")
    measure(parser.parse_args())
