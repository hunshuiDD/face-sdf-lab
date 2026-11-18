#include "FaceKeyLightComponent.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Components/LightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/World.h"
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFaceSwitchTest, "FaceLighting.KeyLightSwitch",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFaceSwitchTest::RunTest(const FString&)
{
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    if (!TestNotNull(TEXT("transient world"), World)) return false;
    auto* Owner = World->SpawnActor<AActor>();
    auto* A = World->SpawnActor<ADirectionalLight>();
    auto* B = World->SpawnActor<ADirectionalLight>();
    B->SetActorRotation(FRotator(0, 180, 0));
    auto* Solver = NewObject<UFaceKeyLightComponent>(Owner);
    Solver->RegisterComponent();
    for (auto* Light : { A, B })
    {
        FFaceLightEntry Entry;
        Entry.Light = Light;
        Entry.ReferenceIntensity = Light->GetLightComponent()->Intensity;
        Solver->Candidates.Add(Entry);
    }
    Solver->Candidates[1].Priority = .9f;
    auto Step = [&](float Dt) { Solver->TickComponent(Dt, LEVELTICK_All, nullptr); };
    Step(.01f);
    TestTrue(TEXT("initial winner"), Solver->Selected == A);
    Solver->Candidates[1].Priority = 1.1f;
    Step(1.f);
    TestTrue(TEXT("inside hysteresis band"), Solver->Selected == A);
    Solver->Candidates[1].Priority = 1.5f;
    Step(.08f);
    TestTrue(TEXT("hold not met"), Solver->Selected == A);
    Solver->Candidates[1].Priority = .9f;
    Step(.1f);
    Solver->Candidates[1].Priority = 1.5f;
    Step(.08f);
    TestTrue(TEXT("interrupted challenger timer reset"), Solver->Selected == A);
    const FVector Old = Solver->DirectionToLight;
    Step(.08f);
    TestTrue(TEXT("sustained challenger"), Solver->Selected == B);
    TestTrue(TEXT("antipodal transition stays finite and normalized"), Solver->DirectionToLight.IsNormalized());
    TestTrue(TEXT("direction moves continuously"), FVector::DotProduct(Old, Solver->DirectionToLight) > -0.99
        && FVector::DotProduct(Old, Solver->DirectionToLight) < .99999);
    Solver->Candidates[1].Visibility = 0.f;
    Step(.01f);
    TestTrue(TEXT("invisible incumbent releases"), Solver->Selected == A);
    Solver->Candidates.Reset();
    Step(.01f);
    TestTrue(TEXT("no candidate"), !Solver->bHasLight && !Solver->Selected);
    World->DestroyWorld(false);
    return true;
}
#endif
