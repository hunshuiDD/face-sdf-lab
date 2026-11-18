#include "FaceWipeWidget.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Components/Slider.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "FaceProjectActor.h"
#include "GameFramework/PlayerController.h"
#include "Framework/Application/SlateApplication.h"
#include "Input/Events.h"
#include "Layout/WidgetPath.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/AutomationTest.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/SVirtualWindow.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFaceWipePointerDragTest, "FaceWipeUI.PointerDragToActorMID",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FFaceWipePointerDragTest::RunTest(const FString&)
{
    if (!TestTrue(TEXT("Slate is initialized"), FSlateApplication::IsInitialized())) return false;
    UWorld* World = UWorld::CreateWorld(EWorldType::Game, false);
    if (!TestNotNull(TEXT("runtime test world"), World)) return false;
    AFaceProjectActor* Actor = World->SpawnActor<AFaceProjectActor>();
    Actor->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere")));
    Actor->GetStaticMeshComponent()->SetMaterial(0, UMaterial::GetDefaultMaterial(MD_Surface));
    Actor->DispatchBeginPlay();
    if (!TestNotNull(TEXT("actor BeginPlay creates its MID"), Actor->FaceMaterial.Get()))
    {
        World->DestroyWorld(false);
        return false;
    }
    APlayerController* Controller = World->SpawnActor<APlayerController>();
    ULocalPlayer* LocalPlayer = NewObject<ULocalPlayer>(GEngine);
    Controller->SetPlayer(LocalPlayer);
    UFaceWipeWidget* Widget = UFaceWipeWidget::CreateForPlayer(Controller);
    if (!TestNotNull(TEXT("normal runtime context finds the one face actor"), Widget))
    {
        World->DestroyWorld(false);
        return false;
    }
    Widget->AddToRoot();
    TSharedRef<SVirtualWindow> Window = SNew(SVirtualWindow).Size(FVector2D(520, 150));
    Window->SetContent(Widget->TakeWidget());
    FSlateApplication& App = FSlateApplication::Get();
    App.RegisterVirtualWindow(Window);
    Window->SlatePrepass();
    TSharedRef<SSlider> Slider = StaticCastSharedRef<SSlider>(Widget->WipeSlider->TakeWidget());
    FWidgetPath Path;
    App.GeneratePathToWidgetChecked(Slider, Path);
    // UE 5.8 event routing indexes a pointer-position entry for each arranged widget.
    // Legacy GeneratePathToWidgetChecked populates only Widgets, so rebuild the full path.
    TArray<FWidgetAndPointer> WidgetsAndPointers;
    for (int32 Index = 0; Index < Path.Widgets.Num(); ++Index)
    {
        WidgetsAndPointers.Emplace(Path.Widgets[Index], TOptional<FVirtualPointerPosition>());
    }
    Path = FWidgetPath(WidgetsAndPointers);
    const FGeometry Geometry = Path.Widgets.Last().Geometry;
    const float Thumb = Widget->WipeSlider->GetWidgetStyle().NormalThumbImage.ImageSize.X;
    const float Width = Geometry.GetLocalSize().X;
    TestTrue(TEXT("arranged UMG slider has usable width"), Width > Thumb + 100);
    TArray<TSharedPtr<FJsonValue>> Samples;
    auto PointerPosition = [&](float Value)
    {
        return FVector2D(Geometry.LocalToAbsolute(FVector2D(Thumb * .5f + Value * (Width - Thumb), Geometry.GetLocalSize().Y * .5f)));
    };
    auto Sample = [&](const TCHAR* Label, float Expected)
    {
        float MIDValue = -1, Compare = -1;
        const bool HasWipe = Actor->FaceMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("WipeX")), MIDValue);
        const bool HasCompare = Actor->FaceMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("CompareEnable")), Compare);
        TestTrue(FString(Label) + TEXT(" MID WipeX exists"), HasWipe);
        TestTrue(FString(Label) + TEXT(" MID CompareEnable exists"), HasCompare);
        TestTrue(FString(Label) + TEXT(" UMG value matches pointer"), FMath::IsNearlyEqual(Widget->WipeSlider->GetValue(), Expected, 1e-4f));
        TestTrue(FString(Label) + TEXT(" model value matches pointer"), FMath::IsNearlyEqual(Widget->GetWipeValue(), Expected, 1e-4f));
        TestTrue(FString(Label) + TEXT(" MID value matches pointer"), FMath::IsNearlyEqual(MIDValue, Expected, 1e-4f));
        TestTrue(FString(Label) + TEXT(" comparison enabled"), Compare == 1.f);
        TSharedRef<FJsonObject> Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("event"), Label);
        Row->SetNumberField(TEXT("expected"), Expected);
        Row->SetNumberField(TEXT("umg_slider"), Widget->WipeSlider->GetValue());
        Row->SetNumberField(TEXT("model"), Widget->GetWipeValue());
        Row->SetNumberField(TEXT("mid_wipe_x"), MIDValue);
        Row->SetNumberField(TEXT("mid_compare_enable"), Compare);
        Samples.Add(MakeShared<FJsonValueObject>(Row));
    };
    auto Drag = [&](float Start, float End, const TCHAR* Label)
    {
        const TSet<FKey> Pressed{ EKeys::LeftMouseButton };
        const FVector2D From = PointerPosition(Start), To = PointerPosition(End);
        FPointerEvent Hover(0, From, From, TSet<FKey>(), EKeys::Invalid, 0, FModifierKeysState());
        App.RoutePointerMoveEvent(Path, Hover, false);
        FPointerEvent Down(0, From, From, Pressed, EKeys::LeftMouseButton, 0, FModifierKeysState());
        App.RoutePointerDownEvent(Path, Down);
        TestTrue(TEXT("real Slate pointer capture acquired"), Slider->HasMouseCaptureByUser(0, 0));
        FPointerEvent Move(0, To, From, Pressed, EKeys::Invalid, 0, FModifierKeysState());
        App.RoutePointerMoveEvent(Path, Move, false);
        Sample(Label, FMath::Clamp(End, 0.f, 1.f));
        FPointerEvent Up(0, To, To, TSet<FKey>(), EKeys::LeftMouseButton, 0, FModifierKeysState());
        App.RoutePointerUpEvent(Path, Up);
        TestFalse(TEXT("real Slate pointer capture released"), Slider->HasMouseCaptureByUser(0, 0));
    };
    Widget->SetWipeValue(.4f);
    Sample(TEXT("programmatic_value"), .4f);
    Drag(.2f, .8f, TEXT("forward_drag"));
    Drag(.8f, .2f, TEXT("reverse_drag"));
    Drag(.2f, -.1f, TEXT("left_clamp"));
    Drag(.2f, 1.1f, TEXT("right_clamp"));

    Widget->CompareToggle->SetIsChecked(false);
    Widget->CompareToggle->OnCheckStateChanged.Broadcast(false);
    float Disabled = -1;
    Actor->FaceMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("CompareEnable")), Disabled);
    TestEqual(TEXT("comparison checkbox drives disabled MID"), Disabled, 0.f);
    Widget->CompareToggle->SetIsChecked(true);
    Widget->CompareToggle->OnCheckStateChanged.Broadcast(true);
    float Enabled = -1;
    Actor->FaceMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("CompareEnable")), Enabled);
    TestEqual(TEXT("comparison checkbox restores MID"), Enabled, 1.f);

    UMaterialInstanceDynamic* Previous = Actor->FaceMaterial;
    Actor->FaceMaterial = UMaterialInstanceDynamic::Create(UMaterial::GetDefaultMaterial(MD_Surface), Actor);
    Widget->RefreshBinding();
    float ReplacementValue = -1;
    Actor->FaceMaterial->GetScalarParameterValue(FMaterialParameterInfo(TEXT("WipeX")), ReplacementValue);
    TestEqual(TEXT("replacement actor MID receives current value"), ReplacementValue, Widget->GetWipeValue());
    TestTrue(TEXT("actor MID was genuinely replaced"), Actor->FaceMaterial.Get() != Previous);

    TSharedRef<FJsonObject> Receipt = MakeShared<FJsonObject>();
    Receipt->SetStringField(TEXT("test"), TEXT("FaceWipeUI.PointerDragToActorMID"));
    Receipt->SetStringField(TEXT("input"), TEXT("FSlateApplication routed pointer down/move/up on actual UMG USlider/SSlider in virtual SWindow"));
    Receipt->SetNumberField(TEXT("slider_width"), Width);
    Receipt->SetNumberField(TEXT("thumb_width"), Thumb);
    Receipt->SetArrayField(TEXT("samples"), Samples);
    Receipt->SetBoolField(TEXT("passed"), !HasAnyErrors());
    FString Filename;
    FParse::Value(FCommandLine::Get(), TEXT("FaceWipeReport="), Filename);
    if (Filename.IsEmpty()) Filename = FPaths::ProjectSavedDir() / TEXT("FaceWipeUI/pointer_receipt.json");
    FString Json;
    FJsonSerializer::Serialize(Receipt, TJsonWriterFactory<>::Create(&Json));
    TestTrue(TEXT("pointer evidence written"), FFileHelper::SaveStringToFile(Json, *Filename));
    App.UnregisterVirtualWindow(Window);
    Widget->RemoveFromRoot();
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
