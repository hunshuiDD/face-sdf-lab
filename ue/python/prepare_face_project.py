"""Create a disposable project-format SDF test with an actual public head and key-light actor."""
import json
import os
import traceback
from pathlib import Path
import unreal as u

root=Path(os.environ.get("FACE_PROJECT_ROOT",str(Path(__file__).resolve().parents[1])))
out=root/"evidence"
out.mkdir(parents=True, exist_ok=True)
report={"engine":u.SystemLibrary.get_engine_version(),"status":"PREPARING"}
def save():
    (out/"prepare.json").write_text(json.dumps(report,indent=2),encoding="utf8")
def xyz(v):return [float(v.x),float(v.y),float(v.z)]
try:
    editor=u.get_editor_subsystem(u.UnrealEditorSubsystem)
    level=u.get_editor_subsystem(u.LevelEditorSubsystem)
    path="/Game/FaceProject/L_PublicFace"
    assert level.load_level(path) if u.EditorAssetLibrary.does_asset_exist(path) else level.new_level(path)
    world=editor.get_editor_world()
    actors=u.get_editor_subsystem(u.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        actors.destroy_actor(actor)
    tools=u.AssetToolsHelpers.get_asset_tools()
    task=u.AssetImportTask()
    task.filename=str(root/"source/PublicHead.fbx")
    task.destination_path="/Game/FaceProject"
    task.destination_name="SM_PublicHead"
    task.automated=True
    task.replace_existing=True
    task.save=True
    options=u.FbxImportUI()
    options.import_mesh=True
    options.import_materials=False
    options.import_textures=False
    options.import_as_skeletal=False
    options.mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH
    options.static_mesh_import_data.combine_meshes=True
    options.static_mesh_import_data.normal_import_method=u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS
    options.static_mesh_import_data.generate_lightmap_u_vs=False
    task.options=options
    tools.import_asset_tasks([task])
    mesh=u.load_asset(task.imported_object_paths[0])
    tex_task=u.AssetImportTask()
    tex_task.filename=str(root/"source/PublicHead_project.exr")
    tex_task.destination_path="/Game/FaceProject"
    tex_task.destination_name="T_PublicHead_Project"
    tex_task.automated=True
    tex_task.replace_existing=True
    tex_task.save=True
    tools.import_asset_tasks([tex_task])
    texture=u.load_asset(tex_task.imported_object_paths[0])
    texture.set_editor_property("srgb",False)
    texture.set_editor_property("compression_settings",u.TextureCompressionSettings.TC_HDR)
    texture.set_editor_property("mip_gen_settings",u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    texture.set_editor_property("never_stream",True)
    texture.set_editor_property("address_x",u.TextureAddress.TA_CLAMP)
    texture.set_editor_property("address_y",u.TextureAddress.TA_CLAMP)
    u.EditorAssetLibrary.save_loaded_asset(texture)
    lib=u.MaterialEditingLibrary
    mat=u.load_asset("/Game/FaceProject/M_FaceProject")
    if mat:
        lib.delete_all_material_expressions(mat)
    else:
        mat=tools.create_asset("M_FaceProject","/Game/FaceProject",u.Material,u.MaterialFactoryNew())
    mat.set_editor_property("shading_model",u.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("two_sided",False)
    custom=lib.create_material_expression(mat,u.MaterialExpressionCustom,0,0)
    custom.set_editor_property("output_type",u.CustomMaterialOutputType.CMOT_FLOAT3)
    custom.set_editor_property("code",(root/"shaders/FaceProject.ush").read_text(encoding="utf8"))
    names=["Project","DirectionToLight","FaceForward","FaceRight","SoftDegrees","EnableAA","LightColor","DarkColor","DebugMode",
           "WorldNormal","ViewDirection","ScreenUV","HighlightStrength","HighlightPower","CompareEnable","WipeX"]
    inputs=[]
    for name in names:
        item=u.CustomInput()
        item.set_editor_property("input_name",name)
        inputs.append(item)
    custom.set_editor_property("inputs",inputs)
    sample=lib.create_material_expression(mat,u.MaterialExpressionTextureSampleParameter2D,-500,0)
    sample.set_editor_property("parameter_name","ProjectTex")
    sample.set_editor_property("texture",texture)
    sample.set_editor_property("sampler_type",u.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
    assert lib.connect_material_expressions(sample,"RGBA",custom,"Project")
    for node_type,output,name in ((u.MaterialExpressionPixelNormalWS,"","WorldNormal"),
                                  (u.MaterialExpressionCameraVectorWS,"","ViewDirection"),
                                  (u.MaterialExpressionScreenPosition,"ViewportUV","ScreenUV")):
        node=lib.create_material_expression(mat,node_type,-700,-100)
        assert lib.connect_material_expressions(node,output,custom,name)
    vectors={"DirectionToLight":(0,-1,0),"FaceForward":(0,-1,0),"FaceRight":(1,0,0),
             "LightColor":(.65,.47,.37),"DarkColor":(.16,.09,.075)}
    for i,(name,value) in enumerate(vectors.items()):
        node=lib.create_material_expression(mat,u.MaterialExpressionVectorParameter,-500,140+i*90)
        node.set_editor_property("parameter_name",name)
        node.set_editor_property("default_value",u.LinearColor(*value,1))
        assert lib.connect_material_expressions(node,"RGB",custom,name)
    for i,(name,value) in enumerate({"SoftDegrees":3.,"EnableAA":1.,"DebugMode":0.,"HighlightStrength":.12,
                                   "HighlightPower":64.,"CompareEnable":0.,"WipeX":.5}.items()):
        node=lib.create_material_expression(mat,u.MaterialExpressionScalarParameter,-250,150+i*90)
        node.set_editor_property("parameter_name",name)
        node.set_editor_property("default_value",value)
        assert lib.connect_material_expressions(node,"",custom,name)
    assert lib.connect_material_property(custom,"",u.MaterialProperty.MP_EMISSIVE_COLOR)
    lib.recompile_material(mat)
    u.EditorAssetLibrary.save_loaded_asset(mat)
    actor=actors.spawn_actor_from_class(u.load_class(None,"/Script/FaceKeyLight.FaceProjectActor"),u.Vector(0,0,0))
    actor.set_actor_label("PublicHead_FaceProject")
    actor.set_actor_rotation(u.Rotator(pitch=0,yaw=180,roll=0),False)
    actor.local_face_forward=u.Vector(0,1,0)
    actor.local_face_right=u.Vector(1,0,0)
    actor.static_mesh_component.set_static_mesh(mesh)
    actor.static_mesh_component.set_material(0,mat)
    bounds=actor.get_actor_bounds(False)
    centre,extent=bounds
    light=actors.spawn_actor_from_class(u.DirectionalLight,u.Vector(0,-100,100))
    light.set_actor_label("FaceKey")
    light.light_component.set_mobility(u.ComponentMobility.MOVABLE)
    light.light_component.set_intensity(1.)
    entry=u.FaceLightEntry()
    entry.light=light
    entry.reference_intensity=1.
    actor.solver.candidates=[entry]
    actor.solver.blend_seconds=0.
    actor.solver.hold_seconds=0.
    camera_position=u.Vector(55,-115,centre.z+13)
    rotation=u.MathLibrary.find_look_at_rotation(camera_position,u.Vector(0,-3,centre.z+3))
    cam=actors.spawn_actor_from_class(u.CameraActor,camera_position,rotation)
    cam.set_actor_label("CAM_PublicHead")
    cam_comp=cam.get_component_by_class(u.CameraComponent)
    cam_comp.set_field_of_view(28)
    cam_comp.set_editor_property("constrain_aspect_ratio",False)
    cap_actor=actors.spawn_actor_from_class(u.SceneCapture2D,camera_position,rotation)
    cap=cap_actor.get_component_by_class(u.SceneCaptureComponent2D)
    cap.set_editor_property("fov_angle",28.)
    cap.set_editor_property("capture_every_frame",False)
    cap.set_editor_property("capture_on_movement",False)
    cap.set_editor_property("capture_source",u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
    actors.spawn_actor_from_class(u.PlayerStart,u.Vector(0,-300,100))
    pp=actors.spawn_actor_from_class(u.PostProcessVolume,u.Vector())
    pp.set_editor_property("unbound",True)
    settings=pp.settings
    settings.set_editor_property("override_auto_exposure_method",True)
    settings.set_editor_property("auto_exposure_method",u.AutoExposureMethod.AEM_MANUAL)
    settings.set_editor_property("override_auto_exposure_bias",True)
    settings.set_editor_property("auto_exposure_bias",0.)
    pp.settings=settings
    assert u.EditorLoadingAndSavingUtils.save_map(world,"/Game/FaceProject/L_PublicFace")
    report.update(status="SAVED",mesh=mesh.get_path_name(),texture=texture.get_path_name(),
        source_size=[texture.blueprint_get_size_x(),texture.blueprint_get_size_y()],srgb=texture.srgb,
        compression=str(texture.compression_settings),bounds={"centre":xyz(centre),"extent":xyz(extent)},
        actor_class=actor.get_class().get_path_name(),camera={"position":xyz(camera_position),"rotation":str(rotation)},
        forward=xyz(u.MathLibrary.transform_direction(actor.get_actor_transform(),actor.local_face_forward)),
        right=xyz(u.MathLibrary.transform_direction(actor.get_actor_transform(),actor.local_face_right)))
except Exception:
    report.update(status="FAILED",error=traceback.format_exc())
    u.log_error(report["error"])
finally:
    save()
    u.SystemLibrary.quit_editor()
