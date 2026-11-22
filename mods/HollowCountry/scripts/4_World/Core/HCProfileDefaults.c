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

    static string ReadText(string path, bool reportTooLarge = true)
    {
        // Open once: an absent/unreadable file already fails here. Callers
        // require the completed text synchronously, including loadout readback.
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle) { return ""; }
        string text;
        int count = ReadFile(handle, text, MAX_BYTES + 1);
        CloseFile(handle);
        if (count > MAX_BYTES || text.Length() > MAX_BYTES)
        {
            // Log only a relative addon/profile path, never a host path. The
            // bounded read reports observed bytes (at least MAX_BYTES + 1).
            string relative = "unknown";
            int prefix = path.IndexOf("data/defaults/");
            string missionRoot = "$mission:hollow-country/";
            if (prefix >= 0) { relative = path.Substring(prefix + 14, path.Length() - prefix - 14); }
            else if (path.IndexOf(PROFILE_ROOT) == 0) { relative = path.Substring(PROFILE_ROOT.Length(), path.Length() - PROFILE_ROOT.Length()); }
            else if (path.IndexOf(missionRoot) == 0) { relative = path.Substring(missionRoot.Length(), path.Length() - missionRoot.Length()); }
            if (reportTooLarge) { Print("[HollowCountry] profile default refused reason=too_large path=" + relative + " bytes=" + count.ToString()); }
            return "";
        }
        if (count < 1 || text.Length() < 1) { return ""; }
        return text;
    }

    static bool WriteText(string path, string text)
    {
        if (text.Length() < 1 || text.Length() > MAX_BYTES) { return false; }
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle) { return false; }
        // Keep the synchronous copy/readback contract until its callers own a
        // durable continuation. As in HCStagedSaveImage, stay below the observed
        // native FPrint transfer cap: <=256 chunks for the 1 MiB input ceiling.
        int offset = 0;
        int total = text.Length();
        while (offset < total)
        {
            int length = total - offset;
            if (length > 4096) { length = 4096; }
            string piece = text.Substring(offset, length);
            if (piece.Length() != length) { CloseFile(handle); return false; }
            FPrint(handle, piece);
            offset = offset + length;
        }
        CloseFile(handle);
        return ReadText(path) == text;
    }

    // Creates each missing parent directory of a profile-relative file.
    static bool PrepareParents(string relative)
    {
        // Same bound as Valid (MAX_RELATIVE); every caller already passed Valid.
        if (relative.Length() > 160) { return false; }
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root)) { return false; }
        // At most 8 nested folders: a constant-trip loop, one
        // FileExist (and at most one MakeDirectory) per level. A deeper path is
        // refused, never silently truncated.
        int from = 0;
        for (int level = 0; level < 8; level++)
        {
            int slash = relative.IndexOfFrom(from, "/");
            if (slash < 0) { return true; }
            string folder = root + "/" + relative.Substring(0, slash);
            if (!FileExist(folder) && !MakeDirectory(folder)) { return false; }
            from = slash + 1;
        }
        if (relative.IndexOfFrom(from, "/") < 0) { return true; }
        Print("[HC Profile] default parent folders refused reason=path_too_deep max_levels=8 relative_chars=" + relative.Length().ToString());
        return false;
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

    // Synchronous completion: callers may read the profile immediately. Only
    // our verified first-copy marker permits repair of an existing torn copy.
    static bool Ensure(string relative, string shippedRoot)
    {
        if (!Valid(relative)) { return false; }
        string target = PROFILE_ROOT + relative;
        string provisionPath = target + ".hcdefault.provision";
        bool exists = FileExist(target);
        if (exists && !FileExist(provisionPath)) { return true; }
        string shipped = shippedRoot + relative;
        string text = ReadText(shipped);
        if (text == "")
        {
            Print("[HollowCountry] profile default unavailable file=" + relative + "; feature keeps its own admission diagnostic");
            return false;
        }
        string temporary = target + ".hcdefault.tmp";
        bool repair = false;
        if (exists)
        {
            string profile = ReadText(target);
            string intent = ReadText(provisionPath);
            if (profile == text)
            {
                if (FileExist(temporary) && ReadText(temporary) == text)
                {
                    if (!DeleteFile(temporary))
                    {
                        Print("[HollowCountry] profile default refused file=" + relative + " reason=tmp_delete");
                        return false;
                    }
                }
                if (!DeleteFile(provisionPath))
                {
                    Print("[HollowCountry] profile default refused file=" + relative + " reason=provision_delete");
                    return false;
                }
                return true;
            }
            if (intent == "") { return true; }
            // A completed older image remains valid operator-visible data.
            // Retire its receipt so later warm boots take the existence path.
            if (profile == intent)
            {
                if (!DeleteFile(provisionPath))
                {
                    Print("[HollowCountry] profile default refused file=" + relative + " reason=provision_delete");
                    return false;
                }
                return true;
            }
            repair = profile == "";
            if (repair)
            {
                FileHandle emptyHandle = OpenFile(target, FileMode.READ);
                if (!emptyHandle)
                {
                    Print("[HollowCountry] profile default refused file=" + relative + " reason=profile_unreadable");
                    return false;
                }
                string emptyProbe;
                int emptyBytes = ReadFile(emptyHandle, emptyProbe, 1);
                CloseFile(emptyHandle);
                if (emptyBytes != 0) { return true; }
            }
            if (!repair && profile.Length() < intent.Length())
            {
                repair = intent.Substring(0, profile.Length()) == profile;
            }
            if (!repair) { return true; }
        }
        if (!PrepareParents(relative))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=directory");
            return false;
        }
        // This first-copy marker is distinct from HCXAIRespawnDefaults' origin:
        // its origin means COMPLETED adoption and must not precede target copy.
        // Our marker proves an absent/torn target was ours, until readback.
        bool intentOk = WriteText(temporary, text);
        // Keep a verified repair marker intact across retries: rewriting it
        // could tear the only authority while the target is still a prefix.
        if (intentOk && !repair) { intentOk = WriteText(provisionPath, text); }
        if (!intentOk)
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=intent_readback");
            return false;
        }
        if (exists && !DeleteFile(target))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=target_delete");
            return false;
        }
        // After deleting the torn target, refresh an older marker before the
        // new copy. A crash while refreshing leaves an absent target, so the
        // next boot can safely provision again even if the marker is torn.
        if (repair && !WriteText(provisionPath, text))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=intent_readback");
            return false;
        }
        if (!CopyFile(temporary, target) || ReadText(target) != text)
        {
            // Keep intent and provenance until target readback succeeds.
            Print("[HollowCountry] profile default refused file=" + relative + " reason=write_readback");
            return false;
        }
        if (!DeleteFile(temporary))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=tmp_delete");
            return false;
        }
        if (!DeleteFile(provisionPath))
        {
            Print("[HollowCountry] profile default refused file=" + relative + " reason=provision_delete");
            return false;
        }
        string mode = "fresh";
        if (repair) { mode = "resume_interrupted"; }
        int bytes = text.Length();
        Print("[HollowCountry] profile default provisioned file=" + relative + " bytes=" + bytes.ToString() + " mode=" + mode + " source=pbo");
        return true;
    }

    static bool EnsureBase(string relative)
    {
        return Ensure(relative, PBO_ROOT);
    }
}
