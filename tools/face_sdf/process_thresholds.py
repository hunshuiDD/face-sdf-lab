"""Fit monotonic angular fields, clean small components outside a protected nose/mouth region."""
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw

root=Path(__file__).resolve().parent
out=root/"PublicHead"
cycles="--cycles" in sys.argv
tag="cycles_" if cycles else ""
data=np.load(out/("cycles_visibility.npz" if cycles else "raw_visibility.npz"))
field=data["threshold"]
coverage=data["coverage"]
protect=data["protection"]
if "--protect" in sys.argv:
    protect=np.asarray(Image.open(sys.argv[sys.argv.index("--protect")+1]).convert("L"))>0
    assert protect.shape==coverage.shape
    protect &= coverage
size=coverage.shape[0]
angles=data["angles"]
yy,xx=np.nonzero(coverage)

def png16(path,values):
    color=0 if values.ndim==2 else 6
    height,width=values.shape[:2]
    a=np.ascontiguousarray(values.astype(">u2")).view(np.uint8).reshape(height,-1)
    raw=b"".join(b"\0"+row.tobytes() for row in a)
    def chunk(kind,body):
        return struct.pack(">I",len(body))+kind+body+struct.pack(">I",zlib.crc32(kind+body)&0xffffffff)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,16,color,0,0,0))
                     +chunk(b"IDAT",zlib.compress(raw,6))+chunk(b"IEND",b""))

def small_components(mask,limit):
    """Four-connected run-length labeling. Return tiny components wholly inside the UV domain."""
    parent=[]; rows=[]; areas=[];protected=[];edge=[]
    domain_inner=coverage.copy()
    domain_inner[1:] &= coverage[:-1]
    domain_inner[:-1] &= coverage[1:]
    domain_inner[:,1:] &= coverage[:,:-1]
    domain_inner[:,:-1] &= coverage[:,1:]
    def find(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]
            i=parent[i]
        return i
    previous=[]
    for y,row in enumerate(mask):
        delta=np.diff(np.r_[False,row,False].astype(np.int8))
        starts=np.flatnonzero(delta==1); stops=np.flatnonzero(delta==-1)
        current=[]
        for left,right in zip(starts,stops):
            i=len(parent)
            parent.append(i); areas.append(int(right-left)); rows.append((y,int(left),int(right)))
            protected.append(bool(protect[y,left:right].any()))
            edge.append(bool((~domain_inner[y,left:right]).any()))
            current.append(i)
            for old in previous:
                _,a,b=rows[old]
                if b<=left: continue
                if a>=right: break
                ra,rb=find(i),find(old)
                if ra!=rb: parent[rb]=ra
        previous=current
    totals={}; forbidden=set()
    for i in range(len(parent)):
        group=find(i)
        totals[group]=totals.get(group,0)+areas[i]
        if protected[i] or edge[i]: forbidden.add(group)
    output=np.zeros_like(mask)
    groups={group for group,area in totals.items() if area<=limit and group not in forbidden}
    for i,(y,a,b) in enumerate(rows):
        if find(i) in groups: output[y,a:b]=True
    return output,len(groups)

stats={}
variants={"raw":field.copy()}
for name,ratio,window in [("light",.00005,3),("medium",.0002,3),("strong",.0005,5)]:
    limit=max(1,round(coverage.sum()*ratio))
    lit=[]
    components=0
    for angle in angles:
        mask=(field>angle/180)&coverage
        remove,n=small_components(mask,limit)
        fill,m=small_components((~mask)&coverage,limit)
        mask=(mask & ~remove)|fill
        lit.append(mask[yy,xx])
        components+=n+m
    lit=np.array(lit)
    costs=lit.sum(0).astype(np.int16)
    bestcost=costs.copy(); best=np.zeros(len(xx),np.int16)
    for k in range(1,len(angles)):
        costs+=1-2*lit[k-1].astype(np.int16)
        take=costs<bestcost
        best[take]=k
        bestcost[take]=costs[take]
    clean=field.copy()
    clean[yy,xx]=np.clip((best-.5)/(len(angles)-1),0,1)
    padded=np.pad(clean,window//2,mode="edge")
    median=np.median(np.lib.stride_tricks.sliding_window_view(padded,(window,window)),axis=(-1,-2))
    local=np.where(np.abs(median-clean)<.07,median,clean)
    clean=np.where(coverage&~protect,local,field)
    variants[name]=clean
    stats[name]=dict(component_limit_pixels=limit,filter_window=window,small_components_changed=components,
        altered_covered_pixels=int(((clean!=field)&coverage).sum()),
        max_changed_angle_degrees=float(np.max(np.abs(clean-field))*180),
        protected_changed_pixels=int((clean[protect]!=field[protect]).sum()))
    assert np.array_equal(clean[protect],field[protect])
files={}
for name,values in variants.items():
    gray=np.rint(values*65535).astype(np.uint16)
    rgba=np.stack((gray[:,::-1],gray,coverage.astype(np.uint16)*65535,
                   np.full_like(gray,65535)),axis=-1)
    prefix=out/("T_PublicHead_"+tag+name)
    png16(prefix.with_name(prefix.name+"_gray16.png"),gray)
    png16(prefix.with_name(prefix.name+"_project_RGBA16.png"),rgba)
    Image.fromarray(np.rint(values*255).astype(np.uint8)).save(prefix.with_name(prefix.name+"_G_preview.png"))
    files[name]=dict(gray=prefix.name+"_gray16.png",project=prefix.name+"_project_RGBA16.png",
        sha256=hashlib.sha256(prefix.with_name(prefix.name+"_project_RGBA16.png").read_bytes()).hexdigest())
Image.fromarray(protect.astype(np.uint8)*255).save(out/(tag+"Protect_NoseMouth.png"))
pos=data["position"]
front=coverage&(pos[...,1]<-.05)&(pos[...,2]>.075)&(pos[...,2]<.30)
fit_errors=data["fit_errors"]
cover_indices=data["pixel_indices"]
stats["fit_front_disagreement"]=float(fit_errors[front.flat[cover_indices]].sum()/(front.sum()*len(angles)))
stats["variants"]=files
stats["protect_world_bounds"]=json.loads((out/("cycles_fit.json" if cycles else "bake.json")).read_text())["protected_world_bounds"]
if "--protect" in sys.argv:
    stats["protect_mask_override"]=str(Path(sys.argv[sys.argv.index("--protect")+1]).resolve())
(out/(tag+"cleanup.json")).write_text(json.dumps(stats,indent=2),encoding="utf8")
np.savez_compressed(out/(tag+"threshold_variants.npz"),**variants,coverage=coverage,protection=protect)
# The diagnostic front raster uses source world geometry and a fixed orthographic camera.
image=Image.new("RGB",(1024,600),(29,33,40))
draw=ImageDraw.Draw(image)
for i,(name,values) in enumerate(variants.items()):
    zmin,zmax=.04,.333
    mask=np.full((500,250),-np.inf)
    display=np.zeros((500,250),np.uint8)
    px=np.clip(np.rint(125+pos[...,0]*850).astype(int),0,249)
    py=np.clip(np.rint(475-(pos[...,2]-zmin)*1500).astype(int),0,499)
    selected=np.flatnonzero(front)
    for index in sorted(selected,key=lambda k:pos.reshape(-1,3)[k,1],reverse=True):
        y,x=divmod(int(index),size)
        iy,ix=py[y,x],px[y,x]
        display[iy,ix]=round(values[y,x]*255)
    tile=Image.fromarray(display)
    image.paste(tile,(i*256,38))
    draw.text((i*256+8,12),name+" | angular threshold",fill="white")
image.save(out/(tag+"threshold_front_diagnostic.png"))
print(json.dumps({k:v for k,v in stats.items() if k!="variants"},indent=2))
