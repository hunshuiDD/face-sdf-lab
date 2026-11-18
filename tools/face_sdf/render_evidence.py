"""Render the unchanged CC0 head under raw visibility and four encoded threshold candidates."""
import bpy
import math
import json
import sys
from pathlib import Path
import numpy as np
from mathutils import Vector

root=Path(__file__).resolve().parent
out=root/"PublicHead"
cycles="--baked-direct" in sys.argv
tag="cycles_" if cycles else ""
renderdir=out/("renders_cycles" if cycles else "renders")
renderdir.mkdir(exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(root/"inputs/PublicHead.blend"))
head=bpy.data.objects[json.loads((root/"inputs/head_facts.json").read_text())["object"]]
head.animation_data_clear()
for p in head.data.polygons: p.use_smooth=True
head.data.materials.clear()
mat=bpy.data.materials.new("PersonalAngularEvidence")
mat.use_nodes=True
head.data.materials.append(mat)
n=mat.node_tree.nodes
n.clear()
uv=n.new("ShaderNodeTexCoord")
tex=n.new("ShaderNodeTexImage")
tex.interpolation="Closest"
mat.node_tree.links.new(uv.outputs["UV"],tex.inputs["Vector"])
sep=n.new("ShaderNodeSeparateColor")
mat.node_tree.links.new(tex.outputs["Color"],sep.inputs[0])
test=n.new("ShaderNodeMath");test.operation="GREATER_THAN"
channel=sep.outputs["Green"]
mat.node_tree.links.new(channel,test.inputs[0])
ramp=n.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color=(.085,.058,.042,1)
ramp.color_ramp.elements[1].color=(.66,.46,.32,1)
mat.node_tree.links.new(test.outputs[0],ramp.inputs[0])
emission=n.new("ShaderNodeEmission")
mat.node_tree.links.new(ramp.outputs[0],emission.inputs["Color"])
output=n.new("ShaderNodeOutputMaterial")
mat.node_tree.links.new(emission.outputs[0],output.inputs["Surface"])
camera_data=bpy.data.cameras.new("EvidenceCamera")
camera=bpy.data.objects.new("EvidenceCamera",camera_data)
bpy.context.scene.collection.objects.link(camera)
camera.location=(0,-1,.145)
camera.rotation_euler=(Vector((0,-.025,.145))-camera.location).to_track_quat("-Z","Y").to_euler()
camera_data.type="ORTHO";camera_data.ortho_scale=.415
scene=bpy.context.scene
scene.camera=camera
scene.render.engine="CYCLES"
scene.cycles.device="CPU"
scene.cycles.samples=1
scene.render.resolution_x=512;scene.render.resolution_y=512;scene.render.resolution_percentage=100
scene.render.film_transparent=True
scene.view_settings.view_transform="Standard"
scene.view_settings.look="None"
scene.view_settings.exposure=0
scene.view_settings.gamma=1
scene.render.image_settings.file_format="PNG"
scene.render.image_settings.color_mode="RGBA"
scene.render.image_settings.color_depth="8"
raw=np.load(out/("cycles_visibility.npz" if cycles else "raw_visibility.npz"))
size=int(raw["resolution"])
six=raw["six_angles"].tolist()
indices=raw["pixel_indices"]
for variant in ["visibility","raw","light","medium","strong"]:
    image=None
    if variant!="visibility":
        image=bpy.data.images.load(str(out/f"T_PublicHead_{tag}{variant}_project_RGBA16.png"),check_existing=False)
        image.colorspace_settings.name="Non-Color"
        tex.image=image
    for j,angle in enumerate(six):
        if variant=="visibility":
            pixels=np.zeros((size*size,4),np.float32);pixels[:,3]=1
            pixels[indices,:3]=raw["six_visibility"][j,:,None]
            image=bpy.data.images.new("RawVisible",width=size,height=size,alpha=True,float_buffer=True)
            image.colorspace_settings.name="Non-Color"
            image.pixels.foreach_set(pixels.reshape(size,size,4)[::-1].ravel())
            tex.image=image
            mat.node_tree.links.new(sep.outputs["Green"],test.inputs[0])
            test.inputs[1].default_value=.5
        else:
            mat.node_tree.links.new(sep.outputs["Red" if angle<0 else "Green"],test.inputs[0])
            test.inputs[1].default_value=abs(angle)/180
        scene.render.filepath=str(renderdir/f"{variant}_{j+1:02d}_{angle:+04d}.png")
        bpy.ops.render.render(write_still=True)
        if variant=="visibility": bpy.data.images.remove(image)
    if variant!="visibility": bpy.data.images.remove(image)
