"""Launch a paired whole-frame GPU test on Windows once other UE processes exit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from gpu_guard import check


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory for CSVs, tasklist records and viewport proofs.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = args.output.resolve()
    project = Path(os.environ.get("TA_FACE_HOST", root.parents[2] / "host")).resolve() / "FaceProject.uproject"
    if not project.is_file():
        parser.error(f"Missing prepared CC0 host: {project}")
    out.mkdir(parents=True, exist_ok=False)
    clear = 0
    with (out / "preflight.jsonl").open("w", encoding="utf8", buffering=1) as preflight:
        while clear < 2:
            sample = check()
            preflight.write(json.dumps(sample, ensure_ascii=False) + "\n")
            clear = clear + 1 if sample["returncode"] == 0 and not sample["pids"] and sample["raw"] else 0
            if clear < 2:
                time.sleep(7)
    entry = root / "gpu_entry.py"
    env = {**os.environ, "FACE_PERF_OUT": str(out), "FACE_PERF_ENTRY": str(entry)}
    cmd = [os.environ.get("UE_EDITOR_CMD", "UnrealEditor-Cmd.exe"), str(project),
           "/Game/FaceProject/L_PublicFace", "-game", "-RenderOffscreen", "-ForceRes", "-dx12", "-sm6",
           "-NoSplash", "-nosound", "-NoP4", "-Unattended", "-ResX=1024", "-ResY=1024",
           f"-UserDir={(out / 'runtime').as_posix()}", f"-abslog={out / 'ue.log'}",
           "-ExecCmds=py __import__('runpy').run_path(__import__('os').environ['FACE_PERF_ENTRY'])"]
    (out / "command.json").write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf8")
    with (out / "stdout.log").open("wb") as stream:
        subprocess.run(cmd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=2100, check=True)
    receipt = json.loads((out / "run.json").read_text(encoding="utf8"))
    if receipt["status"] != "COMPLETE":
        raise RuntimeError(receipt.get("error", receipt["status"]))


if __name__ == "__main__":
    main()
