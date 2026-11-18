// Self-provisioning of shipped profile defaults (owner report 2026-11-18: the
// Workshop install route has no deploy step, so a fresh $profile:HollowCountry
// lacks the default data files and features never appear). Defaults ship
// inside the addon PBO under <prefix>/data/defaults/<relative profile path>.
// An existing operator file is never overwritten or rewritten; a missing one is
// copied once from the PBO through temp/readback, or read in place (Resolve).
// Native evidence (scripts-1.30.164289): 1_Core/proto/EnSystem.c:397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile, :462 FPrint, :525 MakeDirectory,
// :528 DeleteFile, :531 CopyFile; PBO-path reads use the same calls as
// 3_Game/tools/JsonFileLoader.c:9-18 reading "scripts/data/notifications.json"
// for 3_Game/Client/Notifications/NotificationSystem.c:74,285.
class HCProfileDefaults
{
    static const string PROFILE_ROOT = "$profile:HollowCountry/";
    static const string PBO_ROOT = "HollowCountry/data/defaults/";
    static const int MAX_BYTES = 1048576;
    static const int MAX_RELATIVE = 160;

    // Relative profile paths only: no drive/scheme, no parent traversal, no
    // absolute or backslash forms, bounded length.
    static bool Valid(string relative)
    {
        int length = relative.Length();
        if (length < 1 || length > MAX_RELATIVE) { return false; }
        if (relative.IndexOf("..") >= 0 || relative.IndexOf(":") >= 0 || relative.IndexOf("\\") >= 0) { return false; }
        if (relative.Get(0) == "/" || relative.Get(length - 1) == "/") { return false; }
        return true;
    }

    static string ReadText(string path)
    {
        if (!FileExist(path)) { return ""; }
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string text;
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        if (count < 1 || count > MAX_BYTES || text.Length() < 1 || text.Length() > MAX_BYTES) { return ""; }
        return text;
    }

    static bool WriteText(string path, string text)
    {
        if (text.Length() < 1 || text.Length() > MAX_BYTES) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        FPrint(handle, text);
        CloseFile(handle);
        return ReadText(path) == text;
    }

    // Creates each missing parent directory of a profile-relative file.
    static bool PrepareParents(string relative)
    {
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root)) { return false; }
        int length = relative.Length();
        int index = 0;
        string folder = "";
        while (index < length)
        {
            if (relative.Get(index) == "/")
            {
                folder = root + "/" + relative.Substring(0, index);
                if (!FileExist(folder) && !MakeDirectory(folder)) { return false; }
            }
            index = index + 1;
        }
        return true;
    }

    // The path a reader should open: the operator's profile file when present,
    // otherwise the shipped default inside the PBO, otherwise "".
    static string Resolve(string relative, string shippedRoot)
    {
        if (!Valid(relative)) { return ""; }
        string profile = PROFILE_ROOT + relative;
        if (FileExist(profile)) { return profile; }
        string shipped = shippedRoot + relative;
        if (FileExist(shipped)) { return shipped; }
        return "";
    }

    // Copies the shipped default to $profile:HollowCountry/<relative> only when
    // the profile file is absent. Returns true when the profile file exists
    // afterwards (operator file kept, or default provisioned and read back).
    static bool Ensure(string relative, string shippedRoot)
    {
        if (!Valid(relative)) { return false; }
        string target = PROFILE_ROOT + relative;
        if (FileExist(target)) { return true; }
        string shipped = shippedRoot + relative;
        string text = ReadText(shipped);
        if (text == "")
        {
            Print("[HollowCountry] profile default missing file=" + relative + " source=" + shipped + "; feature keeps its own admission diagnostic");
            return false;
        }
        if (!PrepareParents(relative))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=directory");
            return false;
        }
        string temporary = target + ".hcdefault.tmp";
        // The target was absent before this copy, so a copy that fails readback is removed and retried next boot.
        bool provCopied = false;
        bool provOk = WriteText(temporary, text);
        if (provOk) { provCopied = CopyFile(temporary, target); provOk = provCopied; }
        if (provOk) { provOk = ReadText(target) == text; }
        if (!provOk)
        {
            DeleteFile(temporary);
            if (provCopied) { DeleteFile(target); }
            Print("[HollowCountry] profile default refused file=" + relative + " reason=write_readback");
            return false;
        }
        DeleteFile(temporary);
        int bytes = text.Length();
        Print("[HollowCountry] profile default provisioned file=" + relative + " bytes=" + bytes.ToString() + " source=pbo; operator files are never overwritten");
        return true;
    }

    static bool EnsureBase(string relative)
    {
        return Ensure(relative, PBO_ROOT);
    }
}
