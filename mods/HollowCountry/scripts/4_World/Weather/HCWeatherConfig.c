// C2 optional tuning; missing keys retain authored defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// Bounded read through HCGroupIO (EnSystem.c:417/425/443). No profile writes.
// Loaded once per process; restart to apply changes. No new tick work or RPC.
class HCWeatherConfig
{
    static const int READ_LIMIT = 8192;
    int BadDayBuckets = 1;
    int FogMorningBuckets = 3;
    float FogStartHour = 5;
    float FogPeakHour = 7;
    float FogEndHour = 9;
    float FogBaseline = 0.04;
    float FogMorningLevel = 0.6;
    float NightStartHour = 20;
    float NightEndHour = 5;
    float NightCloudCap = 0.55;
    float StormCloud = 0.95;
    float WetCloud = 0.72;
    float RainCloudThreshold = 0.65;
    float StormCloudThreshold = 0.85;
    float StormDurationSeconds = 90.0;
    float RainStopSeconds = 90.0;
    float MorningFogLift = 0.2;
    float CalmCloud = 0.25;
    float PlainCloud = 0.35;
    float BadCloud = 0.98;
    float BadRain = 0.9;
    float StormRain = 0.85;
    float WetRain = 0.25;
    float CalmWind = 2;
    float NightWind = 4;
    float BadWind = 16;
    float StormWind = 14;
    float WetWind = 8;
    float PlainWind = 4;
    float CycleSeconds = 7200;
    float BadStormStartSeconds = 1800;
    float WetStartSeconds = 2700;
    float StormStartSeconds = 3600;
    float StormEndSeconds = 5400;
    float BadWindCloudThreshold = 0.65;
    float WetEndRainThreshold = 0.02;
    float CalmHours = 3;
    float StormWindDirection = 0.8;
    float PlainWindDirection = -1.2;
    float DistanceBase = 0.015;
    float DistanceMorningLift = 0.04;
    float DistanceCloudLift = 0.01;
    float HeightBase = 50;
    float HeightMorningLift = 40;
    float WindDampingDivisor = 20;
    protected static ref HCWeatherConfig s_Config;

    static HCWeatherConfig HCGet()
    {
        if (!HCWeatherConfig.s_Config) { HCWeatherConfig.s_Config = HCWeatherConfig.HCLoad(); }
        return HCWeatherConfig.s_Config;
    }

    static void HCSet(HCWeatherConfig config) { HCWeatherConfig.s_Config = config; }

    static HCWeatherConfig HCLoad()
    {
        HCWeatherConfig defaults = new HCWeatherConfig;
        string path = "$profile:HollowCountry/weather.json";
        if (!FileExist(path)) { return defaults; }
        string image;
        string error;
        HCWeatherConfig loaded;
        if (!HCGroupIO.Read(path, HCWeatherConfig.READ_LIMIT, image) || !JsonFileLoader<HCWeatherConfig>.LoadData(image, loaded, error) || !loaded)
        {
            Print("[HC Config] weather reason=read_or_json defaults_retained runtime=PENDING");
            return defaults;
        }
        defaults.HCApply(image, loaded);
        return defaults;
    }

    void HCApply(string image, HCWeatherConfig loaded)
    {
        bool invalid = false;
        this.BadDayBuckets = 1;
        if (HCJsonFields.Has(image, "BadDayBuckets"))
        {
            if (loaded.BadDayBuckets >= 0 && loaded.BadDayBuckets <= 5) { this.BadDayBuckets = loaded.BadDayBuckets; }
            else { invalid = true; }
        }
        this.FogMorningBuckets = 3;
        if (HCJsonFields.Has(image, "FogMorningBuckets"))
        {
            if (loaded.FogMorningBuckets >= 0 && loaded.FogMorningBuckets <= 5) { this.FogMorningBuckets = loaded.FogMorningBuckets; }
            else { invalid = true; }
        }
        this.FogStartHour = 5;
        if (HCJsonFields.Has(image, "FogStartHour"))
        {
            if (loaded.FogStartHour >= 0 && loaded.FogStartHour <= 23) { this.FogStartHour = loaded.FogStartHour; }
            else { invalid = true; }
        }
        this.FogPeakHour = 7;
        if (HCJsonFields.Has(image, "FogPeakHour"))
        {
            if (loaded.FogPeakHour >= 0 && loaded.FogPeakHour <= 23.5) { this.FogPeakHour = loaded.FogPeakHour; }
            else { invalid = true; }
        }
        this.FogEndHour = 9;
        if (HCJsonFields.Has(image, "FogEndHour"))
        {
            if (loaded.FogEndHour >= 0.1 && loaded.FogEndHour <= 24) { this.FogEndHour = loaded.FogEndHour; }
            else { invalid = true; }
        }
        this.FogBaseline = 0.04;
        if (HCJsonFields.Has(image, "FogBaseline"))
        {
            if (loaded.FogBaseline >= 0 && loaded.FogBaseline <= 1) { this.FogBaseline = loaded.FogBaseline; }
            else { invalid = true; }
        }
        this.FogMorningLevel = 0.6;
        if (HCJsonFields.Has(image, "FogMorningLevel"))
        {
            if (loaded.FogMorningLevel >= 0 && loaded.FogMorningLevel <= 1) { this.FogMorningLevel = loaded.FogMorningLevel; }
            else { invalid = true; }
        }
        this.NightStartHour = 20;
        if (HCJsonFields.Has(image, "NightStartHour"))
        {
            if (loaded.NightStartHour >= 12 && loaded.NightStartHour <= 24) { this.NightStartHour = loaded.NightStartHour; }
            else { invalid = true; }
        }
        this.NightEndHour = 5;
        if (HCJsonFields.Has(image, "NightEndHour"))
        {
            if (loaded.NightEndHour >= 0 && loaded.NightEndHour <= 12) { this.NightEndHour = loaded.NightEndHour; }
            else { invalid = true; }
        }
        this.NightCloudCap = 0.55;
        if (HCJsonFields.Has(image, "NightCloudCap"))
        {
            if (loaded.NightCloudCap >= 0 && loaded.NightCloudCap <= 1) { this.NightCloudCap = loaded.NightCloudCap; }
            else { invalid = true; }
        }
        this.StormCloud = 0.95;
        if (HCJsonFields.Has(image, "StormCloud"))
        {
            if (loaded.StormCloud >= 0 && loaded.StormCloud <= 1) { this.StormCloud = loaded.StormCloud; }
            else { invalid = true; }
        }
        this.WetCloud = 0.72;
        if (HCJsonFields.Has(image, "WetCloud"))
        {
            if (loaded.WetCloud >= 0 && loaded.WetCloud <= 1) { this.WetCloud = loaded.WetCloud; }
            else { invalid = true; }
        }
        this.RainCloudThreshold = 0.65;
        if (HCJsonFields.Has(image, "RainCloudThreshold"))
        {
            if (loaded.RainCloudThreshold >= 0 && loaded.RainCloudThreshold <= 1) { this.RainCloudThreshold = loaded.RainCloudThreshold; }
            else { invalid = true; }
        }
        this.StormCloudThreshold = 0.85;
        if (HCJsonFields.Has(image, "StormCloudThreshold"))
        {
            if (loaded.StormCloudThreshold >= 0 && loaded.StormCloudThreshold <= 1) { this.StormCloudThreshold = loaded.StormCloudThreshold; }
            else { invalid = true; }
        }
        this.StormDurationSeconds = 90.0;
        if (HCJsonFields.Has(image, "StormDurationSeconds"))
        {
            if (loaded.StormDurationSeconds >= 1 && loaded.StormDurationSeconds <= 3600) { this.StormDurationSeconds = loaded.StormDurationSeconds; }
            else { invalid = true; }
        }
        this.RainStopSeconds = 90.0;
        if (HCJsonFields.Has(image, "RainStopSeconds"))
        {
            if (loaded.RainStopSeconds >= 1 && loaded.RainStopSeconds <= 3600) { this.RainStopSeconds = loaded.RainStopSeconds; }
            else { invalid = true; }
        }
        this.MorningFogLift = 0.2;
        if (HCJsonFields.Has(image, "MorningFogLift"))
        {
            if (loaded.MorningFogLift >= 0 && loaded.MorningFogLift <= 1) { this.MorningFogLift = loaded.MorningFogLift; }
            else { invalid = true; }
        }
        this.CalmCloud = 0.25;
        if (HCJsonFields.Has(image, "CalmCloud"))
        {
            if (loaded.CalmCloud >= 0 && loaded.CalmCloud <= 1) { this.CalmCloud = loaded.CalmCloud; }
            else { invalid = true; }
        }
        this.PlainCloud = 0.35;
        if (HCJsonFields.Has(image, "PlainCloud"))
        {
            if (loaded.PlainCloud >= 0 && loaded.PlainCloud <= 1) { this.PlainCloud = loaded.PlainCloud; }
            else { invalid = true; }
        }
        this.BadCloud = 0.98;
        if (HCJsonFields.Has(image, "BadCloud"))
        {
            if (loaded.BadCloud >= 0 && loaded.BadCloud <= 1) { this.BadCloud = loaded.BadCloud; }
            else { invalid = true; }
        }
        this.BadRain = 0.9;
        if (HCJsonFields.Has(image, "BadRain"))
        {
            if (loaded.BadRain >= 0 && loaded.BadRain <= 1) { this.BadRain = loaded.BadRain; }
            else { invalid = true; }
        }
        this.StormRain = 0.85;
        if (HCJsonFields.Has(image, "StormRain"))
        {
            if (loaded.StormRain >= 0 && loaded.StormRain <= 1) { this.StormRain = loaded.StormRain; }
            else { invalid = true; }
        }
        this.WetRain = 0.25;
        if (HCJsonFields.Has(image, "WetRain"))
        {
            if (loaded.WetRain >= 0 && loaded.WetRain <= 1) { this.WetRain = loaded.WetRain; }
            else { invalid = true; }
        }
        this.CalmWind = 2;
        if (HCJsonFields.Has(image, "CalmWind"))
        {
            if (loaded.CalmWind >= 0 && loaded.CalmWind <= 16) { this.CalmWind = loaded.CalmWind; }
            else { invalid = true; }
        }
        this.NightWind = 4;
        if (HCJsonFields.Has(image, "NightWind"))
        {
            if (loaded.NightWind >= 0 && loaded.NightWind <= 16) { this.NightWind = loaded.NightWind; }
            else { invalid = true; }
        }
        this.BadWind = 16;
        if (HCJsonFields.Has(image, "BadWind"))
        {
            if (loaded.BadWind >= 0 && loaded.BadWind <= 16) { this.BadWind = loaded.BadWind; }
            else { invalid = true; }
        }
        this.StormWind = 14;
        if (HCJsonFields.Has(image, "StormWind"))
        {
            if (loaded.StormWind >= 0 && loaded.StormWind <= 16) { this.StormWind = loaded.StormWind; }
            else { invalid = true; }
        }
        this.WetWind = 8;
        if (HCJsonFields.Has(image, "WetWind"))
        {
            if (loaded.WetWind >= 0 && loaded.WetWind <= 16) { this.WetWind = loaded.WetWind; }
            else { invalid = true; }
        }
        this.PlainWind = 4;
        if (HCJsonFields.Has(image, "PlainWind"))
        {
            if (loaded.PlainWind >= 0 && loaded.PlainWind <= 16) { this.PlainWind = loaded.PlainWind; }
            else { invalid = true; }
        }
        this.CycleSeconds = 7200;
        if (HCJsonFields.Has(image, "CycleSeconds"))
        {
            if (loaded.CycleSeconds >= 60 && loaded.CycleSeconds <= 86400) { this.CycleSeconds = loaded.CycleSeconds; }
            else { invalid = true; }
        }
        this.BadStormStartSeconds = 1800;
        if (HCJsonFields.Has(image, "BadStormStartSeconds"))
        {
            if (loaded.BadStormStartSeconds >= 0 && loaded.BadStormStartSeconds <= 86400) { this.BadStormStartSeconds = loaded.BadStormStartSeconds; }
            else { invalid = true; }
        }
        this.WetStartSeconds = 2700;
        if (HCJsonFields.Has(image, "WetStartSeconds"))
        {
            if (loaded.WetStartSeconds >= 0 && loaded.WetStartSeconds <= 86400) { this.WetStartSeconds = loaded.WetStartSeconds; }
            else { invalid = true; }
        }
        this.StormStartSeconds = 3600;
        if (HCJsonFields.Has(image, "StormStartSeconds"))
        {
            if (loaded.StormStartSeconds >= 0 && loaded.StormStartSeconds <= 86400) { this.StormStartSeconds = loaded.StormStartSeconds; }
            else { invalid = true; }
        }
        this.StormEndSeconds = 5400;
        if (HCJsonFields.Has(image, "StormEndSeconds"))
        {
            if (loaded.StormEndSeconds >= 1 && loaded.StormEndSeconds <= 86400) { this.StormEndSeconds = loaded.StormEndSeconds; }
            else { invalid = true; }
        }
        this.BadWindCloudThreshold = 0.65;
        if (HCJsonFields.Has(image, "BadWindCloudThreshold"))
        {
            if (loaded.BadWindCloudThreshold >= 0 && loaded.BadWindCloudThreshold <= 1) { this.BadWindCloudThreshold = loaded.BadWindCloudThreshold; }
            else { invalid = true; }
        }
        this.WetEndRainThreshold = 0.02;
        if (HCJsonFields.Has(image, "WetEndRainThreshold"))
        {
            if (loaded.WetEndRainThreshold >= 0 && loaded.WetEndRainThreshold <= 1) { this.WetEndRainThreshold = loaded.WetEndRainThreshold; }
            else { invalid = true; }
        }
        this.CalmHours = 3;
        if (HCJsonFields.Has(image, "CalmHours"))
        {
            if (loaded.CalmHours >= 0 && loaded.CalmHours <= 24) { this.CalmHours = loaded.CalmHours; }
            else { invalid = true; }
        }
        this.StormWindDirection = 0.8;
        if (HCJsonFields.Has(image, "StormWindDirection"))
        {
            if (loaded.StormWindDirection >= -3.14159 && loaded.StormWindDirection <= 3.14159) { this.StormWindDirection = loaded.StormWindDirection; }
            else { invalid = true; }
        }
        this.PlainWindDirection = -1.2;
        if (HCJsonFields.Has(image, "PlainWindDirection"))
        {
            if (loaded.PlainWindDirection >= -3.14159 && loaded.PlainWindDirection <= 3.14159) { this.PlainWindDirection = loaded.PlainWindDirection; }
            else { invalid = true; }
        }
        this.DistanceBase = 0.015;
        if (HCJsonFields.Has(image, "DistanceBase"))
        {
            if (loaded.DistanceBase >= 0 && loaded.DistanceBase <= 1) { this.DistanceBase = loaded.DistanceBase; }
            else { invalid = true; }
        }
        this.DistanceMorningLift = 0.04;
        if (HCJsonFields.Has(image, "DistanceMorningLift"))
        {
            if (loaded.DistanceMorningLift >= 0 && loaded.DistanceMorningLift <= 1) { this.DistanceMorningLift = loaded.DistanceMorningLift; }
            else { invalid = true; }
        }
        this.DistanceCloudLift = 0.01;
        if (HCJsonFields.Has(image, "DistanceCloudLift"))
        {
            if (loaded.DistanceCloudLift >= 0 && loaded.DistanceCloudLift <= 1) { this.DistanceCloudLift = loaded.DistanceCloudLift; }
            else { invalid = true; }
        }
        this.HeightBase = 50;
        if (HCJsonFields.Has(image, "HeightBase"))
        {
            if (loaded.HeightBase >= 0 && loaded.HeightBase <= 1000) { this.HeightBase = loaded.HeightBase; }
            else { invalid = true; }
        }
        this.HeightMorningLift = 40;
        if (HCJsonFields.Has(image, "HeightMorningLift"))
        {
            if (loaded.HeightMorningLift >= 0 && loaded.HeightMorningLift <= 1000) { this.HeightMorningLift = loaded.HeightMorningLift; }
            else { invalid = true; }
        }
        this.WindDampingDivisor = 20;
        if (HCJsonFields.Has(image, "WindDampingDivisor"))
        {
            if (loaded.WindDampingDivisor >= 16 && loaded.WindDampingDivisor <= 100) { this.WindDampingDivisor = loaded.WindDampingDivisor; }
            else { invalid = true; }
        }
        if (!(this.FogStartHour < this.FogPeakHour && this.FogPeakHour < this.FogEndHour))
        {
            this.FogStartHour = 5;
            this.FogPeakHour = 7;
            this.FogEndHour = 9;
            invalid = true;
        }
        if (!(this.BadStormStartSeconds <= this.WetStartSeconds && this.WetStartSeconds < this.StormStartSeconds && this.StormStartSeconds < this.StormEndSeconds && this.StormEndSeconds < this.CycleSeconds))
        {
            this.BadStormStartSeconds = 1800;
            this.WetStartSeconds = 2700;
            this.StormStartSeconds = 3600;
            this.StormEndSeconds = 5400;
            this.CycleSeconds = 7200;
            invalid = true;
        }
        if (!(this.RainCloudThreshold <= this.StormCloudThreshold))
        {
            this.RainCloudThreshold = 0.65;
            this.StormCloudThreshold = 0.85;
            invalid = true;
        }
        if (invalid) { Print("[HC Config] weather reason=invalid_tuning defaults_retained runtime=PENDING"); }
    }
}
