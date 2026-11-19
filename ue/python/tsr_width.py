"""Apply after setting the AA method, and again when quality settings change."""
import unreal


def apply_face_width(mid, requested_width=1.0, tsr_width=0.0):
    aa_method = unreal.SystemLibrary.get_console_variable_int_value("r.AntiAliasingMethod")
    weight = min(requested_width, tsr_width) if aa_method == 4 else requested_width
    mid.set_scalar_parameter_value("EnableAA", weight)
    return weight


if __name__ == "__main__":
    world = unreal.find_object(None, "/Game/FaceProject/L_PublicFace.L_PublicFace")
    cls = unreal.load_class(None, "/Script/FaceKeyLight.FaceProjectActor")
    head, = unreal.GameplayStatics.get_all_actors_of_class(world, cls)
    weight = apply_face_width(head.face_material)
    unreal.log(f"CC0 face EnableAA = {weight}")
