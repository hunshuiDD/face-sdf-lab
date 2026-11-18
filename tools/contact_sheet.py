"""把光照矩阵截图拼成网格（P0-2 的离线部分）。

文件名约定（由 ue/python/light_matrix_capture.py 生成）：
    LM_<行标签>__<列标签>.png      例：LM_dusk__yaw090_pitch20.png
行、列按文件名里出现的顺序排列；缺的格子填灰色并在图上标"缺"。

用法：
    python -I tools/contact_sheet.py <截图目录> --out sheet.png [--cell 480]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat

PAT = re.compile(r"^LM_(?P<row>[^_]+(?:_[^_]+)*?)__(?P<col>.+)\.(png|jpg|jpeg)$", re.I)


def parse(folder: Path):
    cells, rows, cols = {}, [], []
    for p in sorted(folder.iterdir()):
        m = PAT.match(p.name)
        if not m:
            continue
        r, c = m.group("row"), m.group("col")
        if r not in rows:
            rows.append(r)
        if c not in cols:
            cols.append(c)
        cells[(r, c)] = p
    return rows, cols, cells


def check_frame(img: Image.Image) -> str | None:
    """全黑或全白帧返回原因，否则返回 None。"""
    mean = sum(ImageStat.Stat(img.convert("L")).mean)
    if mean < 2:
        return "全黑"
    if mean > 253:
        return "全白"
    return None


def build(folder: Path, out: Path, cell: int = 480) -> dict:
    rows, cols, cells = parse(folder)
    if not cells:
        raise ValueError(f"{folder} 里没有 LM_<行>__<列>.png 格式的截图")
    ch = cell * 9 // 16
    label_w, label_h = 160, 28
    sheet = Image.new("RGB", (label_w + cell * len(cols), label_h + ch * len(rows)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    problems = []
    for j, c in enumerate(cols):
        d.text((label_w + j * cell + 6, 8), c, fill=(230, 230, 230))
    for i, r in enumerate(rows):
        d.text((6, label_h + i * ch + ch // 2), r, fill=(230, 230, 230))
        for j, c in enumerate(cols):
            x, y = label_w + j * cell, label_h + i * ch
            p = cells.get((r, c))
            if p is None:
                d.rectangle([x, y, x + cell - 1, y + ch - 1], fill=(80, 80, 80))
                d.text((x + 8, y + 8), "缺", fill=(255, 80, 80))
                problems.append(f"{r}/{c}: 缺图")
                continue
            img = Image.open(p).convert("RGB")
            bad = check_frame(img)
            sheet.paste(img.resize((cell, ch)), (x, y))
            if bad:
                d.rectangle([x, y, x + cell - 1, y + ch - 1], outline=(255, 0, 0), width=4)
                problems.append(f"{r}/{c}: {bad}")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return {"rows": rows, "cols": cols, "images": len(cells), "expected": len(rows) * len(cols), "problems": problems}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cell", type=int, default=480)
    a = ap.parse_args(argv)
    r = build(a.folder, a.out, a.cell)
    print(f"行 {len(r['rows'])} × 列 {len(r['cols'])}，图 {r['images']}/{r['expected']}")
    for p in r["problems"]:
        print("问题:", p)
    return 1 if r["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
