"""UE csvprofile 结果统计与 A/B 对比（P0-4 / D3-3 / M）。

采集（在 UE 控制台）：
    csvprofile start   → 录 60 秒 →   csvprofile stop
CSV 默认写到 <Project>/Saved/Profiling/CSV/。
支持 UE 5.8.3 的 EVENTS 首列、捕获末尾扩展表头与变长行。
事件文字不参与数值计算，较早帧未定义的统计列填 NaN。

用法：
    python -I tools/gpu_csv_report.py run.csv                     # 单份统计
    python -I tools/gpu_csv_report.py base.csv --compare new.csv  # A/B，差值 < 2% 记为"测不出"
可选 --columns 用逗号列出要看的列（支持前缀 GPU/ 这样的通配：写 GPU/*）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

DEFAULT_COLUMNS = ["FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "GPU/*"]
NOISE = 0.02


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def load(path: Path) -> dict[str, np.ndarray]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        raise ValueError(f"{path} 是空文件")
    # UE can add counters during capture and writes the complete header at the end.
    header_rows = [i for i, row in enumerate(rows) if row and row[0].strip() == rows[0][0].strip()
                   and "FrameTime" in row]
    header = [h.strip() for h in rows[header_rows[-1] if header_rows else 0]]
    data = []
    for r in rows[1:]:
        if not r or r[0].strip().startswith("[") or r == header:
            break
        values = r[1:] if header[0] == "EVENTS" else r
        if not any(_is_number(x) for x in values):
            break
        padded = r[:len(header)] + [""] * max(0, len(header) - len(r))
        data.append([float(x) if _is_number(x) else np.nan for x in padded])
    if not data:
        raise ValueError(f"{path} 没有数值行")
    arr = np.array(data, dtype=np.float64)
    return {h: arr[:, i] for i, h in enumerate(header) if i < arr.shape[1]}


def select(cols: dict[str, np.ndarray], patterns: list[str]) -> list[str]:
    out = []
    for p in patterns:
        if p.endswith("*"):
            out += sorted(c for c in cols if c.startswith(p[:-1]) and c not in out)
        elif p in cols and p not in out:
            out.append(p)
    return out


def stats(v: np.ndarray) -> dict:
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0}
    return {"n": int(v.size), "mean": float(v.mean()), "p50": float(np.percentile(v, 50)),
            "p95": float(np.percentile(v, 95)), "p99": float(np.percentile(v, 99))}


def report(path: Path, patterns: list[str]) -> dict:
    cols = load(path)
    return {c: stats(cols[c]) for c in select(cols, patterns)}


def compare(a: dict, b: dict) -> dict:
    out = {}
    for c in a:
        if c not in b or a[c].get("n", 0) == 0 or b[c].get("n", 0) == 0:
            continue
        base, new = a[c]["p50"], b[c]["p50"]
        rel = (new - base) / base if base else float("nan")
        verdict = "测不出" if abs(rel) < NOISE else ("变慢" if rel > 0 else "变快")
        out[c] = {"base_p50": base, "new_p50": new, "delta_ms": new - base, "delta_pct": rel * 100, "verdict": verdict}
    return out


def _table(rep: dict) -> str:
    lines = ["| 列 | 样本 | 均值 ms | P50 | P95 | P99 |", "|---|---|---|---|---|---|"]
    for c, s in rep.items():
        if s.get("n"):
            lines.append(f"| {c} | {s['n']} | {s['mean']:.3f} | {s['p50']:.3f} | {s['p95']:.3f} | {s['p99']:.3f} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", type=Path)
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--columns", default=",".join(DEFAULT_COLUMNS))
    ap.add_argument("--json", type=Path, help="把结果另存为 JSON")
    a = ap.parse_args(argv)
    pats = [p.strip() for p in a.columns.split(",") if p.strip()]
    base = report(a.csv, pats)
    result = {"base": base}
    print(f"## {a.csv.name}\n\n{_table(base)}\n")
    if a.compare:
        new = report(a.compare, pats)
        cmp_ = compare(base, new)
        result.update({"new": new, "compare": cmp_})
        print(f"## {a.compare.name}\n\n{_table(new)}\n")
        print("## A/B（按 P50，|差值| < 2% 记为测不出）\n")
        print("| 列 | 基线 P50 | 新 P50 | 差值 ms | 差值 % | 结论 |\n|---|---|---|---|---|---|")
        for c, r in cmp_.items():
            print(f"| {c} | {r['base_p50']:.3f} | {r['new_p50']:.3f} | {r['delta_ms']:+.3f} | {r['delta_pct']:+.1f}% | {r['verdict']} |")
    if a.json:
        a.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
