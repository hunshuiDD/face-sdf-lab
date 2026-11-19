"""UE game thread sets the MID; a separate tasklist observer runs outside the render loop."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import unreal as u

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root.parents[2] / "python"))
from gpu_guard import check
from tsr_width import apply_face_width

out = Path(os.environ["FACE_PERF_OUT"])
world = u.find_object(None, "/Game/FaceProject/L_PublicFace.L_PublicFace")
def actor(cls):
    value, = u.GameplayStatics.get_all_actors_of_class(world, cls)
    return value
head = actor(u.load_class(None, "/Script/FaceKeyLight.FaceProjectActor"))
cam = actor(u.CameraActor)
light = actor(u.DirectionalLight)
u.GameplayStatics.get_player_controller(world, 0).set_view_target_with_blend(cam, 0)
light.set_actor_rotation(u.MathLibrary.make_rot_from_x(u.Vector(-1, 0, 0)), False)
def cmd(s):
    u.SystemLibrary.execute_console_command(world, s)
settings = {"r.AntiAliasingMethod": 4, "r.ScreenPercentage": 100, "r.DynamicRes.OperationMode": 0,
            "sg.AntiAliasingQuality": 3, "r.TSR.History.ScreenPercentage": 200, "r.MotionBlurQuality": 0,
            "r.EyeAdaptationQuality": 0, "r.BloomQuality": 0, "r.VSync": 0, "t.MaxFPS": 0,
            "t.IdleWhenNotForeground": 0, "r.OneFrameThreadLag": 1, "csv.CompressionMode": 0}
for key, value in settings.items():
    cmd(f"{key} {value}")
cmd("stat none")
for key, value in {"SoftDegrees": 3, "CompareEnable": 0, "DebugMode": 0}.items():
    head.face_material.set_scalar_parameter_value(key, value)
jobs = []
for pair in range(1, 4):
    candidates = [("quarter", .25), ("sixteenth", .0625), ("bypass", 0.)]
    for name, cap in candidates[pair-1:] + candidates[:pair-1]:
        order = ("B", "A") if pair == 2 else ("A", "B")
        jobs.extend((f"{name}_{pair}_{side}", cap if side == "B" else 0.) for side in order)
default_csv = Path(u.Paths.convert_relative_path_to_full(u.Paths.profiling_dir())) / "CSV"
log = {"pid": os.getpid(), "engine": u.SystemLibrary.get_engine_version(), "settings": settings,
       "status": "RUNNING", "runs": [], "discarded": [], "default_csv": str(default_csv)}
def save():
    (out / "run.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf8")
stop_event = threading.Event()
checks = []
def watch():
    with (out / "tasklist.jsonl").open("a", encoding="utf8", buffering=1) as f:
        while not stop_event.is_set():
            receipt = check()
            checks.append(receipt)
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
            stop_event.wait(1.)
threading.Thread(target=watch, daemon=True).start()
state = {"i": 0, "phase": "set", "after": time.monotonic() + 14, "attempt": 0, "busy": False}
def snap():
    material = head.face_material
    v = material.get_vector_parameter_value("DirectionToLight")
    pos = u.GameplayStatics.get_player_camera_manager(world, 0).get_camera_location()
    return {"scalars": {k: material.get_scalar_parameter_value(k) for k in ("EnableAA","SoftDegrees","DebugMode","CompareEnable")},
            "light": [v.r,v.g,v.b], "camera": [pos.x,pos.y,pos.z], "mesh": head.static_mesh_component.static_mesh.get_path_name(),
            "cvars": {k: u.SystemLibrary.get_console_variable_float_value(k) for k in settings}}
def finish(status):
    stop_event.set()
    log["status"] = status
    save()
    u.unregister_slate_post_tick_callback(handle)
    cmd("quit")
def tick(dt):
    if state["busy"] or time.monotonic() < state["after"]:
        return
    state["busy"] = True
    try:
        if state["i"] == len(jobs):
            finish("COMPLETE")
            return
        name, cap = jobs[state["i"]]
        if state["phase"] == "set":
            apply_face_width(head.face_material, 1., cap)
            state.update(phase="start", after=time.monotonic()+2)
            return
        if state["phase"] == "start":
            pre = check()
            if not pre["exclusive"]:
                state["after"] = time.monotonic()+3
                return
            before = snap()
            assert before["scalars"] == {"EnableAA":cap,"SoftDegrees":3,"DebugMode":0,"CompareEnable":0}
            assert all(before["cvars"][k] == v for k,v in settings.items())
            assert "SM_PublicHead" in before["mesh"] and abs(before["light"][0]-1) < 1e-5
            proof = out / (name + ".png")
            if not proof.exists():
                cmd(f'Shot filename="{proof.as_posix()}" -nosuffix')
                state["after"] = time.monotonic()+1
                return
            assert proof.read_bytes()[16:24] == bytes.fromhex("0000040000000400")
            csv_path = out / f"{name}_attempt{state['attempt']}.csv"
            # UE concatenates this filename onto its default folder. Point directly at our evidence.
            filename = Path(os.path.relpath(csv_path, default_csv)).as_posix()
            cmd(f'csvprofile STARTFILE="{filename}"')
            cmd("csvprofile START")
            state.update(phase="sample", start=time.monotonic(), wall=time.time(), before=before, pre=pre,
                         offset=len(checks), csv_file=csv_path.name, after=time.monotonic()+0.4)
            return
        if state["phase"] == "sample":
            samples = checks[state["offset"]:]
            bad = any(not c["exclusive"] for c in samples)
            last = samples[-1] if samples else state["pre"]
            bad |= time.time() - last["wall"] > 4
            if not bad and time.monotonic() - state["start"] < 20:
                state["after"] = time.monotonic()+0.1
                return
            cmd("csvprofile STOP")
            elapsed = time.monotonic()-state["start"]
            post = check()
            after = snap()
            record = dict(name=name, cap=cap, pre=state["pre"], post=post, seconds=elapsed, before=state["before"],
                          after=after, sample_checks=len(samples), csv=state["csv_file"], start_epoch=state["wall"])
            if bad or not post["exclusive"]:
                log["discarded"].append(record)
                state["attempt"] += 1
            else:
                assert after == state["before"] and len(samples) >= 8
                log["runs"].append(record)
                state["i"] += 1
            save()
            state.update(phase="set", after=time.monotonic()+2)
    except Exception:
        log["error"] = traceback.format_exc()
        finish("FAILED")
    finally:
        state["busy"] = False
save()
handle = u.register_slate_post_tick_callback(tick)
