"""Verify the paired CSVs, camera/MID/CVars and exclusive-UE process evidence."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image

out = Path(sys.argv[1])
run = json.loads((out / "run.json").read_text(encoding="utf8"))
guards = [json.loads(line) for line in (out / "tasklist.jsonl").read_text(encoding="utf8").splitlines()]
assert run["status"] == "COMPLETE" and len(run["runs"]) == 18
rows = {}
for record in run["runs"]:
    assert record["pre"]["exclusive"] and record["post"]["exclusive"]
    assert record["pre"]["pids"] == record["post"]["pids"] == [run["pid"]]
    assert record["before"] == record["after"]
    start = record["start_epoch"]
    active = [g for g in guards if start <= g["wall"] <= start + record["seconds"]]
    assert len(active) >= 8 and all(g["exclusive"] for g in active)
    stamps = [start, *[g["wall"] for g in active], start + record["seconds"]]
    assert max(np.diff(stamps)) < 4
    path = out / record["csv"]
    values, frame_time = [], []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        header = next(reader)
        gi, fi = header.index("GPUTime"), header.index("FrameTime")
        for row in reader:
            if not row or row[0].startswith("[") or row[0] == header[0]:
                break
            values.append(float(row[gi]))
            frame_time.append(float(row[fi]))
    seconds = sum(frame_time) / 1000
    assert 19 < seconds < 21 and len(values) > 1000 and min(values) > 0, (seconds,len(values))
    with Image.open(out / (record["name"] + ".png")) as im:
        assert im.size == (1024,1024) and (np.asarray(im.convert("RGB")).max(2) > 16).sum() > 20000
    rows[record["name"]] = dict(p50=float(np.median(values)),p95=float(np.percentile(values,95)),
                                frames=len(values),seconds=seconds, mid=record["cap"],
                                raw_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                                tasklist_checks=len(active),max_check_gap_seconds=max(np.diff(stamps)))
summary = {}
for candidate in ("quarter","sixteenth","bypass"):
    pairs = []
    for pair in range(1,4):
        a,b = (rows[f"{candidate}_{pair}_{side}"]["p50"] for side in ("A","B"))
        pairs.append(dict(a=a,b=b,change_pct=100*(b/a-1)))
    groups = [[p[s] for p in pairs] for s in ("a","b")]
    a,b = map(np.median,groups)
    floor = max(2., *(100*np.ptp(group)/np.median(group) for group in groups))
    diff = 100*(b/a-1)
    signs = {np.sign(p["change_pct"]) for p in pairs}
    summary[candidate] = dict(pairs=pairs, baseline_p50=a, candidate_p50=b, change_pct=diff,
                              noise_floor_pct=floor, resolved=bool(abs(diff)>floor and len(signs)==1))
result = dict(pid=run["pid"], valid_segments=len(rows), discarded=len(run["discarded"]), rows=rows, summary=summary)
(out/"summary.json").write_text(json.dumps(result,indent=2),encoding="utf8")
print(json.dumps(summary,indent=2))
