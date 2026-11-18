"""Copy the CC0-only host and validate three outline methods with identical camera motion."""
from pathlib import Path
import json
import hashlib
import os
import subprocess
import sys
from PIL import Image

root=Path(__file__).resolve().parent
host=root/"host"
source=Path(os.environ.get("TA_FACE_HOST",root.parents[2]/"host"))
project=host/"FaceOutline.uproject"
exe=os.environ.get("UE_EDITOR_CMD", "UnrealEditor-Cmd.exe")
world="/Game/FaceOutline/L_Outlines"
def init():
    public=source/"Content/FaceProject"
    files=list(public.glob("*.umap"))+list(public.glob("*.uasset"))
    if not files:
        raise FileNotFoundError(f"Prepare the FaceProject host before copying it: {source}")
    plugin=source/"Plugins/FaceKeyLight"
    files += [plugin/"FaceKeyLight.uplugin",*list((plugin/"Binaries/Win64").glob("*.dll")),plugin/"Binaries/Win64/UnrealEditor.modules"]
    for p in files:
        dst=host/p.relative_to(source)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if not dst.exists():dst.write_bytes(p.read_bytes())
        assert hashlib.sha256(dst.read_bytes()).digest()==hashlib.sha256(p.read_bytes()).digest()
    project.write_text(json.dumps({"FileVersion":3,"EngineAssociation":"5.8","Plugins":[
        {"Name":p,"Enabled":True} for p in ("PythonScriptPlugin","EditorScriptingUtilities","FaceKeyLight")]+[{"Name":"AndroidFileServer","Enabled":False}]}),encoding="utf8")
    conf=host/"Config";conf.mkdir(exist_ok=True)
    (conf/"DefaultEngine.ini").write_text("[/Script/Engine.RendererSettings]\nr.CustomDepth=3\nr.RayTracing=False\nr.DefaultFeature.AutoExposure=False\n",encoding="utf8")
def launch(options,out,env=None):
    args=[str(exe),str(project),*options,"-unattended","-nop4","-nosplash","-nosound","-dx12","-sm6",f"-abslog={out/'ue.log'}"]
    with (out/"stdout.log").open("wb") as stream:
        proc=subprocess.run(args,env={**os.environ,**(env or {})},stdout=stream,stderr=subprocess.STDOUT,
                            creationflags=subprocess.CREATE_NO_WINDOW,timeout=210)
    if proc.returncode:raise RuntimeError(f"UE returned {proc.returncode}: {out}")
if "init" in sys.argv:
    init()
if "prepare" in sys.argv:
    launch(["-run=pythonscript","-AllowCommandletRendering",f"-script={root/'prepare.py'}"],root)
    r=json.loads((root/"prepare.json").read_text());assert r["status"]=="SAVED",r
if "capture" in sys.argv:
    for path in ("none","shell","before","after","linear_hard","linear_production"):
        linear=path.startswith("linear")
        modes=(("ref4",0,1536),("off",0,384),("tsr",4,384))
        if linear:modes=(("ref4",0,1536),("off",0,384),("on",0,384),("tsr_off",4,384),("tsr_on",4,384))
        for variant,aa,size in modes:
            case=path+"_"+variant
            if len(sys.argv)>2 and "all" not in sys.argv and case not in sys.argv:continue
            retake="retake" in sys.argv
            out=root/"runs"/(case+"_warm" if retake else case);out.mkdir(parents=True,exist_ok=True)
            level="/Game/FaceOutline/L_LinearFace" if linear else world
            cfg={"world":level+"."+level.split("/")[-1],"soft":0 if path=="linear_hard" else 3,
                 "analytic":int(variant in ("on","tsr_on")) if linear else 1,"aa":aa,"size":size}
            if not linear:cfg["outline"]=path
            if retake:cfg["warm_ticks"]=425
            if not (out/"run.json").exists():
                (out/"case.json").write_text(json.dumps(cfg),encoding="utf8")
                launch([level,"-game","-RenderOffscreen","-ForceRes","-UseFixedTimeStep","-FPS=24",f"-ResX={size}",f"-ResY={size}",
                        f'-ExecCmds=py "{(root / "entry.py").as_posix()}"'],out,{"FACE_TEMPORAL_OUT":str(out)})
            run=json.loads((out/"run.json").read_text());assert run["status"]=="COMPLETE" and run["case"]==cfg,run.get("error")
            assert len(run["frames"])==32
            with Image.open(out/"frame_015.png") as im:assert im.size==(size,size)
            print(case,flush=True)
