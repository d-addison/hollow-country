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
        float dawn = Math.Clamp((hour - 8.0) / 2.0, 0.0, 1.0);
        float dusk = Math.Clamp((18.0 - hour) / 4.0, 0.0, 1.0);
        float daylight = dawn * dusk;
        float damp = 0.45 * Math.Clamp(overcast, 0.0, 1.0) + 0.25 * Math.Clamp(fog, 0.0, 1.0) + 0.30 * Math.Clamp(rain, 0.0, 1.0);
        float amount = strength * daylight;
        grade.Desaturation = amount * (0.12 + 0.10 * damp);
        grade.TintRed = 1.0 - amount * (0.025 + 0.015 * damp);
        grade.TintGreen = 1.0 - amount * 0.005;
        grade.TintBlue = 1.0 - amount * 0.012;
        grade.Contrast = 1.0 + amount * (0.025 + 0.015 * damp);
        grade.Vignette = amount * (0.025 + 0.025 * damp);
        grade.Exposure = 1.0;
    }
}
