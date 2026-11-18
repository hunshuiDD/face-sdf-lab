using UnrealBuildTool;

public class FaceWipeUI : ModuleRules
{
    public FaceWipeUI(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "UMG", "FaceKeyLight" });
        PrivateDependencyModuleNames.AddRange(new[] { "Slate", "SlateCore", "InputCore", "Json", "JsonUtilities" });
    }
}
