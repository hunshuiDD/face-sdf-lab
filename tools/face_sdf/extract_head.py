"""Read only the selected CC0 asset. No bundled text or driver is executed."""
import bpy
import json
import sys
from pathlib import Path

out=Path(__file__).resolve().parent
args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
source=Path(args[0]).resolve() if args else out/"inputs/human_base_meshes_bundle.blend"
object_name=args[1] if len(args)>1 else "GEO-head_stylized"
bpy.ops.wm.read_factory_settings(use_empty=True)
with bpy.data.libraries.load(str(source),link=False) as (_,dst):
    assert object_name in _.objects,object_name
    dst.objects=[object_name]
    dst.texts=["README"] if "README" in _.texts else []
head=dst.objects[0]
bpy.context.collection.objects.link(head)
head.location=(0,0,0)
head.rotation_euler=(0,0,0)
head.scale=(1,1,1)
head.animation_data_clear()
for polygon in head.data.polygons:
    polygon.use_smooth=True
readme=dst.texts[0].as_string() if dst.texts else "No README supplied. Source license must be recorded by the caller."
if not args: assert "CC0" in readme
(out/"inputs/bundle_README.txt").write_text(readme,encoding="utf8")
me=head.data
me.calc_loop_triangles()
import numpy as np
vertices=np.array([v.co[:] for v in me.vertices],np.float64)
triangles=np.array([t.vertices[:] for t in me.loop_triangles],np.int32)
uv=np.array([[me.uv_layers.active.data[i].uv[:] for i in t.loops] for t in me.loop_triangles],np.float64)
normals=np.array([[me.corner_normals[i].vector[:] for i in t.loops] for t in me.loop_triangles],np.float64)
np.savez_compressed(out/"inputs/head_geometry.npz",vertices=vertices,triangles=triangles,uv=uv,normals=normals)
(out/"inputs/head_facts.json").write_text(json.dumps(dict(blender=bpy.app.version_string,object=head.name,
    vertices=len(vertices),triangles=len(triangles),uv_layer=me.uv_layers.active.name,
    bbox=[vertices.min(0).tolist(),vertices.max(0).tolist()],normal="smooth corner normal",
    forward="-Y",up="+Z",source_position_reset=True,source=source.name),indent=2),encoding="utf8")
bpy.context.preferences.filepaths.save_version=0
bpy.ops.wm.save_as_mainfile(filepath=str(out/"inputs/PublicHead.blend"),compress=True)
