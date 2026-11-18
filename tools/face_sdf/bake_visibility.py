"""Bake actual directional self visibility into the mesh's unchanged UV coordinates."""
import bpy
import hashlib
import json
import math
import sys
import time
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

root=Path(__file__).resolve().parent
output=root/"PublicHead"
output.mkdir(exist_ok=True)
resolution=int(sys.argv[sys.argv.index("--")+1]) if "--" in sys.argv else 1024
start=time.perf_counter()
data=np.load(root/"inputs/head_geometry.npz")
vertices,triangles,uv,normals=[data[k] for k in ("vertices","triangles","uv","normals")]
assert np.isfinite(vertices).all() and np.isfinite(uv).all() and np.isfinite(normals).all()
assert uv.min()>=-1e-6 and uv.max()<=1+1e-6,"UV coordinates must lie in 0..1"
size=resolution
position=np.zeros((size,size,3),np.float64)
normal=np.zeros_like(position)
coverage=np.zeros((size,size),bool)
overlap=np.zeros((size,size),np.uint8)
for ids,texcoords,ns in zip(triangles,uv,normals):
    screen=texcoords*np.array([size,-size])+np.array([-.5,size-.5])
    minimum=np.maximum(np.ceil(screen.min(0)).astype(int),0)
    maximum=np.minimum(np.floor(screen.max(0)).astype(int),size-1)
    if np.any(minimum>maximum): continue
    a,b,c=screen
    determinant=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    if abs(determinant)<1e-12: continue
    yy,xx=np.mgrid[minimum[1]:maximum[1]+1,minimum[0]:maximum[0]+1]
    w0=((b[1]-c[1])*(xx-c[0])+(c[0]-b[0])*(yy-c[1]))/determinant
    w1=((c[1]-a[1])*(xx-c[0])+(a[0]-c[0])*(yy-c[1]))/determinant
    w2=1-w0-w1
    inside=(w0>1e-8)&(w1>1e-8)&(w2>1e-8)
    y,x=yy[inside],xx[inside]
    bary=np.stack((w0[inside],w1[inside],w2[inside]),axis=1)
    position[y,x]=bary@vertices[ids]
    normal[y,x]=bary@ns
    coverage[y,x]=True
    overlap[y,x]+=1
assert not np.any(overlap>1),"Overlapping triangle interiors are ambiguous"
normal/=np.maximum(np.linalg.norm(normal,axis=-1,keepdims=True),1e-12)
indices=np.flatnonzero(coverage)
positions=position.reshape(-1,3)[indices]
ns=normal.reshape(-1,3)[indices]
tree=BVHTree.FromPolygons(vertices.tolist(),triangles.tolist(),all_triangles=True)
offset=2e-6
origins=[Vector(p+n*offset) for p,n in zip(positions,ns)]
angles=np.linspace(0,180,33)
lit=np.zeros((len(angles),len(indices)),bool)
counts=[]
for i,angle in enumerate(angles):
    a=math.radians(float(angle))
    direction=Vector((math.sin(a),-math.cos(a),0))
    facing=(ns@np.array(direction))>1e-6
    candidates=np.flatnonzero(facing)
    for j in candidates:
        lit[i,j]=tree.ray_cast(origins[j],direction)[0] is None
    counts.append(dict(angle=float(angle),facing=int(facing.sum()),lit=int(lit[i].sum()),
                       self_shadowed=int(facing.sum()-lit[i].sum())))
    print("BAKE",i+1,len(angles),angle,counts[-1],round(time.perf_counter()-start,2),flush=True)
# A scalar threshold can encode one lit->shadow crossing. Fit that crossing to all raw angles.
# Candidate k predicts lit for samples 0..k-1 and shadow for samples k..N-1.
cost=lit.sum(0).astype(np.int16)
best_cost=cost.copy()
best=np.zeros(len(indices),np.int16)
for k in range(1,len(angles)):
    cost=cost+1-2*lit[k-1].astype(np.int16)
    update=cost<best_cost
    best[update]=k
    best_cost[update]=cost[update]
threshold=np.clip((best-.5)/(len(angles)-1),0,1)
field=np.zeros((size,size),np.float64)
field.flat[indices]=threshold
protect=coverage&(np.abs(position[...,0])<.065)&(position[...,1]<-.085)&(position[...,2]>.075)&(position[...,2]<.19)
front=coverage&(position[...,1]<-.05)&(position[...,2]>.035)&(position[...,2]<.30)
paired=front&coverage[:,::-1]
mirrored=position[:,::-1].copy()
mirrored[...,0]*=-1
errors=np.linalg.norm(position[paired]-mirrored[paired],axis=-1)
six_angles=[0,45,90,-45,-90,135]
six=[]
for angle in six_angles:
    if angle>=0:
        six.append(lit[int(angle/5.625)])
        continue
    a=math.radians(angle)
    direction=Vector((math.sin(a),-math.cos(a),0))
    result=np.zeros(len(indices),bool)
    for j in np.flatnonzero((ns@np.array(direction))>1e-6):
        result[j]=tree.ray_cast(origins[j],direction)[0] is None
    six.append(result)
np.savez_compressed(output/"raw_visibility.npz",lit=np.packbits(lit,axis=1),pixel_indices=indices,
    angles=angles,resolution=np.array(size),threshold=field,coverage=coverage,protection=protect,
    position=position.astype(np.float32),normal=normal.astype(np.float32),fit_errors=best_cost,
    six_angles=six_angles,six_visibility=np.array(six))
report=dict(method="directional BVH ray tracing from UV texel surface, smooth-normal facing, self visibility",
    blender=bpy.app.version_string,source="inputs/head_geometry.npz",
    source_sha256=hashlib.sha256((root/"inputs/head_geometry.npz").read_bytes()).hexdigest(),
    resolution=size,covered_pixels=int(coverage.sum()),overlap_interior_pixels=int((overlap>1).sum()),
    ray_origin_normal_offset_m=offset,angles=counts,protected_pixels=int(protect.sum()),
    protected_world_bounds=dict(abs_x_max=.065,y_max=-.085,z_min=.075,z_max=.19),
    front_uv_mirror_pair_fraction=float(paired.sum()/max(1,front.sum())),
    front_uv_mirror_geometry_error_m_max=float(errors.max()) if len(errors) else None,
    scalar_fit_mean_disagreement=float(best_cost.sum()/(len(angles)*len(indices))),
    texels_with_nonmonotonic_raw_lighting=int((np.diff(lit.astype(np.int8),axis=0)>0).any(0).sum()),
    seconds=time.perf_counter()-start)
(output/"bake.json").write_text(json.dumps(report,indent=2),encoding="utf8")
print("DONE",json.dumps({k:report[k] for k in ("covered_pixels","seconds","scalar_fit_mean_disagreement")}),flush=True)
