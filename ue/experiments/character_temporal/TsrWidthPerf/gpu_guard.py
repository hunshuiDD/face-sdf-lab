import csv
import os
import subprocess
import time


def check():
    proc = subprocess.run(["tasklist.exe", "/FI", "IMAGENAME eq UnrealEditor*", "/FO", "CSV", "/NH"],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    output = proc.stdout.decode("mbcs", errors="replace").strip()
    rows = list(csv.reader(output.splitlines()))
    pids = [int(r[1]) for r in rows if len(r) >= 2 and r[0].lower().startswith("unrealeditor")]
    return {"wall": time.time(), "returncode": proc.returncode, "raw": output, "pids": pids,
            "exclusive": proc.returncode == 0 and pids == [os.getpid()]}
