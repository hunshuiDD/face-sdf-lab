"""Actual DX12 head captures with a per-character F3-driven MID."""
import json
import math
import os
import time
import traceback
from pathlib import Path
import unreal as u

root=Path(os.environ.get("FACE_PROJECT_ROOT",str(Path(__file__).resolve().parents[1])))
out=root/"evidence"
out.mkdir(parents=True, exist_ok=True)
world=u.find_object(None,"/Game/FaceProject/L_PublicFace.L_PublicFace")
if not world:raise RuntimeError("Public head world missing")
actor_class=u.load_class(None,"/Script/FaceKeyLight.FaceProjectActor")
heads=list(u.GameplayStatics.get_all_actors_of_class(world,actor_class))
lights=list(u.GameplayStatics.get_all_actors_of_class(world,u.DirectionalLight))
cameras=list(u.GameplayStatics.get_all_actors_of_class(world,u.CameraActor))
captures=list(u.GameplayStatics.get_all_actors_of_class(world,u.SceneCapture2D))
assert len(heads)==len(lights)==len(cameras)==len(captures)==1
head,light,camera=heads[0],lights[0],cameras[0]
pc=u.GameplayStatics.get_player_controller(world,0)
pc.set_view_target_with_blend(camera,0)
cap=captures[0].get_component_by_class(u.SceneCaptureComponent2D)
target=u.RenderingLibrary.create_render_target2d(world,512,512,u.TextureRenderTargetFormat.RTF_RGBA8)
cap.texture_target=target
report={"status":"RUNNING","engine":u.SystemLibrary.get_engine_version(),"runtime":"uncooked -game DX12 SM6",
        "source":"Blender CC0 GEO-head_stylized + independent 33-angle baked project RGBA16 + personal shader",
        "frames":[],"material_actor_binding":"AFaceProjectActor::Tick -> per-actor MID"}
jobs=[("front",0,1,None),("left045",45,1,None),("left090",90,1,None),("right045",45,-1,None),("right090",90,-1,None),("back_left135",135,1,None),
      ("wipe020",90,1,.2),("wipe050",90,1,.5),("wipe080",90,1,.8)]
state={"tick":0,"index":0,"wait":120,"stage":"set","busy":False}
started=time.monotonic()

def command(text):u.SystemLibrary.execute_console_command(world,text)
def vector(v):return [float(v.x),float(v.y),float(v.z)]
def save():
    (out/"run.json").write_text(json.dumps(report,indent=2),encoding="utf8")
def finish(error=None):
    report.update(status="FAILED" if error else "COMPLETE",error=error,elapsed_seconds=time.monotonic()-started)
    save()
    u.unregister_slate_post_tick_callback(handle)
    command("quit")

def tick(dt):
    if state["busy"]:return
    state["busy"]=True
    try:
        state["tick"]+=1
        if time.monotonic()-started>180:raise RuntimeError("Capture timeout")
        if state["wait"]>0:
            state["wait"]-=1
            return
        if state["index"]==len(jobs):
            # Check source channels after import by drawing the texture to a float target.
            reference=json.loads((root/"source/texture_samples.json").read_text(encoding="utf8"))
            material=head.face_material
            material.set_scalar_parameter_value("DebugMode",2.)
            rt=u.RenderingLibrary.create_render_target2d(world,1024,1024,u.TextureRenderTargetFormat.RTF_RGBA32F)
            u.RenderingLibrary.draw_material_to_render_target(world,rt,material)
            samples=[]
            for sample in reference["samples"]:
                x,y=sample["xy"]
                color=u.RenderingLibrary.read_render_target_raw_pixel(world,rt,x,y)
                actual=[color.r,color.g,color.b]
                error=max(abs(a-b) for a,b in zip(actual,sample["expected"][:3]))
                samples.append({**sample,"actual_rgb":actual,"max_error":error})
            report["texture_samples"]=samples
            if max(row["max_error"] for row in samples)>.002:raise RuntimeError("Texture precision mismatch")
            finish()
            return
        name,angle,side,wipe=jobs[state["index"]]
        if state["stage"]=="set":
            phi=math.radians(angle)
            desired=[-side*math.sin(phi),-math.cos(phi),0.]
            toward=u.Vector(-desired[0],-desired[1],-desired[2])
            light.set_actor_rotation(u.MathLibrary.make_rot_from_x(toward),False)
            state["desired"]=desired
            material=head.face_material
            material.set_scalar_parameter_value("CompareEnable",float(wipe is not None))
            material.set_scalar_parameter_value("WipeX",wipe if wipe is not None else .5)
            state["wait"]=45
            state["stage"]="capture"
        else:
            material=head.face_material
            assert material is not None
            mid_direction=material.get_vector_parameter_value("DirectionToLight")
            mid_vector=[mid_direction.r,mid_direction.g,mid_direction.b]
            actual=vector(head.solver.direction_to_light)
            error=max(abs(a-b) for a,b in zip(actual,state["desired"]))
            if error>1e-4:raise RuntimeError("Solver direction mismatch "+str(actual)+" desired="+str(state["desired"]))
            if max(abs(a-b) for a,b in zip(actual,mid_vector))>1e-5:raise RuntimeError("MID parameter mismatch")
            material.set_scalar_parameter_value("DebugMode",0.)
            cap.capture_scene()
            destination=out/(name+".png")
            u.RenderingLibrary.export_render_target(world,target,str(out),name)
            unextended=out/name
            if unextended.exists():unextended.replace(destination)
            command('Shot filename="'+str((out/(name+"_viewport.png")).as_posix())+'" -nosuffix')
            report["frames"].append({"name":name,"angle":angle,"side":side,"selected":head.solver.selected.get_path_name(),
                "expected_direction":state["desired"],"solver_direction":actual,"direction_max_error":error,
                "world_forward":[getattr(material.get_vector_parameter_value("FaceForward"),c) for c in ("r","g","b")],
                "world_right":[getattr(material.get_vector_parameter_value("FaceRight"),c) for c in ("r","g","b")],
                "material":material.get_path_name(),"file":destination.name,"tick":state["tick"]})
            wipe_actual=material.get_scalar_parameter_value("WipeX")
            compare_actual=material.get_scalar_parameter_value("CompareEnable")
            if wipe is not None and abs(wipe_actual-wipe)>1e-5:raise RuntimeError("Wipe parameter mismatch")
            report["frames"][-1].update(mid_direction=mid_vector,wipe=wipe,
                wipe_readback=wipe_actual,compare_readback=compare_actual)
            save()
            state.update(index=state["index"]+1,stage="set",wait=12)
    except Exception:finish(traceback.format_exc())
    finally:state["busy"]=False

for cmd in ("r.SetRes 768x768w","r.VSync 0","t.MaxFPS 90","r.AntiAliasingMethod 0","r.MotionBlurQuality 0",
            "r.EyeAdaptationQuality 0","r.BloomQuality 0","r.TonemapperFilm 0","r.TonemapperGamma 2.2","t.IdleWhenNotForeground 0"):
    command(cmd)
save()
handle=u.register_slate_post_tick_callback(tick)
