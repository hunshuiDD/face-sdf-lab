#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "FaceKeyLightComponent.generated.h"

USTRUCT(BlueprintType)
struct FFaceLightEntry
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") TObjectPtr<AActor> Light;
    // Intensity of this light (in its own editor units) at artistic score 1.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face", meta=(ClampMin="0.001")) float ReferenceIntensity = 1;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face", meta=(ClampMin="0.0")) float Priority = 1;
    // Optional externally measured visibility. 1 disables occlusion weighting.
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face", meta=(ClampMin="0.0",ClampMax="1.0")) float Visibility = 1;
};

UCLASS(ClassGroup=(Rendering),meta=(BlueprintSpawnableComponent))
class FACEKEYLIGHT_API UFaceKeyLightComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UFaceKeyLightComponent();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") TArray<FFaceLightEntry> Candidates;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") FVector LocalSamplePoint = FVector::ZeroVector;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") float SwitchMargin = 0.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") float HoldSeconds = 0.15f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") float BlendSeconds = 0.25f;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Face") FVector DirectionToLight = FVector::ForwardVector;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Face") TObjectPtr<AActor> Selected;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Face") bool bHasLight = false;
    virtual void TickComponent(float Delta, ELevelTick Kind, FActorComponentTickFunction* Tick) override;
private:
    TWeakObjectPtr<AActor> Pending;
    float PendingSeconds = 0;
};
