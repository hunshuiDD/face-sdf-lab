"""Capture consecutive real game viewport frames along a repeatable subpixel camera move."""
import json
import os
import time
import traceback
from pathlib import Path
import unreal as u

out=Path(os.environ["FACE_TEMPORAL_OUT"])
cfg=json.loads((out/"case.json").read_text())
world_path=cfg.get("world","/Game/FaceProject/L_PublicFace.L_PublicFace")
w=u.find_object(None,world_path)
actors=lambda cls:u.GameplayStatics.get_all_actors_of_class(w,cls)
head,=actors(u.load_class(None,"/Script/FaceKeyLight.FaceProjectActor"))
cam,=actors(u.CameraActor)
light,=actors(u.DirectionalLight)
pc=u.GameplayStatics.get_player_controller(w,0)
pc.set_view_target_with_blend(cam,0)
mid=head.face_material
outline=cfg.get("outline")
if outline:
    shells=[a for a in actors(u.StaticMeshActor) if a.get_actor_label()=="DiagnosticReverseShell"]
    shell,=shells
    shell.set_actor_hidden_in_game(outline!="shell")
    if outline in ("before","after"):
        pp,=actors(u.PostProcessVolume)
        source=u.load_asset("/Game/FaceOutline/M_Stencil"+outline.capitalize())
        assert source
        pp_mid=u.MaterialLibrary.create_dynamic_material_instance(w,source)
        pp_mid.set_scalar_parameter_value("Radius",2*cfg["size"]/384.)
        pp.add_or_update_blendable(pp_mid,1.)
base=cam.get_actor_location()
side=cam.get_actor_right_vector()
mat_params={"CompareEnable":0,"DebugMode":0,"EnableAA":cfg["analytic"],"SoftDegrees":cfg["soft"]}
for key,val in mat_params.items():mid.set_scalar_parameter_value(key,val)
light.set_actor_rotation(u.MathLibrary.make_rot_from_x(u.Vector(-1,0,0)),False)
def cmd(s):u.SystemLibrary.execute_console_command(w,s)
settings={"r.AntiAliasingMethod":cfg["aa"],"r.ScreenPercentage":100,"r.DynamicRes.OperationMode":0,
          "r.MotionBlurQuality":0,"r.VSync":0,"r.BloomQuality":0,"r.EyeAdaptationQuality":0,
          "r.TonemapperGamma":2.2,"r.Tonemapper.Sharpen":0,"r.OneFrameThreadLag":0,"t.IdleWhenNotForeground":0}
for name,v in settings.items():cmd(f"{name} {v}")
cmd("stat none")
def xyz(v):return [v.x,v.y,v.z]
report={"engine":u.SystemLibrary.get_engine_version(),"case":cfg,"frames":[],"status":"RUNNING",
        "head":head.get_path_name(),"mesh":head.static_mesh_component.static_mesh.get_path_name(),"camera":cam.get_path_name(),
        "light":light.get_path_name(),"mid":mid.get_path_name(),"camera_step_cm":.055}
if outline:
    report["outline"]={"method":outline,"shell_hidden":shell.get_editor_property("hidden"),"custom_depth":head.static_mesh_component.render_custom_depth,
                       "stencil":head.static_mesh_component.custom_depth_stencil_value,
                       "pp":pp_mid.get_path_name() if outline in ("before","after") else None}
state={"tick":0,"busy":False}
start=time.monotonic()
def tick(dt):
    if state["busy"]:return
    state["busy"]=True
    try:
        step=state["tick"]-cfg.get("warm_ticks",105)
        state["tick"]+=1
        if time.monotonic()-start>150:raise RuntimeError("viewport capture timed out")
        if step < -32:return
        if step==-32:
            report["cvars"]={name:u.SystemLibrary.get_console_variable_float_value(name) for name in settings}
            assert all(abs(report["cvars"][n]-v)<.0001 for n,v in settings.items()),report["cvars"]
            report["mid_scalars"]={n:mid.get_scalar_parameter_value(n) for n in mat_params}
            assert all(abs(report["mid_scalars"][n]-v)<.0001 for n,v in mat_params.items())
            direction=mid.get_vector_parameter_value("DirectionToLight")
            assert abs(direction.r-1)<1e-4 and abs(direction.g)<1e-4 and abs(direction.b)<1e-4
            report["light_to_surface_opposite_direction"]=[direction.r,direction.g,direction.b]
        if step<32:
            # Move at constant screen-space speed before sample zero. The player
            # camera manager updates on the next tick; record its actual POV.
            loc=base+side*(.055*(step-15.5))
            cam.set_actor_location(loc,False,False)
            if step>=0:
                dst=(out/f"frame_{step:03d}.png").as_posix()
                cmd(f'Shot filename="{dst}" -nosuffix')
                mgr=u.GameplayStatics.get_player_camera_manager(w,0)
                report["frames"].append({"i":step,"tick":state["tick"],"cmd_camera_cm":xyz(loc),
                    "pov_camera_cm":xyz(mgr.get_camera_location()),"dt":dt})
            return
        if len(list(out.glob("frame_*.png")))!=32:return
        report["status"]="COMPLETE"
    except Exception:report.update(status="FAILED",error=traceback.format_exc())
    finally:state["busy"]=False
    (out/"run.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    u.unregister_slate_post_tick_callback(handle)
    cmd("quit")
handle=u.register_slate_post_tick_callback(tick)
