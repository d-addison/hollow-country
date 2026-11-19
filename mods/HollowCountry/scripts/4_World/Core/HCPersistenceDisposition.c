// HC-28: operator-attested stopped pair, NOT an engine generation oracle.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 1_Core/proto/EnString.c:199,223 Length/Hash; EnConvert.c:30 ToString;
// EnDebug.c:96 Print; 3_Game/Global/Game.c:1120
// IsServer, :934 GetWorldName; JsonFileLoader.c:69 LoadData via HCGroupJson.
// IO/readback evidence is on HCGroupIO; EnSystem.c:525/528/531 supplies
// MakeDirectory/DeleteFile/CopyFile. No atomic rename/fsync/native snapshot API.
class HCRecoveryHCReceipt
{
    int Version;
    int Generation;
    string WorldName;
    bool PairedRestore;
    string NativeBackupId;
    int WorldLength;
    int WorldHash;
    int EscalationLength;
    int EscalationHash;
    int GroupRevision;
    int GroupLength;
    int GroupHash;
}

class HCRecoveryNativeReceipt
{
    int Version;
    int Generation;
    string WorldName;
    bool StoppedPairAttested;
    string NativeBackupId;
}

class HCPersistenceDisposition
{
    protected static bool s_Loaded;
    protected static bool s_LoadOK;
    protected static bool s_WorldStarted;
    protected static bool s_EscalationStarted;
    protected static bool s_GroupsStarted;

    // Modules register before their admission attempt, including refusals, so
    // only the last module Stop removes the session marker after all flushes.
    static void HCStartStore(string name)
    {
        if (name == "world") { s_WorldStarted = true; }
        if (name == "escalation") { s_EscalationStarted = true; }
        if (name == "groups") { s_GroupsStarted = true; }
    }

    static void HCStopStore(string name)
    {
        HCRecoveryGate.HCClose(name);
        if (name == "world") { s_WorldStarted = false; }
        if (name == "escalation") { s_EscalationStarted = false; }
        if (name == "groups") { s_GroupsStarted = false; }
        if (!s_WorldStarted && !s_EscalationStarted && !s_GroupsStarted) { HCStop(); }
    }

    // Module call sites share one load before admission. No receipt is needed for a normal
    // boot. An optional stopped-pair attestation is verified and consumed once.
    static bool HCLoad(bool enableWorld = true)
    {
        if (s_Loaded) { return s_LoadOK; }
        s_Loaded = true;
        s_LoadOK = false;
        HCRecoveryGate.HCReset();
        if (!GetGame() || !GetGame().IsServer()) { return HCRefuseRestore("server_required"); }
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return HCRefuseRestore("profile_unavailable"); }
        if (FileExist("$profile:HollowCountry/recovery-active.intent"))
        {
            Print("[HC Plan] HC-28 warning=unclosed_native_session action=validate_each_store runtime=PENDING");
        }
        bool hasHC = FileExist("$profile:HollowCountry/recovery-hc.json");
        bool hasNative = FileExist("$profile:HollowCountry/recovery-native.json");
        int generation = 0;
        string suffix;
        if (hasHC || hasNative)
        {
            HCRecoveryHCReceipt hc;
            HCRecoveryNativeReceipt nativeReceipt;
            if (!hasHC || !hasNative) { return HCRefuseRestore("partial_restore_attestation"); }
            if (!HCGroupJson<HCRecoveryHCReceipt>.Load("$profile:HollowCountry/recovery-hc.json", 4096, hc) || !hc) { return HCRefuseRestore("hc_receipt_corrupt"); }
            if (!HCGroupJson<HCRecoveryNativeReceipt>.Load("$profile:HollowCountry/recovery-native.json", 2048, nativeReceipt) || !nativeReceipt) { return HCRefuseRestore("native_receipt_corrupt"); }
            if (hc.Version != 1 || nativeReceipt.Version != 1 || hc.Generation < 1 || hc.Generation > 1000000000 || hc.GroupRevision < 0 || hc.GroupRevision > 1000000000) { return HCRefuseRestore("receipt_schema_or_identity"); }
            if (hc.Generation != nativeReceipt.Generation || hc.NativeBackupId != nativeReceipt.NativeBackupId) { return HCRefuseRestore("generation_mismatch"); }
            if (hc.WorldName != GetGame().GetWorldName() || nativeReceipt.WorldName != hc.WorldName) { return HCRefuseRestore("world_mismatch"); }
            if (!hc.PairedRestore || !nativeReceipt.StoppedPairAttested || hc.NativeBackupId.Length() < 1 || hc.NativeBackupId.Length() > 128) { return HCRefuseRestore("paired_restore_required"); }
            if (enableWorld)
            {
                if (!HCMatchImage("$profile:HollowCountry/world.json", 1048576, hc.WorldLength, hc.WorldHash)) { return HCRefuseRestore("world_pair_image_mismatch"); }
                if (!HCMatchImage("$profile:HollowCountry/escalation.json", 2048, hc.EscalationLength, hc.EscalationHash)) { return HCRefuseRestore("escalation_pair_image_mismatch"); }
            }
            if (hc.GroupRevision > 0)
            {
                string groupPath = "$profile:HollowCountry/Groups/state/state_" + hc.GroupRevision.ToString() + ".json";
                if (!HCMatchImage(groupPath, 1048576, hc.GroupLength, hc.GroupHash)) { return HCRefuseRestore("group_pair_image_mismatch"); }
            }
            if (hc.GroupRevision == 0 && (hc.GroupLength != 0 || hc.GroupHash != 0)) { return HCRefuseRestore("empty_group_attestation_invalid"); }
            int now = HCGroupClock.Utc();
            if (now < 1) { return HCRefuseRestore("restore_utc_unavailable"); }
            suffix = ".consumed-" + now.ToString();
            generation = hc.Generation;
        }
        // A stale intent is evidence to warn about, never evidence of damage.
        // Keep it until clean Stop; do not truncate it to start another session.
        if (!FileExist("$profile:HollowCountry/recovery-active.intent") && !HCGroupIO.WriteNew("$profile:HollowCountry/recovery-active.intent", generation.ToString(), 32)) { return HCRefuseRestore("session_intent_failed"); }
        if (hasHC || hasNative)
        {
            // Installed EnSystem.c:528/531 has no RenameFile. Logical rename:
            // preserve BOTH archives and verify before removing either source.
            // Failure retains evidence and refuses restore, never a data rollback.
            if (!HCArchive("$profile:HollowCountry/recovery-hc.json", suffix, 4096) || !HCArchive("$profile:HollowCountry/recovery-native.json", suffix, 2048)) { return HCRefuseRestore("attestation_archive_failed"); }
            if (!DeleteFile("$profile:HollowCountry/recovery-hc.json") || !DeleteFile("$profile:HollowCountry/recovery-native.json")) { return HCRefuseRestore("attestation_consume_incomplete"); }
        }
        HCRecoveryGate.HCAdmit(generation);
        s_LoadOK = true;
        HCReport();
        return true;
    }

    static bool HCArchive(string path, string suffix, int limit)
    {
        string original;
        string archived;
        if (!HCGroupIO.HCReadRaw(path, limit, original) || FileExist(path + suffix)) { return false; }
        if (!CopyFile(path, path + suffix)) { return false; }
        return HCGroupIO.HCReadRaw(path + suffix, limit, archived) && archived == original;
    }

    static bool HCMatchImage(string path, int limit, int length, int checksum)
    {
        if (length == 0 && checksum == 0) { return !FileExist(path); }
        if (length < 1 || length > limit) { return false; }
        string text;
        return HCGroupIO.HCReadRaw(path, limit, text) && text.Length() == length && text.Hash() == checksum;
    }

    static bool HCAdmitStore(string name) { return HCRecoveryGate.HCReady(name); }
    static bool HCQuarantine(string name, string reason) { return HCRecoveryGate.HCRefuse(name, reason); }

    // An invalid optional attestation refuses this startup without labelling
    // any player file corrupt. Operator evidence remains at its original path.
    static bool HCRefuseRestore(string reason)
    {
        Print("[HC Plan] HC-28 recovery=attestation_refused reason=" + reason + " quarantine=0 runtime=PENDING");
        return false;
    }

    static void HCStop()
    {
        s_Loaded = false;
        s_LoadOK = false;
        s_WorldStarted = false;
        s_EscalationStarted = false;
        s_GroupsStarted = false;
        HCRecoveryGate.HCClose("world");
        HCRecoveryGate.HCClose("escalation");
        HCRecoveryGate.HCClose("groups");
        // Called after all module flushes, including healthy stores when a
        // different store has faulted. This is not a native-save attestation.
        if (FileExist("$profile:HollowCountry/recovery-active.intent") && !DeleteFile("$profile:HollowCountry/recovery-active.intent"))
        {
            Print("[HC Plan] HC-28 warning=session_intent_cleanup_failed runtime=PENDING");
        }
    }

    static void HCReport()
    {
        string line = "[HC Plan] HC-28 generation=" + HCRecoveryGate.HCGeneration().ToString();
        line += " recovery=validate_each_store quarantine=" + HCRecoveryGate.HCQuarantined().ToString();
        Print(line + " state=admitted reason=" + HCRecoveryGate.HCReason() + " native_generation=unobserved runtime=PENDING");
    }
}
