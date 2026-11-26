// Native scripts-1.30.164289: gameplay.c:104-117 ScriptRPC.Send;
// 1_Core/proto/Serializer.c:57-58 Read/Write. Separate from command tickets.
// Hard bounds: 32 peers, 128 chunks * 64 rows, 48 layer names, 384 draw pins.
class HCAdminWorldWire
{
    // 4853913 is HCSeasonSnapshotRPC.RPC_SEASON (docs/ACCEPTANCE_CHECKLIST.md); these two ids were free (2026-11-26).
    static const int REQUEST = 4853915;
    static const int REPLY = 4853916;
    static const int ROWS = 8192;
    static const int CHUNK = 64;
    static const int DRAW = 384;
}
class HCAdminWorldRequest
{
    int Session;
    bool Open;
    string LootFilter;
    int StaticVersion;
    vector Centre;
    float Scale;
}
class HCAdminWorldReply
{
    int Session;
    int Sequence;
    int Chunk;
    bool Last;
    bool IsStatic;
    int CatalogRevision;
    int DrawLimit;
    int Total;
    int Truncated;
    ref array<ref HCAdminMark> Marks = new array<ref HCAdminMark>;
}

modded class HCOperatorSettingsRegistry
{
    protected static bool s_AdminWorldRegistered;
    static void HCAdminWorldInit()
    {
        HCInit();
        if (s_AdminWorldRegistered) { return; }
        s_AdminWorldRegistered = true;
        HCAdd("AdminWorld.RefreshSeconds", "int", 4, 3, 30, "HCAdminWorldConfig");
        HCAdd("AdminWorld.RowsPerTick", "int", 32, 1, 64, "HCAdminWorldConfig");
        HCAdd("AdminWorld.MaxRows", "int", 8192, 512, 8192, "HCAdminWorldConfig");
        HCAdd("AdminWorld.MaxDraw", "int", 384, 64, 384, "HCAdminWorldConfig");
    }
}
