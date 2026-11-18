"""Build the neck-only cleanup for the CC0 GEO-head_stylized bake."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np
from PIL import Image


def rgba16(gray, coverage):
    channels = np.stack((gray[:, ::-1], gray, coverage * np.uint16(65535),
                         np.full_like(gray, 65535)), axis=-1).astype(">u2")
    h, w = gray.shape
    rows = channels.view("u1").reshape(h, w * 8)
    data = b"".join(b"\0" + row.tobytes() for row in rows)

    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(data, 6)) + chunk(b"IEND", b""))


def build(bake, out):
    out.mkdir(exist_ok=True, parents=True)
    with np.load(bake / "cycles_visibility.npz") as visibility:
        z = visibility["position"][..., 2]
        covered = visibility["coverage"]
        protected = visibility["protection"]
    fields, hashes = {}, {}
    for variant in ("raw", "strong"):
        stem = f"T_PublicHead_cycles_{variant}"
        with Image.open(bake / (stem + "_gray16.png")) as im:
            fields[variant] = np.array(im, dtype=np.uint16)
        source = (bake / (stem + "_project_RGBA16.png")).read_bytes()
        assert rgba16(fields[variant], covered) == source, "Source does not match this bake's packing"
        hashes[variant] = hashlib.sha256(source).hexdigest()

    # Local Z in this CC0 head's bake. Both variants agree across the cut.
    cutoff = 0.04535
    mask = covered & ~protected & (z < cutoff)
    raw, strong = fields["raw"], fields["strong"]
    different = raw != strong
    assert not np.any(different & covered & (np.abs(z - cutoff) < .00068))
    result = np.where(mask, strong, raw)
    changed = result != raw
    # Check both the G thresholds and the physical locations of the mirrored R changes.
    for channel_changes in (changed, changed[:, ::-1]):
        assert not np.any(channel_changes & protected)
        assert not np.any(channel_changes & covered & (z >= cutoff))
    assert changed.any() and np.array_equal(result[mask], strong[mask])
    target = out / "T_PublicHead_cycles_neck_project_RGBA16.png"
    target.write_bytes(rgba16(result, covered))
    with Image.open(target) as saved:
        saved.verify()
    Image.fromarray(mask.astype("u1") * 255).save(out / "CC0_neck_mask.png")
    report = {"head": "GEO-head_stylized", "size": list(z.shape),
              "source_world_z_cut": cutoff, "covered_texels": int(covered.sum()),
              "mask_texels": int(mask.sum()), "changed_g_texels": int(changed.sum()),
              "protected_texels": int(protected.sum()), "protected_rg_changed": 0,
              "covered_rg_changed_above_cutoff": 0,
              "raw_strong_changed_g": int(different.sum()),
              "nearest_changed_z_below_cut": float(z[different & (z < cutoff)].max()),
              "nearest_changed_z_above_cut": float(z[different & (z >= cutoff)].min()),
              "source_sha256": hashes, "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (out / "build.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bake", type=Path, help="PublicHead output from the normal Cycles pipeline")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    build(args.bake, args.out)
