"""Build angular thresholds from actual Cycles bake samples, retaining independent BVH agreement."""
import json
from pathlib import Path
import numpy as np

out=Path(__file__).resolve().parent/"PublicHead"
surface=np.load(out/"raw_visibility.npz")
bake=np.load(out/"cycles_direct.npz")
coverage=surface["coverage"]
indices=surface["pixel_indices"]
values=bake["direct"].reshape(35,-1)[:,indices]
# Values are irradiance / pi. Tiny grazing-angle values are numerical noise.
lit=values[:33]>1e-5
angles=bake["angles"][:33]
cost=lit.sum(0).astype(np.int16)
bestcost=cost.copy();best=np.zeros(len(indices),np.int16)
for k in range(1,len(angles)):
    cost+=1-2*lit[k-1].astype(np.int16)
    update=cost<bestcost
    best[update]=k;bestcost[update]=cost[update]
field=np.zeros(coverage.shape,np.float64)
field.flat[indices]=np.clip((best-.5)/(len(angles)-1),0,1)
position=surface["position"]
protect=coverage&(np.abs(position[...,0])<.065)&(position[...,1]<-.085)&(position[...,2]>.035)&(position[...,2]<.19)
data={k:surface[k] for k in surface.files}
data.update(lit=np.packbits(lit,axis=1),threshold=field,protection=protect,fit_errors=bestcost,
    six_visibility=(values[[0,8,16,33,34,24]]>1e-5))
np.savez_compressed(out/"cycles_visibility.npz",**data)
raw=np.unpackbits(surface["lit"],axis=1)[:,:len(indices)].astype(bool)
front=(position[...,1]<-.05)&(position[...,2]>.035)&(position[...,2]<.30)&coverage
selected=front.flat[indices]
stats=dict(method="Cycles direct diffuse visibility -> least-disagreement monotonic angular threshold",
    threshold_of_direct=1e-5,covered_pixels=len(indices),protected_pixels=int(protect.sum()),
    bvh_agreement_all=float((lit==raw).mean()),bvh_agreement_front=float((lit[:,selected]==raw[:,selected]).mean()),
    scalar_disagreement_all=float(bestcost.sum()/(33*len(indices))),
    scalar_disagreement_front=float(bestcost[selected].sum()/(33*selected.sum())),
    protected_world_bounds=dict(abs_x_max=.065,y_max=-.085,z_min=.035,z_max=.19))
(out/"cycles_fit.json").write_text(json.dumps(stats,indent=2),encoding="utf8")
