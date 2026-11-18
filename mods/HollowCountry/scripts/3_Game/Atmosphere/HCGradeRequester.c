// LC-T102 / EXP-A1. Native snapshot scripts-1.30.164289, relative paths:
// 3_Game/PPEManager/Requesters/PPERequestPlatformsBase.c:2 PPERequesterBase,
// :38-56 Start/Stop/IsRequesterRunning, :155 SetTargetValueFloat,
// :197 SetTargetValueColor, :319 GetActiveRequestStructure, :360 OnStop reset.
// 3_Game/PPEManager/PPERequesterBank.c:78 GetRequester(typename), :174
// RegisterRequester, :262-273 PPERequesterRegistrations extension hook.
// 3_Game/PPEManager/PPEManager.c:61 active-request list, :195 SetRequestActive;
// 3_Game/PPEManager/PPERequestData.c:49 IsDataActive, :59 IsSettingDefaultValues.
// 3_Game/PPEManager/Materials/MatParameters/PPEMatClassParameterCommandData.c:81-86
// sorts layers ascending. Layer -1000 precedes native layers (including zero).
// 3_Game/PPEManager/Materials/MatClasses/PPEGlow.c:27-35 parameters, :42-78
// native layers, :114-123 defaults. No direct material, exposure or NV writes.
// Vanilla examples: Requesters/PPERBloodLoss.c:5 saturation setter;
// Requesters/PPERUnconEffects.c:16-26 Start/vignette;
// Requesters/PPERCameraNV.c:64-70 NV colourisation/exposure layers.
// BloodLoss symptom uses setters without Start: 4_World/Classes/PlayerSymptoms/
// States/Secondary/BloodLoss.c:39-49. Running status alone cannot detect it.

class HCGradeRequester extends PPERequester_GameplayBase
{
    static const int GRADE_LAYER = -1000;

    void Apply(HCGradeParameters grade)
    {
        if (!IsRequesterRunning()) { Start(); }
        SetTargetValueFloat(PostProcessEffectType.Glow, PPEGlow.PARAM_SATURATION, false, 1.0 - grade.Desaturation, GRADE_LAYER, PPOperators.SET);
        SetTargetValueColor(PostProcessEffectType.Glow, PPEGlow.PARAM_COLORIZATIONCOLOR, {grade.TintRed, grade.TintGreen, grade.TintBlue, 0.0}, GRADE_LAYER, PPOperators.SET);
        SetTargetValueFloat(PostProcessEffectType.Glow, PPEGlow.PARAM_CONTRAST, false, grade.Contrast, GRADE_LAYER, PPOperators.SET);
        SetTargetValueFloat(PostProcessEffectType.Glow, PPEGlow.PARAM_VIGNETTE, false, grade.Vignette, GRADE_LAYER, PPOperators.SET);
    }
}

modded class PPERequesterRegistrations
{
    override protected void RegisterAdditionalRequesters()
    {
        super.RegisterAdditionalRequesters();
        PPERequesterBank.RegisterRequester(HCGradeRequester);
    }
}

modded class PPEManager
{
    // Read-only query includes native/mod requesters, new ones, and setter-only
    // effects. Never stops or changes anyone else's requester. List is the
    // manager's existing finite requester bank, not a world/entity scan.
    bool HCGradeNativeActive(PPERequesterBase gradeRequester)
    {
        if (!m_ManagerInitialized || !m_ExistingPostprocessRequests) { return true; }
        foreach (PPERequesterBase other : m_ExistingPostprocessRequests)
        {
            if (!other || other == gradeRequester) { continue; }
            if (other.IsRequesterRunning()) { return true; }
            map<int, ref map<int, ref PPERequestParamDataBase>> materials = other.GetActiveRequestStructure();
            if (!materials) { continue; }
            for (int materialIndex = 0; materialIndex < materials.Count(); materialIndex++)
            {
                map<int, ref PPERequestParamDataBase> parameters = materials.GetElement(materialIndex);
                for (int parameterIndex = 0; parameterIndex < parameters.Count(); parameterIndex++)
                {
                    PPERequestParamDataBase command = parameters.GetElement(parameterIndex);
                    if (command && command.IsDataActive() && !command.IsSettingDefaultValues()) { return true; }
                }
            }
        }
        return false;
    }
}
