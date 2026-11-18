"""Run the complete sample and preserve each command's real exit status."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("--blender", default=os.environ.get("BLENDER_EXE", "blender"))
args=parser.parse_args()
root=Path(__file__).resolve().parent
if not (root / "inputs" / "PublicHead.blend").is_file():
    parser.error("Missing inputs/PublicHead.blend. Follow the extraction steps in the repository README.")
steps=[
    ("blender","bake_visibility.py",["1024"]),
    ("python","process_thresholds.py",[]),
    ("blender","bake_cycles.py",["1024"]),
    ("python","fit_cycles.py",[]),
    ("python","process_thresholds.py",["--cycles"]),
    ("blender","render_evidence.py",[]),
    ("blender","render_evidence.py",["--baked-direct"]),
    ("python","verify_outputs.py",[])]
receipt=[]
for number,(kind,script,options) in enumerate(steps,1):
    command=[sys.executable,str(root/script),*options]
    if kind=="blender":
        command=[args.blender,"-b","--factory-startup","--disable-autoexec","-t","2",
                 "--python-exit-code","7","--python",str(root/script),"--",*options]
    start=time.perf_counter()
    run=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
    log=root/f"pipeline_{number:02d}_{Path(script).stem}.log"
    log.write_bytes(run.stdout)
    receipt.append(dict(command=command,exit_code=run.returncode,seconds=time.perf_counter()-start,log=log.name))
    (root/"pipeline_receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf8")
    print(number,script,run.returncode,round(receipt[-1]["seconds"],2),flush=True)
    if run.returncode: raise SystemExit(run.returncode)
