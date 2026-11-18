#pragma once
#include "CoreMinimal.h"
#include "Engine/StaticMeshActor.h"
#include "FaceProjectActor.generated.h"

class UFaceKeyLightComponent;
class UMaterialInstanceDynamic;

UCLASS()
class FACEKEYLIGHT_API AFaceProjectActor : public AStaticMeshActor
{
    GENERATED_BODY()
public:
    AFaceProjectActor();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Face") TObjectPtr<UFaceKeyLightComponent> Solver;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") FVector LocalFaceForward = FVector(0,-1,0);
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Face") FVector LocalFaceRight = FVector(1,0,0);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Face") TObjectPtr<UMaterialInstanceDynamic> FaceMaterial;
    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
};
