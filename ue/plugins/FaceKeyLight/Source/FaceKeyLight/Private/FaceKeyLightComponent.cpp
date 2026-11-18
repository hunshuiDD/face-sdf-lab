#include "FaceKeyLightComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/LocalLightComponent.h"
#include "Components/SpotLightComponent.h"
#include "GameFramework/Actor.h"
#include "Modules/ModuleManager.h"

IMPLEMENT_MODULE(FDefaultModuleImpl, FaceKeyLight)

UFaceKeyLightComponent::UFaceKeyLightComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
}

void UFaceKeyLightComponent::TickComponent(float Delta, ELevelTick Kind, FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta, Kind, Tick);
    const FVector Point = GetOwner()->GetActorTransform().TransformPosition(LocalSamplePoint);
    AActor* Best = nullptr;
    float BestScore = 0, CurrentScore = 0;
    FVector BestDir = DirectionToLight, CurrentDir = DirectionToLight;
    for (const auto& Entry : Candidates)
    {
        if (!IsValid(Entry.Light) || Entry.Light->IsHidden()) continue;
        const auto* Light = Entry.Light->FindComponentByClass<ULightComponent>();
        if (!Light || !Light->IsVisible() || Entry.ReferenceIntensity <= 0) continue;
        FVector Dir = -Light->GetForwardVector();
        float Influence = 1;
        if (const auto* Local = Cast<ULocalLightComponent>(Light))
        {
            const FVector Offset = Light->GetComponentLocation() - Point;
            if (Local->AttenuationRadius <= 0 || Offset.IsNearlyZero()) continue;
            Dir = Offset.GetSafeNormal();
            Influence = FMath::Square(FMath::Max(0., 1. - Offset.Size() / Local->AttenuationRadius));
            if (const auto* Spot = Cast<USpotLightComponent>(Local))
            {
                const float Outer = FMath::Cos(FMath::DegreesToRadians(Spot->OuterConeAngle));
                const float Inner = FMath::Cos(FMath::DegreesToRadians(Spot->InnerConeAngle));
                const float Cos = FVector::DotProduct(-Dir, Light->GetForwardVector());
                Influence *= Inner > Outer ? FMath::Clamp((Cos - Outer)/(Inner - Outer), 0.f, 1.f) : float(Cos >= Outer);
            }
        }
        else if (!Light->IsA<UDirectionalLightComponent>()) continue;
        const float Score = Light->Intensity / Entry.ReferenceIntensity * Entry.Priority
            * FMath::Clamp(Entry.Visibility, 0.f, 1.f) * Light->GetLightColor().GetLuminance() * Influence;
        if (Entry.Light == Selected && Score > CurrentScore) { CurrentScore = Score; CurrentDir = Dir; }
        if (Score > BestScore) { Best = Entry.Light; BestScore = Score; BestDir = Dir; }
    }
    const bool HadLight = bHasLight;
    bHasLight = Best != nullptr;
    if (!Best) { Selected = nullptr; Pending.Reset(); PendingSeconds = 0; return; }
    bool Switch = CurrentScore <= 0;
    if (!Switch && Best != Selected && BestScore > CurrentScore * (1 + FMath::Max(0.f, SwitchMargin)))
    {
        if (Pending.Get() != Best) { Pending = Best; PendingSeconds = 0; }
        PendingSeconds += FMath::Max(0.f, Delta);
        Switch = PendingSeconds >= FMath::Max(0.f, HoldSeconds);
    }
    else { Pending.Reset(); PendingSeconds = 0; }
    if (Switch) { Selected = Best; CurrentDir = BestDir; Pending.Reset(); PendingSeconds = 0; }
    const float Alpha = !HadLight || BlendSeconds <= 0 ? 1.f : 1.f - FMath::Exp(-Delta / BlendSeconds);
    const FQuat Arc = FQuat::FindBetweenNormals(DirectionToLight, CurrentDir);
    DirectionToLight = FQuat::Slerp(FQuat::Identity, Arc, Alpha).RotateVector(DirectionToLight).GetSafeNormal();
}
