// Local acceptance only; no production receipt has been earned.
// Installed API citations (snapshot root uses ~, never committed native sources):
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 2_GameLib/gameLib.c:4 GetGame; 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/Global/Game.c:934 GetWorldName(); 1_Core/proto/EnString.c:171 ToLower;
// 1_Core/proto/EnSystem.c:397 FileExist, :417 OpenFile, :425 ReadFile,
// :443 CloseFile, :380 FileMode; 1_Core/proto/EnString.c:199 Length, :240 IndexOf;
// 1_Core/proto/EnConvert.c:44 int.AsciiToString;
// 1_Core/proto/EnDebug.c:96 Print. HCServer/HCSettings are authored interfaces.
class HCAtmosphereQualification
{
    protected static bool s_Probed;
    protected static bool s_OptIn;
    protected static bool s_WeatherProbed;
    protected static bool s_Delegated;
    protected static bool s_Reported;
    protected static bool s_WorldProbed;
    protected static bool s_WorldSupported;

    static bool Qualified()
    {
        return false;
    }

    static bool SupportedWorld()
    {
        if (!s_WorldProbed)
        {
            s_WorldProbed = true;
            string atmosphereWorld = GetGame().GetWorldName();
            atmosphereWorld.ToLower();
            s_WorldSupported = atmosphereWorld == "chernarusplus";
            if (!s_WorldSupported)
                Print("[HollowCountry][Atmosphere] BLOCKED unsupported map; ChernarusPlus only; no atmosphere changes");
        }
        return s_WorldSupported;
    }

    static bool LocalOptIn()
    {
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_Probed)
        {
            s_Probed = true;
            s_OptIn = FileExist("$profile:HollowCountry/acceptance/atmosphere.enable");
            if (s_OptIn)
                Print("[HollowCountry][Atmosphere] EXPERIMENTAL local acceptance opt-in; runtime acceptance PENDING; restart required to change marker");
            else
                Print("[HollowCountry][Atmosphere] PENDING native acceptance; no atmosphere.enable marker; vanilla weather retained");
        }
        return s_OptIn;
    }

    static bool DelegatedWeather()
    {
        if (s_WeatherProbed)
            return s_Delegated;
        s_WeatherProbed = true;
        // Require the generator's canonical disabled root, not a substring
        // that could appear in a comment. No general-purpose XML parser.
        FileHandle weatherHandle = OpenFile("$mission:cfgweather.xml", FileMode.READ);
        if (!weatherHandle)
        {
            Print("[HollowCountry][Atmosphere] BLOCKED missing delegated cfgweather.xml; generate v1-script candidate; vanilla retained");
            return false;
        }
        string weatherDocument;
        ReadFile(weatherHandle, weatherDocument, 65537);
        CloseFile(weatherHandle);
        int quoteCode = 34;
        string quoteMark = quoteCode.AsciiToString();
        string disabledPrefix = "<?xml version='1.0' encoding='utf-8'?>\n<weather enable=" + quoteMark + "0" + quoteMark;
        disabledPrefix = disabledPrefix + " reset=" + quoteMark + "0" + quoteMark + ">";
        s_Delegated = weatherDocument.Length() <= 65536 && weatherDocument.IndexOf(disabledPrefix) == 0;
        if (!s_Delegated)
            Print("[HollowCountry][Atmosphere] BLOCKED XML ownership: use v1-script disabled XML without reset; no script weather or lighting applied");
        return s_Delegated;
    }

    static bool Enabled()
    {
        if (!GetGame() || !GetGame().IsServer())
            return false;
        HCServer atmosphereServer = HCServer.Get();
        if (!atmosphereServer || !atmosphereServer.IsStarted())
            return false;
        HCSettings atmosphereSettings = atmosphereServer.GetSettings();
        if (!atmosphereSettings || !atmosphereSettings.EnableAtmosphere)
        {
            if (!s_Reported)
            {
                s_Reported = true;
                Print("[HollowCountry][Atmosphere] DISABLED by settings; vanilla retained");
            }
            return false;
        }
        if (!HCAtmosphereQualification.SupportedWorld())
            return false;
        if (!HCAtmosphereQualification.Qualified() && !HCAtmosphereQualification.LocalOptIn())
            return false;
        return HCAtmosphereQualification.DelegatedWeather();
    }
}
