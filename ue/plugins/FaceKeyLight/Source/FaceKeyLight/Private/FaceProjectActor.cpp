#include "FaceProjectActor.h"
#include "FaceKeyLightComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInstanceDynamic.h"

AFaceProjectActor::AFaceProjectActor()
{
    PrimaryActorTick.bCanEverTick = true;
    GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
    Solver = CreateDefaultSubobject<UFaceKeyLightComponent>(TEXT("FaceLightSolver"));
    PrimaryActorTick.AddPrerequisite(Solver, Solver->PrimaryComponentTick);
}

void AFaceProjectActor::BeginPlay()
{
    Super::BeginPlay();
    FaceMaterial = GetStaticMeshComponent()->CreateDynamicMaterialInstance(0);
}

void AFaceProjectActor::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!FaceMaterial) return;
    const FVector Forward = GetActorTransform().TransformVectorNoScale(LocalFaceForward).GetSafeNormal();
    const FVector Right = GetActorTransform().TransformVectorNoScale(LocalFaceRight).GetSafeNormal();
    const FVector Direction = Solver->bHasLight ? Solver->DirectionToLight : Forward;
    FaceMaterial->SetVectorParameterValue(TEXT("DirectionToLight"), FLinearColor(Direction));
    FaceMaterial->SetVectorParameterValue(TEXT("FaceForward"), FLinearColor(Forward));
    FaceMaterial->SetVectorParameterValue(TEXT("FaceRight"), FLinearColor(Right));
}
