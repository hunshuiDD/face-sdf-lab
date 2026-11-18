"""Compare each actual outline path against its width-matched supersampled reference."""
from pathlib import Path
import hashlib
import json
import os
import sys
import numpy as np
from PIL import Image,ImageDraw,ImageFont

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parents[3]/"tools"))
import flicker_metric as fm

def read(path,tag):
    p=root/"runs"/(path+"_"+tag)
    if (p.with_name(p.name+"_warm")/"run.json").exists():
        p=p.with_name(p.name+"_warm")
    run=json.loads((p/"run.json").read_text())
    assert run["status"]=="COMPLETE" and len(run["frames"])==32
    sequence=[]
    for i in range(32):
        with Image.open(p/f"frame_{i:03d}.png") as file:
            im=file.convert("RGB")
            if im.width!=384:im=im.resize((384,384),Image.Resampling.BOX)
            sequence.append(np.array(im))
    return np.asarray(sequence),np.asarray([f["pov_camera_cm"] for f in run["frames"]])
def ink(seq):
    rgb=seq.astype(np.float32)/255.
    # Diagnostic magenta rejects the skin colors and measures fractional
    # color at the filtered boundary in each path's own display space.
    return np.maximum(0.,np.minimum(rgb[:,:,:,0],rgb[:,:,:,2])-rgb[:,:,:,1])
summary={}
img=Image.new("RGB",(1152,848),"#14212a");d=ImageDraw.Draw(img);font=ImageFont.truetype(os.environ.get("FACE_REVIEW_FONT", "msyh.ttc"), 22)
out=root/"evidence";out.mkdir(exist_ok=True)
blank,track=read("none","off")
assert ink(blank).max()<.15
for j,(method,title) in enumerate([("shell","反面壳 · 法线外扩"),("before","模板描边 · TSR 前"),("after","模板描边 · TSR 后")]):
    ref,camera=read(method,"ref4")
    assert np.max(np.abs(camera-track))<1e-5
    vref=ink(ref)
    if "preview" in sys.argv:
        ref=ref[1:];vref=vref[1:]
    assert np.min((vref>.15).sum(axis=(1,2)))>100
    ref_counts=(vref>.15).sum(axis=(1,2))
    summary[method]={"reference_ink_pixels_median":float(np.median(ref_counts))}
    for k,(tag,subtitle) in enumerate([("off","引擎 AA 关闭"),("tsr","TSR 开启")]):
        frames,camera=read(method,tag)
        assert np.max(np.abs(camera-track))<1e-5
        if "preview" in sys.argv: frames=frames[1:]
        v=ink(frames)
        counts=(v>.15).sum(axis=(1,2))
        assert counts.min()>100,(method,tag,counts)
        measured=fm.compute(list(v),list(vref))
        summary[method][tag]={key:val for key,val in measured.items() if key not in ("heatmap","mask")}
        summary[method][tag].update(ink_pixel_range=[int(counts.min()),int(counts.max())],
                                    ink_count_vs_reference=float(np.median(counts/ref_counts)))
        fm.save_heatmap(measured["heatmap"],out/(method+"_"+tag+"_heat.png"),.3)
        img.paste(Image.fromarray(frames[14 if "preview" in sys.argv else 15]),(384*j,424*k))
        d.text((384*j+10,424*k+389),title+"  /  "+subtitle,fill="white",font=font)
    summary[method]["tsr_change_pct"]=100*(summary[method]["tsr"]["flicker"]/summary[method]["off"]["flicker"]-1)
score={}
for label in ("hard","production"):
    path="linear_"+label
    ref,camera=read(path,"ref4")
    x,y,X,Y=(126,145,281,323)
    cropped=lambda sequence:[(f[y:Y,x:X].astype(float)/255)@fm.LUMA for f in sequence]
    score[label]={}
    for tag in ("off","on","tsr_off","tsr_on"):
        sequence,cam=read(path,tag)
        assert np.max(np.abs(cam-camera))<1e-5
        r=fm.compute(cropped(sequence),cropped(ref))
        score[label][tag]={k:v for k,v in r.items() if k not in ("mask","heatmap")}
    for a,b in (("off","on"),("tsr_off","tsr_on")):
        score[label][a+"_to_"+b]=100*(1-score[label][b]["flicker"]/score[label][a]["flicker"])
img.save(out/"描边实帧对照.jpg",quality=94)
(out/"metrics.json").write_text(json.dumps({"outline":summary,"linear_kernel":score},indent=2),encoding="utf8")
print({k:[v["off"]["flicker"],v["tsr"]["flicker"]] for k,v in summary.items()})
print({k:[v["off_to_on"],v["tsr_off_to_tsr_on"]] for k,v in score.items()})
