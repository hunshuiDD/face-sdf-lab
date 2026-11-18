import json
import os
import runpy
import traceback
from pathlib import Path
import unreal as u

try:
    runpy.run_path(str(Path(__file__).resolve().parents[1]/"FaceTemporal/capture.py"))
except Exception:
    out=Path(os.environ["FACE_TEMPORAL_OUT"])
    (out/"run.json").write_text(json.dumps({"status":"FAILED","error":traceback.format_exc()}),encoding="utf8")
    world=u.find_object(None,json.loads((out/"case.json").read_text())["world"])
    u.SystemLibrary.execute_console_command(world,"quit")
