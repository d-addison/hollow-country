// Dev-only test addon (never shipped). Step file model, result codes and the single log
// writer of the scripted client driver. Shared contract: the step file is written by
// tools/testing/driver_script.py, which validates every field this loader reads.
// Native scripts-1.30.164289 proofs: 3_Game/tools/JsonFileLoader.c:7 LoadFile(path, out data,
// out error); 1_Core/proto/EnSystem.c:397 FileExist; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnString.c Length/Substring/IndexOf. One line per step, one summary line per run.
// The driver never prints a player name, id or path and never touches HCUse or any counter.
class HCDriverResult
{
    static const int RUNNING = 0;
    static const int OK = 1;
    static const int REFUSED = 2;
    static const int UNSUPPORTED = 3;
    static const int TIMEOUT = 4;

    static string Name(int code)
    {
        if (code == HCDriverResult.OK) { return "ok"; }
        if (code == HCDriverResult.REFUSED) { return "refused"; }
        if (code == HCDriverResult.UNSUPPORTED) { return "unsupported"; }
        if (code == HCDriverResult.TIMEOUT) { return "timeout"; }
        return "running";
    }
}

class HCDriverArgs
{
    string item1;
    string item2;
    string type;
    string item;
    string target;
    string freq;
}

class HCDriverStep
{
    string id;
    string kind;
    float seconds;
    ref array<float> to;
    string gait;
    float arrive_m;
    float timeout_s;
    string name;
    string cmd;
    string value;
    string op;
    ref HCDriverArgs args;
}

class HCDriverScript
{
    int version;
    string run_id;
    ref array<ref HCDriverStep> steps;
}

class HCDriverFile
{
    static const string PATH = "$profile:HollowCountry/acceptance/client_driver.json";
    static const int MAX_STEPS = 400;

    // Returns "" when the script is usable, otherwise a short reason. A missing file is the
    // inert case and is reported by the caller as reason=no-step-file.
    static string Load(out HCDriverScript script)
    {
        if (!FileExist(HCDriverFile.PATH)) { return "no-step-file"; }
        string error;
        if (!JsonFileLoader<HCDriverScript>.LoadFile(HCDriverFile.PATH, script, error) || !script) { return "bad-json"; }
        if (script.version != 1) { return "bad-version"; }
        if (!script.steps || script.steps.Count() < 1 || script.steps.Count() > HCDriverFile.MAX_STEPS) { return "bad-steps"; }
        return "";
    }
}

class HCDriverLog
{
    static void Step(string id, string kind, int code, string detail)
    {
        Print("" + "[HC Driver] step=" + id + " kind=" + kind + " result=" + HCDriverResult.Name(code) + " detail=" + HCDriverLog.Clean(detail));
    }

    static void Inert(string reason)
    {
        Print("" + "[HC Driver] inert reason=" + reason);
    }

    static void Done(string run, int steps, int ok, int refused, int unsupported, int timeout)
    {
        Print("" + "[HC Driver] done run=" + run + " steps=" + steps.ToString() + " ok=" + ok.ToString() + " refused=" + refused.ToString() + " unsupported=" + unsupported.ToString() + " timeout=" + timeout.ToString());
    }

    // Details stay one short token line: no spaces that would break key=value parsing beyond
    // the detail tail, bounded length.
    static string Clean(string text)
    {
        if (text.Length() > 160) { text = text.Substring(0, 160); }
        return text;
    }
}
