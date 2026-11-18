#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/CheckBox.h"
#include "FaceWipeWidget.generated.h"

class AFaceProjectActor;
class USlider;
class UTextBlock;
class UMaterialInstanceDynamic;

UCLASS()
class FACEWIPEUI_API UFaceWipeWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category="Face Wipe")
    static UFaceWipeWidget* CreateForPlayer(APlayerController* PlayerController, AFaceProjectActor* ExplicitFaceActor = nullptr);

    UFUNCTION(BlueprintCallable, Category="Face Wipe")
    bool BindFaceActor(AFaceProjectActor* Actor);

    UFUNCTION(BlueprintCallable, Category="Face Wipe")
    void RefreshBinding();

    UFUNCTION(BlueprintCallable, Category="Face Wipe")
    void SetWipeValue(float Value);

    UFUNCTION(BlueprintPure, Category="Face Wipe")
    float GetWipeValue() const { return WipeValue; }

    UFUNCTION(BlueprintPure, Category="Face Wipe")
    bool IsComparisonEnabled() const { return bComparisonEnabled; }

    UPROPERTY(Transient, BlueprintReadOnly, Category="Face Wipe")
    TObjectPtr<USlider> WipeSlider;

    UPROPERTY(Transient, BlueprintReadOnly, Category="Face Wipe")
    TObjectPtr<UCheckBox> CompareToggle;

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

private:
    UFUNCTION() void OnWipeChanged(float Value);
    UFUNCTION() void OnComparisonChanged(bool bChecked);
    void ApplyParameters();
    void UpdateLabel();

    UPROPERTY(Transient) TWeakObjectPtr<AFaceProjectActor> FaceActor;
    UPROPERTY(Transient) TWeakObjectPtr<UMaterialInstanceDynamic> BoundMaterial;
    UPROPERTY(Transient) TObjectPtr<UTextBlock> ValueLabel;
    float WipeValue = 0.5f;
    bool bComparisonEnabled = true;
};
