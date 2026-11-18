"""Measure the same facial region against each trajectory's 4x viewport reference."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parents[3]/"tools"))
import flicker_metric as fm

# Fixed before comparison, based on the first real image. Includes eye socket,
# nose bridge, nostril and lip boundary; excludes the outer head silhouette.
roi=(126,145,281,323)
def read(case):
    p=root/"runs"/case
    report=json.loads((p/"run.json").read_text())
    assert report["status"]=="COMPLETE"
    imgs=[]
    hashes=[]
    for i in range(32):
        f=p/f"frame_{i:03d}.png"
        hashes.append(hashlib.sha256(f.read_bytes()).hexdigest())
        with Image.open(f) as im:
            image=im.convert("RGB")
            if image.width>384:image=image.resize((384,384),Image.Resampling.BOX)
            imgs.append(np.asarray(image,dtype=np.uint8))
    assert len(set(hashes))==32
    return report,imgs,hashes
def luma(frames,region):
    x,y,X,Y=region
    return [(im[y:Y,x:X].astype(np.float64)/255)@fm.LUMA for im in frames]
def measurement(frames,ref,region):
    r=fm.compute(luma(frames,region),luma(ref,region))
    return {k:v for k,v in r.items() if k not in ("mask","heatmap")},r["heatmap"]
summary={"face_xyxy":roi,"unit":"weighted 8-bit display RGB / 255","by_softness":{}}
hashes={}
heats={}
for label in ("hard","production"):
    baseline,ref,hashes[label+"_ref4"]=read(label+"_ref4")
    result={}
    frames={}
    for tag in ("off","on","tsr_off","tsr_on","tsr_repeat"):
        report,imgs,hashes[label+"_"+tag]=read(label+"_"+tag)
        a=[r["pov_camera_cm"] for r in report["frames"]]
        b=[r["pov_camera_cm"] for r in baseline["frames"]]
        drift=float(np.max(np.abs(np.array(a)-b)))
        assert drift<1e-5
        result[tag]={"max_camera_diff_cm":drift}
        frames[tag]=imgs
        for title,region in [("face",roi),("full",(0,0,384,384))]:
            result[tag][title],heat=measurement(imgs,ref,region)
            if title=="face":heats[(label,tag)]=heat
    for tag_a,tag_b in (("off","on"),("tsr_off","tsr_on"),("tsr_on","tsr_repeat")):
        result[tag_a+"_to_"+tag_b]={k:100*(1-result[tag_b][k]["flicker"]/result[tag_a][k]["flicker"]) for k in ("face","full")}
    result["repeat_identical_png"]=sum(x==y for x,y in zip(hashes[label+"_tsr_on"],hashes[label+"_tsr_repeat"]))
    result["repeat_rgb_mae_255"]=float(np.mean([np.abs(a.astype(float)-b).mean() for a,b in zip(frames["tsr_on"],frames["tsr_repeat"])]))
    summary["by_softness"][label]=result
    print(label,result["off_to_on"],result["tsr_off_to_tsr_on"],result["tsr_on_to_tsr_repeat"],flush=True)
out=root/"evidence";out.mkdir(exist_ok=True)
for label in ("hard","production"):
    # Identical heat scale within each paired comparison.
    for group in [("off","on"),("tsr_off","tsr_on")]:
        vmax=max(float(heats[label,tag].max()) for tag in group)
        for tag in group:fm.save_heatmap(heats[label,tag],out/(label+"_"+tag+"_heat.png"),vmax)
(out/"metrics.json").write_text(json.dumps(summary,indent=2),encoding="utf8")
(out/"input_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf8")
with Image.open(root/"runs/hard_off/frame_015.png") as im:
    region=im.convert("RGB");ImageDraw.Draw(region).rectangle(roi,outline="#50ffe0",width=2)
    region.save(out/"face_roi.png")
