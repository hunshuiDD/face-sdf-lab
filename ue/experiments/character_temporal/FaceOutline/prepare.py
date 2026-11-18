"""Author three inspectable outline paths in a copy of the standalone CC0 head host."""
from pathlib import Path
import json
import os
import traceback
import unreal as u

out=Path(__file__).resolve().parent
lib=u.MaterialEditingLibrary
asset=u.AssetToolsHelpers.get_asset_tools()
folder="/Game/FaceOutline"
def material(name):
    p=folder+"/"+name
    m=u.load_asset(p) if u.EditorAssetLibrary.does_asset_exist(p) else asset.create_asset(name,folder,u.Material,u.MaterialFactoryNew())
    lib.delete_all_material_expressions(m)
    return m
def node(m,cls):
    return lib.create_material_expression(m,cls,0,0)
def connect(a,output,b,slot):
    assert lib.connect_material_expressions(a,output,b,slot)
def finish(m):
    lib.recompile_material(m)
    assert u.EditorAssetLibrary.save_loaded_asset(m)

report={}
try:
    shell=material("M_ReverseShell")
    shell.set_editor_property("shading_model",u.MaterialShadingModel.MSM_UNLIT)
    normal=node(shell,u.MaterialExpressionVertexNormalWS)
    thickness=node(shell,u.MaterialExpressionConstant);thickness.r=.24
    scale=node(shell,u.MaterialExpressionMultiply)
    connect(normal,"",scale,"A");connect(thickness,"",scale,"B")
    assert lib.connect_material_property(scale,"",u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    ink=node(shell,u.MaterialExpressionConstant3Vector);ink.constant=u.LinearColor(1,0,1,1)
    assert lib.connect_material_property(ink,"",u.MaterialProperty.MP_EMISSIVE_COLOR)
    finish(shell)
    for name,location in (("Before","BL_SCENE_COLOR_BEFORE_DOF"),("After","BL_SCENE_COLOR_AFTER_TONEMAPPING")):
        m=material("M_Stencil"+name)
        m.set_editor_property("material_domain",u.MaterialDomain.MD_POST_PROCESS)
        m.set_editor_property("blendable_location",getattr(u.BlendableLocation,location))
        # Material code generation registers both scene textures via explicit inputs.
        color=node(m,u.MaterialExpressionSceneTexture);color.set_editor_property("scene_texture_id",u.SceneTextureId.PPI_POST_PROCESS_INPUT0)
        stencil=node(m,u.MaterialExpressionSceneTexture);stencil.set_editor_property("scene_texture_id",u.SceneTextureId.PPI_CUSTOM_STENCIL)
        radius=node(m,u.MaterialExpressionScalarParameter);radius.set_editor_property("parameter_name","Radius");radius.set_editor_property("default_value",2.)
        expr=node(m,u.MaterialExpressionCustom)
        args=[]
        for n in ("Color","Stencil","Radius"):
            arg=u.CustomInput();arg.set_editor_property("input_name",n);args.append(arg)
        expr.set_editor_property("inputs",args)
        expr.set_editor_property("output_type",u.CustomMaterialOutputType.CMOT_FLOAT3)
        expr.set_editor_property("code",(out/"stencil_outline.ush").read_text(encoding="utf8"))
        connect(color,"Color",expr,"Color");connect(stencil,"Color",expr,"Stencil");connect(radius,"",expr,"Radius")
        assert lib.connect_material_property(expr,"",u.MaterialProperty.MP_EMISSIVE_COLOR)
        finish(m)
    level=u.get_editor_subsystem(u.LevelEditorSubsystem)
    assert level.load_level("/Game/FaceProject/L_PublicFace")
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    source,=[a for a in actors.get_all_level_actors() if a.get_actor_label()=="PublicHead_FaceProject"]
    comp=source.static_mesh_component
    comp.set_render_custom_depth(True)
    comp.set_custom_depth_stencil_value(1)
    duplicate=actors.spawn_actor_from_class(u.StaticMeshActor,source.get_actor_location(),source.get_actor_rotation())
    duplicate.set_actor_label("DiagnosticReverseShell")
    outer=duplicate.static_mesh_component
    outer.set_mobility(u.ComponentMobility.MOVABLE)
    outer.set_static_mesh(comp.static_mesh)
    outer.set_reverse_culling(True)
    outer.set_material(0,shell)
    outer.set_cast_shadow(False)
    duplicate.set_actor_hidden_in_game(True)
    assert u.EditorLoadingAndSavingUtils.save_map(world,folder+"/L_Outlines")
    # Keep the previous six-direction asset and map intact in both hosts.
    # Only this new material/map is used by the analytic-kernel comparison.
    newpath=folder+"/M_FaceLinear"
    if not u.EditorAssetLibrary.does_asset_exist(newpath):
        assert u.EditorAssetLibrary.duplicate_asset("/Game/FaceProject/M_FaceProject",newpath)
    candidate=u.load_asset(newpath)
    expr=lib.get_material_property_input_node(candidate,u.MaterialProperty.MP_EMISSIVE_COLOR)
    original=Path(os.environ.get("TA_FACE_SHADER",out.parents[2]/"shaders/FaceProject.ush")).read_text(encoding="utf8")
    begin=original.index("float width =")
    end=original.index("float lit =",begin)
    kernel=(out/"coverage.ush").read_text(encoding="utf8")
    expr.set_editor_property("code",original[:begin]+kernel+"\n"+original[end:])
    finish(candidate)
    comp.set_material(0,candidate)
    assert u.EditorLoadingAndSavingUtils.save_map(world,folder+"/L_LinearFace")
    report.update(status="SAVED",asset=comp.static_mesh.get_path_name(),shell_cm=.24,stencil=1)
except Exception:report.update(status="FAILED",error=traceback.format_exc())
(out/"prepare.json").write_text(json.dumps(report,indent=2),encoding="utf8")
if report["status"]!="SAVED":raise RuntimeError(report["error"])
