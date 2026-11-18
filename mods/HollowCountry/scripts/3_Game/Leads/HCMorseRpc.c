// Issue #62 / LC-T307, EXP-S2. Native snapshot scripts-1.30.164289:
// 1_Core/proto/EnConvert.c:30 int.ToString; EnString.c:199,448 Length/Get.
// 3_Game/gameplay.c:104,117 ScriptRPC/Send; no client command RPC is exposed.
// Before allocation: rg -n '4853862' mods returned no matches (2026-11-17).
class HCMorseRpc
{
    static const int CLUE = 4853862;

    static string Grid(int east, int north)
    {
        return east.ToString() + "-" + north.ToString();
    }

    static string Word(int kind)
    {
        if (kind == HCEventFamily.RECOVERY) { return "CACHE"; }
        if (kind == HCEventFamily.DELIVERY) { return "COURIER"; }
        if (kind == HCEventFamily.INVESTIGATION) { return "SCOUT"; }
        if (kind == HCEventFamily.STATIC_SALVAGE) { return "WIRE"; }
        if (kind == HCEventFamily.AI_ENCOUNTER) { return "WATCH"; }
        if (kind == HCEventFamily.PRESENCE) { return "SIGNAL"; }
        if (kind == HCEventFamily.INFECTED_CLEAR) { return "DANGER"; }
        return "";
    }

    // Only the alphabet needed by E/N, code words and numeric 1 km cells.
    // Pulses use existing vanilla static, never copied audio or a global broadcast.
    static string Symbols(string letter)
    {
        if (letter == "0") { return "-----"; }
        if (letter == "1") { return ".----"; }
        if (letter == "2") { return "..---"; }
        if (letter == "3") { return "...--"; }
        if (letter == "4") { return "....-"; }
        if (letter == "5") { return "....."; }
        if (letter == "6") { return "-...."; }
        if (letter == "7") { return "--..."; }
        if (letter == "8") { return "---.."; }
        if (letter == "9") { return "----."; }
        if (letter == "A") { return ".-"; }
        if (letter == "C") { return "-.-."; }
        if (letter == "D") { return "-.."; }
        if (letter == "E") { return "."; }
        if (letter == "G") { return "--."; }
        if (letter == "H") { return "...."; }
        if (letter == "I") { return ".."; }
        if (letter == "L") { return ".-.."; }
        if (letter == "N") { return "-."; }
        if (letter == "O") { return "---"; }
        if (letter == "R") { return ".-."; }
        if (letter == "S") { return "..."; }
        if (letter == "T") { return "-"; }
        if (letter == "U") { return "..-"; }
        if (letter == "W") { return ".--"; }
        return "";
    }
}
