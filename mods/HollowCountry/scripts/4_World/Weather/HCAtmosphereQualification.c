// Local acceptance only; no production receipt has been earned.
// Installed API citations (snapshot root uses ~, never committed native sources):
// ~/.cache/hollow-country/native-scripts/scripts-1.30.164289/
// 2_GameLib/gameLib.c:4 GetGame; 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/Global/Game.c:934 GetWorldName(), :942 GetVersion(out string);
// 1_Core/proto/EnString.c:171 ToLower, :113 Substring;
// 1_Core/proto/EnConvert.c:44 int.AsciiToString;
// 1_Core/proto/EnSystem.c:397 FileExist, :417 OpenFile, :425 ReadFile,
// :443 CloseFile, :380 FileMode; 1_Core/proto/EnString.c:199 Length, :240 IndexOf;
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
            string v;
            GetGame().GetVersion(v);
            s_WorldSupported = s_WorldSupported && HCBuildIdentity.Matches(v);
            if (!s_WorldSupported)
                Print("[HollowCountry][Atmosphere] BLOCKED unsupported map/build; ChernarusPlus on " + HCBuildIdentity.Canonical() + " only; no atmosphere changes");
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
            s_OptIn = !FileExist("$profile:HollowCountry/acceptance/atmosphere.disable");
            Print(HCV1Admission.Line("Atmosphere", s_OptIn, "atmosphere", HCAtmosphereQualification.Qualified()) + "; restart required to change marker");
        }
        return s_OptIn;
    }

    // XML name characters after ToLower; anything else separates tokens.
    static bool HCXmlNameChar(string ch)
    {
        string nameChars = "abcdefghijklmnopqrstuvwxyz0123456789-_.:";
        if (ch.Length() != 1)
            return false;
        return nameChars.IndexOf(ch) >= 0;
    }

    // Value of one attribute in a lowercased start-tag body, skipping quoted
    // values so a name inside another value never matches. "" = absent,
    // "?" = malformed (unterminated quote or unquoted value).
    static string HCXmlAttribute(string tag, string name)
    {
        int length = tag.Length();
        int index = 0;
        int next = 0;
        int stop = 0;
        int close = 0;
        string ch = "";
        string tail = "";
        string attribute = "";
        string mark = "";
        int quoteCode = 34;
        string quote = quoteCode.AsciiToString();
        while (index < length)
        {
            ch = tag.Substring(index, 1);
            if (ch == "'" || ch == quote)
            {
                next = index + 1;
                tail = tag.Substring(next, length - next);
                close = tail.IndexOf(ch);
                if (close < 0)
                    return "?";
                index = next + close + 1;
                continue;
            }
            if (!HCAtmosphereQualification.HCXmlNameChar(ch))
            {
                index = index + 1;
                continue;
            }
            stop = index;
            while (stop < length)
            {
                ch = tag.Substring(stop, 1);
                if (!HCAtmosphereQualification.HCXmlNameChar(ch))
                    break;
                stop = stop + 1;
            }
            attribute = tag.Substring(index, stop - index);
            index = stop;
            if (attribute != name)
                continue;
            if (stop + 2 >= length)
                return "?";
            ch = tag.Substring(stop, 1);
            next = stop + 1;
            mark = tag.Substring(next, 1);
            if (ch != "=" || (mark != "'" && mark != quote))
                return "?";
            next = stop + 2;
            tail = tag.Substring(next, length - next);
            close = tail.IndexOf(mark);
            if (close < 0)
                return "?";
            return tail.Substring(0, close);
        }
        return "";
    }

    // True only when the first element after <?...?> declarations and
    // <!--...--> comments is <weather ...> with enable 0/false and reset absent
    // or 0/false (the stock mission and generator forms). Commented-out roots,
    // other roots, doctype/CDATA and malformed attributes refuse. Bounded: at
    // most 64 prolog items and a 1024-character root tag of a 64 KiB document.
    static bool DisabledXmlRoot(string document)
    {
        int total = document.Length();
        if (total < 1 || total > 65536)
            return false;
        string text = document;
        text.ToLower();
        int cursor = 0;
        int steps = 0;
        int open = 0;
        int close = 0;
        string rest = "";
        string tag = "";
        string enable = "";
        string reset = "";
        while (steps < 64)
        {
            steps = steps + 1;
            rest = text.Substring(cursor, total - cursor);
            open = rest.IndexOf("<");
            if (open < 0)
                return false;
            cursor = cursor + open;
            rest = text.Substring(cursor, total - cursor);
            if (rest.IndexOf("<?") == 0)
            {
                close = rest.IndexOf("?>");
                if (close < 0)
                    return false;
                cursor = cursor + close + 2;
                continue;
            }
            if (rest.IndexOf("<!--") == 0)
            {
                close = rest.IndexOf("-->");
                if (close < 0)
                    return false;
                cursor = cursor + close + 3;
                continue;
            }
            if (rest.IndexOf("<weather") != 0 || rest.Length() < 9)
                return false;
            tag = rest.Substring(8, 1);
            if (HCAtmosphereQualification.HCXmlNameChar(tag))
                return false;
            close = rest.IndexOf(">");
            if (close < 8 || close > 1024)
                return false;
            tag = rest.Substring(8, close - 8);
            enable = HCAtmosphereQualification.HCXmlAttribute(tag, "enable");
            reset = HCAtmosphereQualification.HCXmlAttribute(tag, "reset");
            if (enable != "0" && enable != "false")
                return false;
            return reset == "" || reset == "0" || reset == "false";
        }
        return false;
    }

    static bool DelegatedWeather()
    {
        if (s_WeatherProbed)
            return s_Delegated;
        s_WeatherProbed = true;
        // The script owns weather when the mission has no cfgweather.xml, or
        // when its root disables the XML controller (stock vanilla missions
        // ship <weather reset="0" enable="0">). No general-purpose XML parser.
        FileHandle weatherHandle = OpenFile("$mission:cfgweather.xml", FileMode.READ);
        if (!weatherHandle)
        {
            s_Delegated = !FileExist("$mission:cfgweather.xml");
            if (s_Delegated)
                Print("[HollowCountry][Atmosphere] cfgweather.xml absent; no XML weather controller, script weather owner");
            else
                Print(HCV1Admission.Refused("Atmosphere", "atmosphere", "cfgweather.xml present but unreadable; vanilla weather retained"));
            return s_Delegated;
        }
        string weatherDocument;
        ReadFile(weatherHandle, weatherDocument, 65537);
        CloseFile(weatherHandle);
        s_Delegated = HCAtmosphereQualification.DisabledXmlRoot(weatherDocument);
        if (!s_Delegated)
            Print(HCV1Admission.Refused("Atmosphere", "atmosphere", "cfgweather.xml root weather enable is not 0, reset is 1, or the root is unreadable; the XML controller owns weather; no script weather or lighting applied"));
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
