// LC-T101 / EXP-A1: authored, provisional late-autumn values; not native acceptance.
// Native snapshot scripts-1.30.164289 (paths relative to that snapshot):
// 1_Core/proto/EnMath.c:540 Math.Clamp.
// 3_Game/PPEManager/Materials/MatClasses/PPEGlow.c:114-123 neutral contrast,
// saturation, colourisation and vignette; :106 filmic exposure baseline 4.0.
// Exposure below is a neutral multiplier; the requester never writes exposure.
class HCGradeParameters
{
    float Desaturation;
    float TintRed = 1.0;
    float TintGreen = 1.0;
    float TintBlue = 1.0;
    float Contrast = 1.0;
    float Vignette;
    float Exposure = 1.0;
}

class HCGradePolicy
{
    // Return through a caller-owned parameter set, avoiding per-frame allocation.
    // Autumn daylight 08-16; lower-weight dusk fades out completely at 18.
    // Night is complete identity, including tint/contrast/vignette, not just EV.
    static void Evaluate(float hour, float overcast, float fog, float rain, float intensity, HCGradeParameters grade)
    {
        float strength = Math.Clamp(intensity, 0.0, 1.0);
        float dawn = Math.Clamp((hour - HCc2PresentationConfig.HCGet().GradeDawnHour) / HCc2PresentationConfig.HCGet().GradeDawnBlendHours, 0.0, 1.0);
        float dusk = Math.Clamp((HCc2PresentationConfig.HCGet().GradeDuskHour - hour) / HCc2PresentationConfig.HCGet().GradeDuskBlendHours, 0.0, 1.0);
        float daylight = dawn * dusk;
        float damp = HCc2PresentationConfig.HCGet().GradeCloudWeight * Math.Clamp(overcast, 0.0, 1.0) + HCc2PresentationConfig.HCGet().GradeFogWeight * Math.Clamp(fog, 0.0, 1.0) + HCc2PresentationConfig.HCGet().GradeRainWeight * Math.Clamp(rain, 0.0, 1.0);
        float amount = strength * daylight;
        grade.Desaturation = amount * (HCc2PresentationConfig.HCGet().GradeDesaturation + HCc2PresentationConfig.HCGet().GradeDampDesaturation * damp);
        grade.TintRed = 1.0 - amount * (HCc2PresentationConfig.HCGet().GradeTintRed + HCc2PresentationConfig.HCGet().GradeDampTintRed * damp);
        grade.TintGreen = 1.0 - amount * HCc2PresentationConfig.HCGet().GradeTintGreen;
        grade.TintBlue = 1.0 - amount * HCc2PresentationConfig.HCGet().GradeTintBlue;
        grade.Contrast = 1.0 + amount * (HCc2PresentationConfig.HCGet().GradeContrast + HCc2PresentationConfig.HCGet().GradeDampContrast * damp);
        grade.Vignette = amount * (HCc2PresentationConfig.HCGet().GradeVignette + HCc2PresentationConfig.HCGet().GradeDampVignette * damp);
        grade.Exposure = 1.0;
    }
}
