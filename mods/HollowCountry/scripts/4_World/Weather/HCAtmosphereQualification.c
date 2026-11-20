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

    // Windowed searches never copy/rescan the remaining XML document per token.
    // HCTextWindow uses inspected EnString.c:113/:448 Substring/Get (1.30.164289).
    static int HCXmlFind(HCTextWindow text, int start, string token)
    {
        int size = token.Length();
        for (int index = start; index + size <= text.Length(); index++)
        {
            if (text.Range(index, size) == token) { return index; }
        }
        return -1;
    }

    // Value of one attribute; skip quoted values to avoid matching names in values.
    static string HCXmlAttribute(string tag, string name)
    {
        HCTextWindow window = new HCTextWindow(tag);
        int length = window.Length();
        int index = 0;
        int quoteCode = 34;
        string quote = quoteCode.AsciiToString();
        while (index < length)
        {
            string ch = window.At(index);
            int next;
            int close;
            if (ch == "'" || ch == quote)
            {
                close = HCXmlFind(window, index + 1, ch);
                if (close < 0) { return "?"; }
                index = close + 1;
                continue;
            }
            if (!HCXmlNameChar(ch)) { index++; continue; }
            int stop = index;
            while (stop < length && HCXmlNameChar(window.At(stop))) { stop++; }
            // Root attribute names are compared once, without copying a tail.
            bool matches = stop - index == name.Length() && window.Range(index, stop - index) == name;
            index = stop;
            if (!matches) { continue; }
            if (stop + 2 >= length) { return "?"; }
            ch = window.At(stop);
            string mark = window.At(stop + 1);
            if (ch != "=" || (mark != "'" && mark != quote)) { return "?"; }
            next = stop + 2;
            close = HCXmlFind(window, next, mark);
            if (close < 0) { return "?"; }
            return window.Range(next, close - next);
        }
        return "";
    }

    // At most 64 prolog items, a 1024-character root tag and a 64 KiB document.
    // Retains the original root/attribute acceptance and malformed-input refusals.
    static bool DisabledXmlRoot(string document)
    {
        int total = document.Length();
        if (total < 1 || total > 65536) { return false; }
        string text = document;
        text.ToLower();
        total = text.Length();
        if (total < 1 || total > 65536) { return false; }
        HCTextWindow window = new HCTextWindow(text);
        int cursor = 0;
        for (int steps = 0; steps < 64; steps++)
        {
            if (cursor < 0 || cursor >= total) { return false; }
            cursor = HCXmlFind(window, cursor, "<");
            if (cursor < 0) { return false; }
            int close;
            if (window.Range(cursor, 2) == "<?")
            {
                close = HCXmlFind(window, cursor, "?>");
                if (close < 0) { return false; }
                cursor = close + 2;
                continue;
            }
            if (window.Range(cursor, 4) == "<!--")
            {
                close = HCXmlFind(window, cursor, "-->");
                if (close < 0) { return false; }
                cursor = close + 3;
                continue;
            }
            if (window.Range(cursor, 8) != "<weather" || total - cursor < 9) { return false; }
            if (HCXmlNameChar(window.At(cursor + 8))) { return false; }
            close = HCXmlFind(window, cursor, ">");
            if (close < cursor + 8 || close - cursor > 1024) { return false; }
            string tag = window.Range(cursor + 8, close - cursor - 8);
            string enable = HCXmlAttribute(tag, "enable");
            string reset = HCXmlAttribute(tag, "reset");
            if (enable != "0" && enable != "false") { return false; }
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
