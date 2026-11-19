// HC-28: operator-attested stopped pair, NOT an engine generation oracle.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 1_Core/proto/EnString.c:199,223 Length/Hash; EnConvert.c:30 ToString;
// EnDebug.c:96 Print; 3_Game/Global/Game.c:1120
// IsServer, :934 GetWorldName; JsonFileLoader.c:69 LoadData via HCGroupJson.
// IO/readback evidence is on HCGroupIO. No rename/fsync/native snapshot API.
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
    // Lead calls once BEFORE feature admission on every server Start. No tick,
    // directory scan, automatic rollback, native inventory write or save loop.
    static bool HCLoad()
    {
        HCRecoveryGate.HCReset();
        if (!GetGame() || !GetGame().IsServer()) { return HCQuarantine("server_required"); }
        if (FileExist("$profile:HollowCountry/recovery-active.intent")) { return HCQuarantine("unclosed_native_session"); }
        if (FileExist("$profile:HollowCountry/world.json.tmp") || FileExist("$profile:HollowCountry/escalation.json.tmp")) { return HCQuarantine("interrupted_store_intent"); }
        HCRecoveryHCReceipt hc;
        HCRecoveryNativeReceipt nativeReceipt;
        if (!HCGroupJson<HCRecoveryHCReceipt>.Load("$profile:HollowCountry/recovery-hc.json", 4096, hc) || !hc) { return HCQuarantine("hc_receipt_missing_or_corrupt"); }
        if (!HCGroupJson<HCRecoveryNativeReceipt>.Load("$profile:HollowCountry/recovery-native.json", 2048, nativeReceipt) || !nativeReceipt) { return HCQuarantine("native_generation_unobservable"); }
        if (hc.Version != 1 || nativeReceipt.Version != 1 || hc.Generation < 1 || hc.Generation > 1000000000 || hc.GroupRevision < 1 || hc.GroupRevision > 1000000000) { return HCQuarantine("receipt_schema_or_identity"); }
        if (hc.Generation != nativeReceipt.Generation || hc.NativeBackupId != nativeReceipt.NativeBackupId) { return HCQuarantine("generation_mismatch"); }
        if (hc.WorldName != GetGame().GetWorldName() || nativeReceipt.WorldName != hc.WorldName) { return HCQuarantine("world_mismatch"); }
        if (!hc.PairedRestore || !nativeReceipt.StoppedPairAttested || hc.NativeBackupId.Length() < 1 || hc.NativeBackupId.Length() > 128) { return HCQuarantine("paired_restore_required"); }
        string groupPath = "$profile:HollowCountry/Groups/state/state_" + hc.GroupRevision.ToString() + ".json";
        if (!HCMatchImage("$profile:HollowCountry/world.json", 1048576, hc.WorldLength, hc.WorldHash)) { return HCQuarantine("world_pair_image_mismatch"); }
        if (!HCMatchImage("$profile:HollowCountry/escalation.json", 2048, hc.EscalationLength, hc.EscalationHash)) { return HCQuarantine("escalation_pair_image_mismatch"); }
        if (!HCMatchImage(groupPath, 1048576, hc.GroupLength, hc.GroupHash)) { return HCQuarantine("group_pair_image_mismatch"); }
        // Persist before opening stores. Intent remains even after clean Stop:
        // script Stop cannot attest that native inventory finished saving.
        if (!HCGroupIO.WriteNew("$profile:HollowCountry/recovery-active.intent", hc.Generation.ToString(), 32)) { return HCQuarantine("session_intent_failed"); }
        HCRecoveryGate.HCAdmit(hc.Generation, groupPath, hc.GroupLength, hc.GroupHash);
        HCReport();
        return true;
    }

    static bool HCMatchImage(string path, int limit, int length, int checksum)
    {
        if (length < 1 || length > limit) { return false; }
        string text;
        return HCGroupIO.HCReadRaw(path, limit, text) && text.Length() == length && text.Hash() == checksum;
    }

    static bool HCAdmitStore(string name)
    {
        // Names document ownership; arbitrary stores cannot opt in via this port.
        if (name != "world" && name != "escalation" && name != "groups") { return false; }
        return HCRecoveryGate.HCReady();
    }

    static bool HCQuarantine(string reason)
    {
        return HCRecoveryGate.HCRefuse(reason);
    }

    static void HCReport()
    {
        string recovery = "quarantined";
        string state = "refused";
        if (HCRecoveryGate.HCReady()) { recovery = "operator_paired_restore"; state = "ready"; }
        int generation = HCRecoveryGate.HCGeneration();
        int quarantined = HCRecoveryGate.HCQuarantined();
        Print("[HC Plan] HC-28 generation=" + generation.ToString() + " recovery=" + recovery + " quarantine=" + quarantined.ToString() + " state=" + state + " reason=" + HCRecoveryGate.HCReason() + " native_generation=operator_attested runtime=PENDING");
    }
}
