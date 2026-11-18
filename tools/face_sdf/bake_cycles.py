"""Independent Cycles direct-diffuse bake on the same unchanged CC0 head."""
import bpy
import json
import math
import sys
import time
from pathlib import Path
import numpy as np
from mathutils import Vector

root=Path(__file__).resolve().parent
out=root/"PublicHead"
size=int(sys.argv[sys.argv.index("--")+1]) if "--" in sys.argv else 1024
bpy.ops.wm.open_mainfile(filepath=str(root/"inputs/PublicHead.blend"))
head=bpy.data.objects[json.loads((root/"inputs/head_facts.json").read_text())["object"]]
head.animation_data_clear()
bpy.context.view_layer.objects.active=head
head.select_set(True)
scene=bpy.context.scene
scene.render.engine="CYCLES"
scene.cycles.device="CPU"
scene.cycles.samples=4
scene.render.bake.margin=0
scene.render.bake.use_clear=True
scene.render.bake.use_pass_direct=True
scene.render.bake.use_pass_indirect=False
scene.render.bake.use_pass_color=False
scene.world=bpy.data.worlds.new("BlackEnvironment")
scene.world.use_nodes=True
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value=0
head.data.materials.clear()
mat=bpy.data.materials.new("WhiteDiffuse")
mat.use_nodes=True
head.data.materials.append(mat)
nodes=mat.node_tree.nodes
nodes.clear()
diffuse=nodes.new("ShaderNodeBsdfDiffuse")
diffuse.inputs["Color"].default_value=(1,1,1,1)
surface=nodes.new("ShaderNodeOutputMaterial")
mat.node_tree.links.new(diffuse.outputs[0],surface.inputs["Surface"])
image=bpy.data.images.new("DirectBake",size,size,alpha=False,float_buffer=True)
image.colorspace_settings.name="Non-Color"
target=nodes.new("ShaderNodeTexImage")
target.image=image
nodes.active=target
sun_data=bpy.data.lights.new("BakeSun","SUN")
sun_data.energy=1
sun_data.angle=0
sun=bpy.data.objects.new("BakeSun",sun_data)
scene.collection.objects.link(sun)
values=[];rows=[]
start=time.perf_counter()
for angle in np.r_[np.linspace(0,180,33),-45,-90]:
    a=math.radians(float(angle))
    to_light=Vector((math.sin(a),-math.cos(a),0))
    sun.rotation_euler=(-to_light).to_track_quat("-Z","Y").to_euler()
    bpy.context.view_layer.update()
    before=time.perf_counter()
    bpy.ops.object.bake(type="DIFFUSE")
    pixels=np.array(image.pixels[:],np.float32).reshape(size,size,4)[::-1,:,:3]
    direct=pixels.mean(-1)
    values.append(direct)
    rows.append(dict(angle=float(angle),seconds=time.perf_counter()-before,max=float(direct.max())))
    print("CYCLES_BAKE",rows[-1],flush=True)
np.savez_compressed(out/"cycles_direct.npz",direct=np.array(values),angles=np.r_[np.linspace(0,180,33),-45,-90])
(out/"cycles_bake.json").write_text(json.dumps(dict(engine=bpy.app.version_string,device="CPU",samples=4,
    bake="DIFFUSE direct, no color, no indirect, sun angle zero, environment black",
    resolution=size,angles=rows,seconds=time.perf_counter()-start),indent=2),encoding="utf8")
