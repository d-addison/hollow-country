// C2 optional tuning; missing keys retain authored defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// Bounded read through HCGroupIO (EnSystem.c:417/425/443). No profile writes.
// Season tuning is loaded once per process. Presentation tuning is server-owned;
// HCPresentationTuningSync transports validated values and polls for file changes.
class HCc2SeasonTuning
{
    static const int READ_LIMIT = 8192;
    float SNAPSHOT_TTL_SECONDS = 90.0;
    float SNAPSHOT_HEARTBEAT_SECONDS = 30.0;
    float FOG_BLEND_HOURS = 0.5;
    float BASELINE_FOG = 0.04;
    float SUMMER_RAIN_SCALE = 0.5;
    float AUTUMN_RAIN_MIN = 0.45;
    float AUTUMN_FOG_MIN = 0.18;
    float WINTER_FOG_MIN = 0.08;
    float AUTUMN_CLOUD_MIN = 0.75;
    float WINTER_CLOUD_MIN = 0.8;
    float SNOW_CLOUD_THRESHOLD = 0.6;
    float WINTER_SNOWFALL = 0.55;
    float SPRING_GRADE = 0.06;
    float SUMMER_GRADE = 0.04;
    float AUTUMN_GRADE = 0.14;
    float WINTER_GRADE = 0.12;
    float AutumnRainCloudThreshold = 0.65;
    float FogDayStartHour = 5;
    float FogDayEndHour = 20;
    protected static ref HCc2SeasonTuning s_Config;

    static HCc2SeasonTuning HCGet()
    {
        if (!HCc2SeasonTuning.s_Config) { HCc2SeasonTuning.s_Config = HCc2SeasonTuning.HCLoad(); }
        return HCc2SeasonTuning.s_Config;
    }

    static void HCSet(HCc2SeasonTuning config) { HCc2SeasonTuning.s_Config = config; }

    static HCc2SeasonTuning HCLoad()
    {
        HCc2SeasonTuning defaults = new HCc2SeasonTuning;
        string path = "$profile:HollowCountry/seasons.json";
        if (!FileExist(path)) { return defaults; }
        string image;
        string error;
        HCc2SeasonTuning loaded;
        if (!HCGroupIO.Read(path, HCc2SeasonTuning.READ_LIMIT, image) || !JsonFileLoader<HCc2SeasonTuning>.LoadData(image, loaded, error) || !loaded)
        {
            Print("[HC Config] seasons reason=read_or_json defaults_retained runtime=PENDING");
            return defaults;
        }
        defaults.HCApply(image, loaded);
        return defaults;
    }

    void HCApply(string image, HCc2SeasonTuning loaded)
    {
        bool invalid = false;
        this.SNAPSHOT_TTL_SECONDS = 90.0;
        if (HCJsonFields.Has(image, "SNAPSHOT_TTL_SECONDS"))
        {
            if (loaded.SNAPSHOT_TTL_SECONDS >= 1 && loaded.SNAPSHOT_TTL_SECONDS <= 300) { this.SNAPSHOT_TTL_SECONDS = loaded.SNAPSHOT_TTL_SECONDS; }
            else { invalid = true; }
        }
        this.SNAPSHOT_HEARTBEAT_SECONDS = 30.0;
        if (HCJsonFields.Has(image, "SNAPSHOT_HEARTBEAT_SECONDS"))
        {
            if (loaded.SNAPSHOT_HEARTBEAT_SECONDS >= 1 && loaded.SNAPSHOT_HEARTBEAT_SECONDS <= 120) { this.SNAPSHOT_HEARTBEAT_SECONDS = loaded.SNAPSHOT_HEARTBEAT_SECONDS; }
            else { invalid = true; }
        }
        this.FOG_BLEND_HOURS = 0.5;
        if (HCJsonFields.Has(image, "FOG_BLEND_HOURS"))
        {
            if (loaded.FOG_BLEND_HOURS >= 0.01 && loaded.FOG_BLEND_HOURS <= 7) { this.FOG_BLEND_HOURS = loaded.FOG_BLEND_HOURS; }
            else { invalid = true; }
        }
        this.BASELINE_FOG = 0.04;
        if (HCJsonFields.Has(image, "BASELINE_FOG"))
        {
            if (loaded.BASELINE_FOG >= 0 && loaded.BASELINE_FOG <= 1) { this.BASELINE_FOG = loaded.BASELINE_FOG; }
            else { invalid = true; }
        }
        this.SUMMER_RAIN_SCALE = 0.5;
        if (HCJsonFields.Has(image, "SUMMER_RAIN_SCALE"))
        {
            if (loaded.SUMMER_RAIN_SCALE >= 0 && loaded.SUMMER_RAIN_SCALE <= 1) { this.SUMMER_RAIN_SCALE = loaded.SUMMER_RAIN_SCALE; }
            else { invalid = true; }
        }
        this.AUTUMN_RAIN_MIN = 0.45;
        if (HCJsonFields.Has(image, "AUTUMN_RAIN_MIN"))
        {
            if (loaded.AUTUMN_RAIN_MIN >= 0 && loaded.AUTUMN_RAIN_MIN <= 1) { this.AUTUMN_RAIN_MIN = loaded.AUTUMN_RAIN_MIN; }
            else { invalid = true; }
        }
        this.AUTUMN_FOG_MIN = 0.18;
        if (HCJsonFields.Has(image, "AUTUMN_FOG_MIN"))
        {
            if (loaded.AUTUMN_FOG_MIN >= 0 && loaded.AUTUMN_FOG_MIN <= 1) { this.AUTUMN_FOG_MIN = loaded.AUTUMN_FOG_MIN; }
            else { invalid = true; }
        }
        this.WINTER_FOG_MIN = 0.08;
        if (HCJsonFields.Has(image, "WINTER_FOG_MIN"))
        {
            if (loaded.WINTER_FOG_MIN >= 0 && loaded.WINTER_FOG_MIN <= 1) { this.WINTER_FOG_MIN = loaded.WINTER_FOG_MIN; }
            else { invalid = true; }
        }
        this.AUTUMN_CLOUD_MIN = 0.75;
        if (HCJsonFields.Has(image, "AUTUMN_CLOUD_MIN"))
        {
            if (loaded.AUTUMN_CLOUD_MIN >= 0 && loaded.AUTUMN_CLOUD_MIN <= 1) { this.AUTUMN_CLOUD_MIN = loaded.AUTUMN_CLOUD_MIN; }
            else { invalid = true; }
        }
        this.WINTER_CLOUD_MIN = 0.8;
        if (HCJsonFields.Has(image, "WINTER_CLOUD_MIN"))
        {
            if (loaded.WINTER_CLOUD_MIN >= 0 && loaded.WINTER_CLOUD_MIN <= 1) { this.WINTER_CLOUD_MIN = loaded.WINTER_CLOUD_MIN; }
            else { invalid = true; }
        }
        this.SNOW_CLOUD_THRESHOLD = 0.6;
        if (HCJsonFields.Has(image, "SNOW_CLOUD_THRESHOLD"))
        {
            if (loaded.SNOW_CLOUD_THRESHOLD >= 0 && loaded.SNOW_CLOUD_THRESHOLD <= 1) { this.SNOW_CLOUD_THRESHOLD = loaded.SNOW_CLOUD_THRESHOLD; }
            else { invalid = true; }
        }
        this.WINTER_SNOWFALL = 0.55;
        if (HCJsonFields.Has(image, "WINTER_SNOWFALL"))
        {
            if (loaded.WINTER_SNOWFALL >= 0 && loaded.WINTER_SNOWFALL <= 1) { this.WINTER_SNOWFALL = loaded.WINTER_SNOWFALL; }
            else { invalid = true; }
        }
        this.SPRING_GRADE = 0.06;
        if (HCJsonFields.Has(image, "SPRING_GRADE"))
        {
            if (loaded.SPRING_GRADE >= 0 && loaded.SPRING_GRADE <= 1) { this.SPRING_GRADE = loaded.SPRING_GRADE; }
            else { invalid = true; }
        }
        this.SUMMER_GRADE = 0.04;
        if (HCJsonFields.Has(image, "SUMMER_GRADE"))
        {
            if (loaded.SUMMER_GRADE >= 0 && loaded.SUMMER_GRADE <= 1) { this.SUMMER_GRADE = loaded.SUMMER_GRADE; }
            else { invalid = true; }
        }
        this.AUTUMN_GRADE = 0.14;
        if (HCJsonFields.Has(image, "AUTUMN_GRADE"))
        {
            if (loaded.AUTUMN_GRADE >= 0 && loaded.AUTUMN_GRADE <= 1) { this.AUTUMN_GRADE = loaded.AUTUMN_GRADE; }
            else { invalid = true; }
        }
        this.WINTER_GRADE = 0.12;
        if (HCJsonFields.Has(image, "WINTER_GRADE"))
        {
            if (loaded.WINTER_GRADE >= 0 && loaded.WINTER_GRADE <= 1) { this.WINTER_GRADE = loaded.WINTER_GRADE; }
            else { invalid = true; }
        }
        this.AutumnRainCloudThreshold = 0.65;
        if (HCJsonFields.Has(image, "AutumnRainCloudThreshold"))
        {
            if (loaded.AutumnRainCloudThreshold >= 0 && loaded.AutumnRainCloudThreshold <= 1) { this.AutumnRainCloudThreshold = loaded.AutumnRainCloudThreshold; }
            else { invalid = true; }
        }
        this.FogDayStartHour = 5;
        if (HCJsonFields.Has(image, "FogDayStartHour"))
        {
            if (loaded.FogDayStartHour >= 0 && loaded.FogDayStartHour <= 12) { this.FogDayStartHour = loaded.FogDayStartHour; }
            else { invalid = true; }
        }
        this.FogDayEndHour = 20;
        if (HCJsonFields.Has(image, "FogDayEndHour"))
        {
            if (loaded.FogDayEndHour >= 12 && loaded.FogDayEndHour <= 24) { this.FogDayEndHour = loaded.FogDayEndHour; }
            else { invalid = true; }
        }
        if (!(this.SNAPSHOT_HEARTBEAT_SECONDS < this.SNAPSHOT_TTL_SECONDS))
        {
            this.SNAPSHOT_HEARTBEAT_SECONDS = 30.0;
            this.SNAPSHOT_TTL_SECONDS = 90.0;
            invalid = true;
        }
        if (!(this.FOG_BLEND_HOURS * 2 < this.FogDayEndHour - this.FogDayStartHour))
        {
            this.FOG_BLEND_HOURS = 0.5;
            this.FogDayEndHour = 20;
            this.FogDayStartHour = 5;
            invalid = true;
        }
        if (invalid) { Print("[HC Config] seasons reason=invalid_tuning defaults_retained runtime=PENDING"); }
    }
}

class HCc2PresentationConfig
{
    static const int READ_LIMIT = 8192;
    int GradeDefaultPercent = 60;
    float GradeDawnHour = 8;
    float GradeDawnBlendHours = 2;
    float GradeDuskHour = 18;
    float GradeDuskBlendHours = 4;
    float GradeCloudWeight = 0.45;
    float GradeFogWeight = 0.25;
    float GradeRainWeight = 0.3;
    float GradeDesaturation = 0.12;
    float GradeDampDesaturation = 0.1;
    float GradeTintRed = 0.025;
    float GradeDampTintRed = 0.015;
    float GradeTintGreen = 0.005;
    float GradeTintBlue = 0.012;
    float GradeContrast = 0.025;
    float GradeDampContrast = 0.015;
    float GradeVignette = 0.025;
    float GradeDampVignette = 0.025;
    float LightDawnStart = 5;
    float LightDawnEnd = 6;
    float LightDuskStart = 19;
    float LightDuskEnd = 20;
    float DuskStart = 16;
    float DuskPeak = 18;
    float DuskEnd = 20;
    float DuskColdHour = 18.5;
    float CloudThreshold = 0.55;
    float FogCloudWeight = 0.15;
    float StormThreshold = 0.65;
    float StormBand = 0.15;
    float CloudBand = 0.25;
    float StormWeightBase = 0.12;
    float StormWeightGain = 0.38;
    float CloudWeight = 0.35;
    float DuskWeight = 0.3;
    float BlendStep = 0.1;
    float HowlGapMinSeconds = 600;
    float HowlGapMaxSeconds = 900;
    float LayerGapMinSeconds = 180;
    float LayerGapMaxSeconds = 300;
    float SoundStartupSeconds = 45;
    float SoundVolume = 0.2;
    protected static ref HCc2PresentationConfig s_Config;

    static HCc2PresentationConfig HCGet()
    {
        if (!HCc2PresentationConfig.s_Config) { HCc2PresentationConfig.s_Config = HCc2PresentationConfig.HCLoad(); }
        return HCc2PresentationConfig.s_Config;
    }

    static void HCSet(HCc2PresentationConfig config) { HCc2PresentationConfig.s_Config = config; }

    static HCc2PresentationConfig HCLoad()
    {
        HCc2PresentationConfig defaults = new HCc2PresentationConfig;
        // Clients never read their local tuning file, including before receipt.
        if (!GetGame() || !GetGame().IsServer()) { return defaults; }
        string path = "$profile:HollowCountry/atmosphere-presentation.json";
        if (!FileExist(path)) { return defaults; }
        string image;
        string error;
        HCc2PresentationConfig loaded;
        if (!HCGroupIO.Read(path, HCc2PresentationConfig.READ_LIMIT, image) || !JsonFileLoader<HCc2PresentationConfig>.LoadData(image, loaded, error) || !loaded)
        {
            Print("[HC Config] atmosphere-presentation reason=read_or_json defaults_retained runtime=PENDING");
            return defaults;
        }
        defaults.HCApply(image, loaded);
        return defaults;
    }

    void HCApply(string image, HCc2PresentationConfig loaded)
    {
        bool invalid = false;
        this.GradeDefaultPercent = 60;
        if (HCJsonFields.Has(image, "GradeDefaultPercent"))
        {
            if (loaded.GradeDefaultPercent >= 0 && loaded.GradeDefaultPercent <= 100 && loaded.GradeDefaultPercent % 10 == 0) { this.GradeDefaultPercent = loaded.GradeDefaultPercent; }
            else { invalid = true; }
        }
        this.GradeDawnHour = 8;
        if (HCJsonFields.Has(image, "GradeDawnHour"))
        {
            if (loaded.GradeDawnHour >= 0 && loaded.GradeDawnHour <= 12) { this.GradeDawnHour = loaded.GradeDawnHour; }
            else { invalid = true; }
        }
        this.GradeDawnBlendHours = 2;
        if (HCJsonFields.Has(image, "GradeDawnBlendHours"))
        {
            if (loaded.GradeDawnBlendHours >= 0.01 && loaded.GradeDawnBlendHours <= 12) { this.GradeDawnBlendHours = loaded.GradeDawnBlendHours; }
            else { invalid = true; }
        }
        this.GradeDuskHour = 18;
        if (HCJsonFields.Has(image, "GradeDuskHour"))
        {
            if (loaded.GradeDuskHour >= 12 && loaded.GradeDuskHour <= 24) { this.GradeDuskHour = loaded.GradeDuskHour; }
            else { invalid = true; }
        }
        this.GradeDuskBlendHours = 4;
        if (HCJsonFields.Has(image, "GradeDuskBlendHours"))
        {
            if (loaded.GradeDuskBlendHours >= 0.01 && loaded.GradeDuskBlendHours <= 12) { this.GradeDuskBlendHours = loaded.GradeDuskBlendHours; }
            else { invalid = true; }
        }
        this.GradeCloudWeight = 0.45;
        if (HCJsonFields.Has(image, "GradeCloudWeight"))
        {
            if (loaded.GradeCloudWeight >= 0 && loaded.GradeCloudWeight <= 1) { this.GradeCloudWeight = loaded.GradeCloudWeight; }
            else { invalid = true; }
        }
        this.GradeFogWeight = 0.25;
        if (HCJsonFields.Has(image, "GradeFogWeight"))
        {
            if (loaded.GradeFogWeight >= 0 && loaded.GradeFogWeight <= 1) { this.GradeFogWeight = loaded.GradeFogWeight; }
            else { invalid = true; }
        }
        this.GradeRainWeight = 0.3;
        if (HCJsonFields.Has(image, "GradeRainWeight"))
        {
            if (loaded.GradeRainWeight >= 0 && loaded.GradeRainWeight <= 1) { this.GradeRainWeight = loaded.GradeRainWeight; }
            else { invalid = true; }
        }
        this.GradeDesaturation = 0.12;
        if (HCJsonFields.Has(image, "GradeDesaturation"))
        {
            if (loaded.GradeDesaturation >= 0 && loaded.GradeDesaturation <= 1) { this.GradeDesaturation = loaded.GradeDesaturation; }
            else { invalid = true; }
        }
        this.GradeDampDesaturation = 0.1;
        if (HCJsonFields.Has(image, "GradeDampDesaturation"))
        {
            if (loaded.GradeDampDesaturation >= 0 && loaded.GradeDampDesaturation <= 1) { this.GradeDampDesaturation = loaded.GradeDampDesaturation; }
            else { invalid = true; }
        }
        this.GradeTintRed = 0.025;
        if (HCJsonFields.Has(image, "GradeTintRed"))
        {
            if (loaded.GradeTintRed >= 0 && loaded.GradeTintRed <= 1) { this.GradeTintRed = loaded.GradeTintRed; }
            else { invalid = true; }
        }
        this.GradeDampTintRed = 0.015;
        if (HCJsonFields.Has(image, "GradeDampTintRed"))
        {
            if (loaded.GradeDampTintRed >= 0 && loaded.GradeDampTintRed <= 1) { this.GradeDampTintRed = loaded.GradeDampTintRed; }
            else { invalid = true; }
        }
        this.GradeTintGreen = 0.005;
        if (HCJsonFields.Has(image, "GradeTintGreen"))
        {
            if (loaded.GradeTintGreen >= 0 && loaded.GradeTintGreen <= 1) { this.GradeTintGreen = loaded.GradeTintGreen; }
            else { invalid = true; }
        }
        this.GradeTintBlue = 0.012;
        if (HCJsonFields.Has(image, "GradeTintBlue"))
        {
            if (loaded.GradeTintBlue >= 0 && loaded.GradeTintBlue <= 1) { this.GradeTintBlue = loaded.GradeTintBlue; }
            else { invalid = true; }
        }
        this.GradeContrast = 0.025;
        if (HCJsonFields.Has(image, "GradeContrast"))
        {
            if (loaded.GradeContrast >= 0 && loaded.GradeContrast <= 1) { this.GradeContrast = loaded.GradeContrast; }
            else { invalid = true; }
        }
        this.GradeDampContrast = 0.015;
        if (HCJsonFields.Has(image, "GradeDampContrast"))
        {
            if (loaded.GradeDampContrast >= 0 && loaded.GradeDampContrast <= 1) { this.GradeDampContrast = loaded.GradeDampContrast; }
            else { invalid = true; }
        }
        this.GradeVignette = 0.025;
        if (HCJsonFields.Has(image, "GradeVignette"))
        {
            if (loaded.GradeVignette >= 0 && loaded.GradeVignette <= 1) { this.GradeVignette = loaded.GradeVignette; }
            else { invalid = true; }
        }
        this.GradeDampVignette = 0.025;
        if (HCJsonFields.Has(image, "GradeDampVignette"))
        {
            if (loaded.GradeDampVignette >= 0 && loaded.GradeDampVignette <= 1) { this.GradeDampVignette = loaded.GradeDampVignette; }
            else { invalid = true; }
        }
        this.LightDawnStart = 5;
        if (HCJsonFields.Has(image, "LightDawnStart"))
        {
            if (loaded.LightDawnStart >= 0 && loaded.LightDawnStart <= 12) { this.LightDawnStart = loaded.LightDawnStart; }
            else { invalid = true; }
        }
        this.LightDawnEnd = 6;
        if (HCJsonFields.Has(image, "LightDawnEnd"))
        {
            if (loaded.LightDawnEnd >= 0.01 && loaded.LightDawnEnd <= 12) { this.LightDawnEnd = loaded.LightDawnEnd; }
            else { invalid = true; }
        }
        this.LightDuskStart = 19;
        if (HCJsonFields.Has(image, "LightDuskStart"))
        {
            if (loaded.LightDuskStart >= 12 && loaded.LightDuskStart <= 23.99) { this.LightDuskStart = loaded.LightDuskStart; }
            else { invalid = true; }
        }
        this.LightDuskEnd = 20;
        if (HCJsonFields.Has(image, "LightDuskEnd"))
        {
            if (loaded.LightDuskEnd >= 12 && loaded.LightDuskEnd <= 24) { this.LightDuskEnd = loaded.LightDuskEnd; }
            else { invalid = true; }
        }
        this.DuskStart = 16;
        if (HCJsonFields.Has(image, "DuskStart"))
        {
            if (loaded.DuskStart >= 0 && loaded.DuskStart <= 23) { this.DuskStart = loaded.DuskStart; }
            else { invalid = true; }
        }
        this.DuskPeak = 18;
        if (HCJsonFields.Has(image, "DuskPeak"))
        {
            if (loaded.DuskPeak >= 0.01 && loaded.DuskPeak <= 23.99) { this.DuskPeak = loaded.DuskPeak; }
            else { invalid = true; }
        }
        this.DuskEnd = 20;
        if (HCJsonFields.Has(image, "DuskEnd"))
        {
            if (loaded.DuskEnd >= 0.02 && loaded.DuskEnd <= 24) { this.DuskEnd = loaded.DuskEnd; }
            else { invalid = true; }
        }
        this.DuskColdHour = 18.5;
        if (HCJsonFields.Has(image, "DuskColdHour"))
        {
            if (loaded.DuskColdHour >= 0 && loaded.DuskColdHour <= 24) { this.DuskColdHour = loaded.DuskColdHour; }
            else { invalid = true; }
        }
        this.CloudThreshold = 0.55;
        if (HCJsonFields.Has(image, "CloudThreshold"))
        {
            if (loaded.CloudThreshold >= 0 && loaded.CloudThreshold <= 0.99) { this.CloudThreshold = loaded.CloudThreshold; }
            else { invalid = true; }
        }
        this.FogCloudWeight = 0.15;
        if (HCJsonFields.Has(image, "FogCloudWeight"))
        {
            if (loaded.FogCloudWeight >= 0 && loaded.FogCloudWeight <= 1) { this.FogCloudWeight = loaded.FogCloudWeight; }
            else { invalid = true; }
        }
        this.StormThreshold = 0.65;
        if (HCJsonFields.Has(image, "StormThreshold"))
        {
            if (loaded.StormThreshold >= 0 && loaded.StormThreshold <= 0.99) { this.StormThreshold = loaded.StormThreshold; }
            else { invalid = true; }
        }
        this.StormBand = 0.15;
        if (HCJsonFields.Has(image, "StormBand"))
        {
            if (loaded.StormBand >= 0 && loaded.StormBand <= 1) { this.StormBand = loaded.StormBand; }
            else { invalid = true; }
        }
        this.CloudBand = 0.25;
        if (HCJsonFields.Has(image, "CloudBand"))
        {
            if (loaded.CloudBand >= 0 && loaded.CloudBand <= 1) { this.CloudBand = loaded.CloudBand; }
            else { invalid = true; }
        }
        this.StormWeightBase = 0.12;
        if (HCJsonFields.Has(image, "StormWeightBase"))
        {
            if (loaded.StormWeightBase >= 0 && loaded.StormWeightBase <= 1) { this.StormWeightBase = loaded.StormWeightBase; }
            else { invalid = true; }
        }
        this.StormWeightGain = 0.38;
        if (HCJsonFields.Has(image, "StormWeightGain"))
        {
            if (loaded.StormWeightGain >= 0 && loaded.StormWeightGain <= 1) { this.StormWeightGain = loaded.StormWeightGain; }
            else { invalid = true; }
        }
        this.CloudWeight = 0.35;
        if (HCJsonFields.Has(image, "CloudWeight"))
        {
            if (loaded.CloudWeight >= 0 && loaded.CloudWeight <= 1) { this.CloudWeight = loaded.CloudWeight; }
            else { invalid = true; }
        }
        this.DuskWeight = 0.3;
        if (HCJsonFields.Has(image, "DuskWeight"))
        {
            if (loaded.DuskWeight >= 0 && loaded.DuskWeight <= 1) { this.DuskWeight = loaded.DuskWeight; }
            else { invalid = true; }
        }
        this.BlendStep = 0.1;
        if (HCJsonFields.Has(image, "BlendStep"))
        {
            if (loaded.BlendStep >= 0.001 && loaded.BlendStep <= 1) { this.BlendStep = loaded.BlendStep; }
            else { invalid = true; }
        }
        this.HowlGapMinSeconds = 600;
        if (HCJsonFields.Has(image, "HowlGapMinSeconds"))
        {
            if (loaded.HowlGapMinSeconds >= 1 && loaded.HowlGapMinSeconds <= 86400) { this.HowlGapMinSeconds = loaded.HowlGapMinSeconds; }
            else { invalid = true; }
        }
        this.HowlGapMaxSeconds = 900;
        if (HCJsonFields.Has(image, "HowlGapMaxSeconds"))
        {
            if (loaded.HowlGapMaxSeconds >= 1 && loaded.HowlGapMaxSeconds <= 86400) { this.HowlGapMaxSeconds = loaded.HowlGapMaxSeconds; }
            else { invalid = true; }
        }
        this.LayerGapMinSeconds = 180;
        if (HCJsonFields.Has(image, "LayerGapMinSeconds"))
        {
            if (loaded.LayerGapMinSeconds >= 1 && loaded.LayerGapMinSeconds <= 86400) { this.LayerGapMinSeconds = loaded.LayerGapMinSeconds; }
            else { invalid = true; }
        }
        this.LayerGapMaxSeconds = 300;
        if (HCJsonFields.Has(image, "LayerGapMaxSeconds"))
        {
            if (loaded.LayerGapMaxSeconds >= 1 && loaded.LayerGapMaxSeconds <= 86400) { this.LayerGapMaxSeconds = loaded.LayerGapMaxSeconds; }
            else { invalid = true; }
        }
        this.SoundStartupSeconds = 45;
        if (HCJsonFields.Has(image, "SoundStartupSeconds"))
        {
            if (loaded.SoundStartupSeconds >= 0 && loaded.SoundStartupSeconds <= 3600) { this.SoundStartupSeconds = loaded.SoundStartupSeconds; }
            else { invalid = true; }
        }
        this.SoundVolume = 0.2;
        if (HCJsonFields.Has(image, "SoundVolume"))
        {
            if (loaded.SoundVolume >= 0 && loaded.SoundVolume <= 1) { this.SoundVolume = loaded.SoundVolume; }
            else { invalid = true; }
        }
        if (!(this.LightDawnStart < this.LightDawnEnd && this.LightDawnEnd <= this.LightDuskStart && this.LightDuskStart < this.LightDuskEnd))
        {
            this.LightDawnStart = 5;
            this.LightDawnEnd = 6;
            this.LightDuskStart = 19;
            this.LightDuskEnd = 20;
            invalid = true;
        }
        if (!(this.DuskStart < this.DuskPeak && this.DuskPeak < this.DuskEnd))
        {
            this.DuskStart = 16;
            this.DuskPeak = 18;
            this.DuskEnd = 20;
            invalid = true;
        }
        if (!(this.HowlGapMinSeconds <= this.HowlGapMaxSeconds))
        {
            this.HowlGapMinSeconds = 600;
            this.HowlGapMaxSeconds = 900;
            invalid = true;
        }
        if (!(this.LayerGapMinSeconds <= this.LayerGapMaxSeconds))
        {
            this.LayerGapMinSeconds = 180;
            this.LayerGapMaxSeconds = 300;
            invalid = true;
        }
        if (this.GradeDesaturation + this.GradeDampDesaturation * (this.GradeCloudWeight + this.GradeFogWeight + this.GradeRainWeight) > 1)
        {
            this.GradeDesaturation = 0.12;
            this.GradeDampDesaturation = 0.1;
            invalid = true;
        }
        if (this.GradeTintRed + this.GradeDampTintRed * (this.GradeCloudWeight + this.GradeFogWeight + this.GradeRainWeight) > 1)
        {
            this.GradeTintRed = 0.025;
            this.GradeDampTintRed = 0.015;
            invalid = true;
        }
        if (this.GradeContrast + this.GradeDampContrast * (this.GradeCloudWeight + this.GradeFogWeight + this.GradeRainWeight) > 1)
        {
            this.GradeContrast = 0.025;
            this.GradeDampContrast = 0.015;
            invalid = true;
        }
        if (this.GradeVignette + this.GradeDampVignette * (this.GradeCloudWeight + this.GradeFogWeight + this.GradeRainWeight) > 1)
        {
            this.GradeVignette = 0.025;
            this.GradeDampVignette = 0.025;
            invalid = true;
        }
        if (this.StormWeightBase + this.StormWeightGain > 1)
        {
            this.StormWeightBase = 0.12;
            this.StormWeightGain = 0.38;
            invalid = true;
        }
        if (invalid) { Print("[HC Config] atmosphere-presentation reason=invalid_tuning defaults_retained runtime=PENDING"); }
    }
}
