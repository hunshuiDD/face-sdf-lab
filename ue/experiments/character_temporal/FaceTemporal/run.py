"""Fresh UE game process per viewport case. Preserve existing validated receipts on retry."""
import json
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image

root=Path(__file__).resolve().parent
exe=os.environ.get("UE_EDITOR_CMD", "UnrealEditor-Cmd.exe")
project=Path(os.environ.get("TA_FACE_HOST",root.parents[2]/"host"))/"FaceProject.uproject"
cases={f"{label}_{tag}":{"soft":soft,"aa":aa,"analytic":analytic,"size":size}
       for label,soft in (("hard",0),("production",3))
       for tag,aa,analytic,size in (("ref4",0,0,1536),("off",0,0,384),("on",0,1,384),
                                   ("tsr_off",4,0,384),("tsr_on",4,1,384),("tsr_repeat",4,1,384))}
def verify(out,cfg):
    r=json.loads((out/"run.json").read_text())
    assert r["status"]=="COMPLETE" and r["case"]==cfg and len(r["frames"])==32,r.get("error")
    for i in range(32):
        with Image.open(out/f"frame_{i:03d}.png") as im:
            assert im.size==(cfg["size"],cfg["size"]),im.size
            im.verify()
for name in sys.argv[1:] or cases:
    cfg=cases[name]
    out=root/"runs"/name
    out.mkdir(exist_ok=True,parents=True)
    if (out/"run.json").exists():verify(out,cfg);continue
    (out/"case.json").write_text(json.dumps(cfg),encoding="utf8")
    size=cfg["size"]
    cmd=[str(exe),str(project),"/Game/FaceProject/L_PublicFace","-game","-RenderOffscreen","-ForceRes","-dx12","-sm6",
         "-NoSplash","-nosound","-NoP4","-Unattended","-UseFixedTimeStep","-FPS=24",f"-ResX={size}",f"-ResY={size}",
         f"-abslog={out/'ue.log'}",f'-ExecCmds=py "{(root / "capture.py").as_posix()}"']
    with (out/"stdout.log").open("wb") as stream:
        run=subprocess.run(cmd,stdout=stream,stderr=subprocess.STDOUT,env={**os.environ,"FACE_TEMPORAL_OUT":str(out)},
                           creationflags=subprocess.CREATE_NO_WINDOW,timeout=195)
    assert run.returncode==0,run.returncode
    verify(out,cfg)
    print(name,"32 viewport PNG",size,flush=True)
