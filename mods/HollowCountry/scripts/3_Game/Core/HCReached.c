// Shared 3_Game API: no references to World classes. Native 1.30.164289:
// Game.c GetTickTime/IsServer; EnString.c Length/Substring/IndexOf;
// EnScript.c map Contains/Insert/Count (hashed: Mark runs on tick paths); EnConvert.c float/int ToString; EnDebug.c Print.
class HCReached
{
    protected static ref map<string, bool> s_Tokens = new map<string, bool>();
    protected static bool s_Begun;
    protected static bool s_Summarised;
    protected static float s_Start;
    protected static int s_OverflowCalls;

    // Once per script lifetime (boot), including a failed start followed by retry.
    static void Begin()
    {
        if (!s_Begun && GetGame() && GetGame().IsServer())
        {
            s_Begun = true;
            s_Start = GetGame().GetTickTime();
        }
    }

    // Bounded log token: never copy free text, paths or whitespace to these lines.
    static string Token(string value)
    {
        if (value.Length() > 64) { return HCReached.TokenShort(value.Substring(0, 64)); }
        return HCReached.TokenShort(value);
    }

    protected static string TokenShort(string value)
    {
        if (value.Length() > 64) { return "unknown"; }
        string allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-";
        string token = "";
        int length = value.Length();
        for (int i = 0; i < length; i++)
        {
            string character = value.Substring(i, 1);
            if (allowed.IndexOf(character) < 0) { character = "_"; }
            token = token + character;
        }
        if (token == "") { return "unknown"; }
        return token;
    }

    static void Mark(string feature)
    {
        if (!s_Begun || !GetGame() || !GetGame().IsServer()) { return; }
        if (s_Tokens.Contains(feature)) { return; }
        // Callers supply stable literal tokens. Reject invalid values, preventing
        // truncation collisions and accidental free-text/private values in the log.
        if (feature == "" || feature.Length() > 64 || HCReached.Token(feature) != feature) { return; }
        if (s_Tokens.Count() >= 64)
        {
            // Counts calls beyond capacity, not distinct rejected strings: retaining
            // an unbounded set just to deduplicate overflow would defeat the cap.
            if (s_OverflowCalls < 2147483647) { s_OverflowCalls++; }
            return;
        }
        s_Tokens.Insert(feature, true);
        float seconds = GetGame().GetTickTime() - s_Start;
        if (seconds < 0) { seconds = 0; }
        Print("[HC Reached] feature=" + feature + " first_s=" + seconds.ToString());
    }

    static void Summary()
    {
        if (s_Summarised || s_OverflowCalls == 0) { return; }
        s_Summarised = true;
        Print("[HC Reached Summary] token_cap=64 overflow_calls=" + s_OverflowCalls.ToString());
    }
}
