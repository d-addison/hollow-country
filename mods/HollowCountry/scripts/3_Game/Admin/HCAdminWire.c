// W6 #123/#133. Installed scripts-1.30.164289 native evidence:
// gameplay.c:104-117 ScriptRPC/Send; 1_Core/proto/Serializer.c:57-58 Write/Read.
// Allocations are request-only; <=512 point/route vertices, <=64 status lines.
// RPC scan of all mods/ on 2026-11-18: 4853701..703, 4853801..802,
// 4853862, 4853901..903 occupied. These two ids were unused.
class HCAdminWire
{
    static const int REQUEST = 4853911;
    static const int REPLY = 4853912;
    static const int MENU = 48539;

    // Text command registration uses the existing bounded Command string. The
    // integer-only catalog cards cannot collect a class filter (lead UI wiring).
    // Native EnString.c:240 IndexOf, :199 Length. No new RPC or wire field.
    static bool HCIsLootMap(string command)
    {
        if (command == "lootmap") { return true; }
        return command.Length() <= 104 && command.IndexOf("lootmap ") == 0;
    }
}

class HCAdminRequest
{
    int Ticket;
    string Command;
    int Value;
}

class HCAdminMark
{
    string Layer;
    vector Position;
    string Label;
    string Detail;
    // Consecutive vertices with the same nonzero Route form a polyline.
    int Route;
}

class HCAdminReply
{
    int Ticket;
    bool Authorized;
    bool Snapshot;
    string Notice;
    ref array<string> Lines = new array<string>;
    ref array<ref HCAdminMark> Marks = new array<ref HCAdminMark>;
}

class HCAdminAllowlist
{
    ref array<string> PlainIds = new array<string>;
}
