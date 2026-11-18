#include "FaceWipeWidget.h"

#include "Blueprint/WidgetTree.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/SizeBox.h"
#include "Components/Slider.h"
#include "Components/TextBlock.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "EngineUtils.h"
#include "FaceProjectActor.h"
#include "GameFramework/PlayerController.h"
#include "Materials/MaterialInstanceDynamic.h"

UFaceWipeWidget* UFaceWipeWidget::CreateForPlayer(APlayerController* PlayerController, AFaceProjectActor* ExplicitFaceActor)
{
    if (!IsValid(PlayerController) || !PlayerController->IsLocalPlayerController()) return nullptr;
    AFaceProjectActor* Target = ExplicitFaceActor;
    if (!Target)
    {
        for (TActorIterator<AFaceProjectActor> It(PlayerController->GetWorld()); It; ++It)
        {
            if (Target) return nullptr;
            Target = *It;
        }
    }
    if (!IsValid(Target) || Target->GetWorld() != PlayerController->GetWorld()) return nullptr;
    UFaceWipeWidget* Widget = CreateWidget<UFaceWipeWidget>(PlayerController, StaticClass());
    if (!Widget || !Widget->BindFaceActor(Target)) return nullptr;
    return Widget;
}

TSharedRef<SWidget> UFaceWipeWidget::RebuildWidget()
{
    if (!WidgetTree) WidgetTree = NewObject<UWidgetTree>(this, TEXT("WidgetTree"));
    if (!WidgetTree->RootWidget)
    {
        USizeBox* Size = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("WipePanel"));
        Size->SetWidthOverride(420);
        Size->SetHeightOverride(100);
        WidgetTree->RootWidget = Size;
        UVerticalBox* Column = WidgetTree->ConstructWidget<UVerticalBox>();
        Size->AddChild(Column);
        UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>();
        Column->AddChildToVerticalBox(Row)->SetPadding(FMargin(0, 8));
        CompareToggle = WidgetTree->ConstructWidget<UCheckBox>(UCheckBox::StaticClass(), TEXT("CompareEnable"));
        CompareToggle->SetIsChecked(bComparisonEnabled);
        CompareToggle->OnCheckStateChanged.AddDynamic(this, &UFaceWipeWidget::OnComparisonChanged);
        Row->AddChildToHorizontalBox(CompareToggle)->SetPadding(FMargin(0, 0, 12, 0));
        ValueLabel = WidgetTree->ConstructWidget<UTextBlock>();
        Row->AddChildToHorizontalBox(ValueLabel);
        WipeSlider = WidgetTree->ConstructWidget<USlider>(USlider::StaticClass(), TEXT("WipeX"));
        WipeSlider->SetMinValue(0);
        WipeSlider->SetMaxValue(1);
        WipeSlider->SetValue(WipeValue);
        WipeSlider->SetIndentHandle(false);
        WipeSlider->OnValueChanged.AddDynamic(this, &UFaceWipeWidget::OnWipeChanged);
        Column->AddChildToVerticalBox(WipeSlider)->SetPadding(FMargin(0, 8));
        UpdateLabel();
    }
    RefreshBinding();
    return Super::RebuildWidget();
}

bool UFaceWipeWidget::BindFaceActor(AFaceProjectActor* Actor)
{
    if (!IsValid(Actor) || Actor->GetWorld() != GetWorld()) return false;
    FaceActor = Actor;
    RefreshBinding();
    return true;
}

void UFaceWipeWidget::RefreshBinding()
{
    UMaterialInstanceDynamic* Current = FaceActor.IsValid() ? FaceActor->FaceMaterial.Get() : nullptr;
    if (Current != BoundMaterial.Get())
    {
        BoundMaterial = Current;
        ApplyParameters();
    }
    if (WipeSlider) WipeSlider->SetIsEnabled(Current != nullptr);
    if (CompareToggle) CompareToggle->SetIsEnabled(Current != nullptr);
}

void UFaceWipeWidget::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
    Super::NativeTick(MyGeometry, InDeltaTime);
    RefreshBinding();
}

void UFaceWipeWidget::OnWipeChanged(float Value)
{
    if (!FMath::IsFinite(Value)) return;
    WipeValue = FMath::Clamp(Value, 0.f, 1.f);
    UpdateLabel();
    ApplyParameters();
}

void UFaceWipeWidget::SetWipeValue(float Value)
{
    if (!FMath::IsFinite(Value)) return;
    Value = FMath::Clamp(Value, 0.f, 1.f);
    if (WipeSlider) WipeSlider->SetValue(Value);
    OnWipeChanged(Value);
}

void UFaceWipeWidget::OnComparisonChanged(bool bChecked)
{
    bComparisonEnabled = bChecked;
    ApplyParameters();
}

void UFaceWipeWidget::ApplyParameters()
{
    if (UMaterialInstanceDynamic* Material = BoundMaterial.Get())
    {
        Material->SetScalarParameterValue(TEXT("CompareEnable"), bComparisonEnabled ? 1.f : 0.f);
        Material->SetScalarParameterValue(TEXT("WipeX"), WipeValue);
    }
}

void UFaceWipeWidget::UpdateLabel()
{
    if (ValueLabel) ValueLabel->SetText(FText::FromString(FString::Printf(TEXT("Material comparison  %.0f%%"), WipeValue * 100)));
}
