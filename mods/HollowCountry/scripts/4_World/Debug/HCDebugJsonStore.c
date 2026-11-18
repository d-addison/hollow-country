// W5 #122. Bounded once per completed capture, <=1MiB (no per-frame I/O).
// Native scripts-1.30.164289: 3_Game/tools/JsonFileLoader.c:85 MakeData;
// 1_Core/proto/EnSystem.c:397,528,531 FileExist/DeleteFile/CopyFile;
// EnString.c:199 Length; EnConvert.c:30 ToString. HCGroupIO reuses native
// EnSystem.c:417,425,443,462 OpenFile/ReadFile/CloseFile/FPrint readback.
// Same temp/backup/copy protocol as HCV2ThreatStore. Raw text seam avoids
// declaring a forbidden field named map. All dynamic JSON uses native encoding.
// No native atomic rename primitive exists; interruptions retain .tmp intent.
class HCDebugJsonStore
{
    static bool HCSave(string path, HCDebugDocument data, int limit, out int bytes)
    {
        bytes = 0;
        string layerJson;
        string routeJson;
        string error;
        if (!JsonFileLoader<map<string, ref array<ref HCDebugPoint>>>.MakeData(data.layers, layerJson, error, false)) { return false; }
        if (!JsonFileLoader<array<ref HCDebugRoute>>.MakeData(data.routes, routeJson, error, false)) { return false; }
        string text = "{\"version\":1,\"time\":" + data.time.ToString() + ",\"map\":\"chernarusplus\",\"layers\":" + layerJson + ",\"routes\":" + routeJson + "}";
        return HCSaveText(path, text, limit, bytes);
    }

    // Candidate for promotion to Core as a shared bounded raw-JSON store seam.
    // Existing HCGroupIO owns write/read verification; no new file reader here.
    static bool HCSaveText(string path, string text, int limit, out int bytes)
    {
        bytes = 0;
        string temporary = path + ".tmp";
        string backup = path + ".bak";
        if (!HCGroupIO.WriteNew(temporary, text, limit)) { return false; }
        if (FileExist(path))
        {
            string previous;
            string backedUp;
            if (!HCGroupIO.Read(path, limit, previous)) { return false; }
            if (FileExist(backup) && !DeleteFile(backup)) { return false; }
            if (!CopyFile(path, backup)) { return false; }
            if (!HCGroupIO.Read(backup, limit, backedUp) || backedUp != previous) { return false; }
            if (!DeleteFile(path)) { return false; }
        }
        if (!CopyFile(temporary, path)) { return false; }
        string actual;
        if (!HCGroupIO.Read(path, limit, actual) || actual != text) { return false; }
        if (!DeleteFile(temporary)) { return false; }
        bytes = text.Length();
        return true;
    }
}
