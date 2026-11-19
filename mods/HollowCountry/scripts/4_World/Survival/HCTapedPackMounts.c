// HC-52: startup-only authored-pair admission, sharing HC-7's custody/journal.
// No tick, save loop, alternate inventory owner, light entity or offset shim.
// Installed scripts-1.30.164289 API evidence (relative to native script root):
// 3_Game/Global/Game.c:558 ConfigGetTextArray,1120 IsServer;
// 1_Core/proto/EnScript.c:380,385,394,407 Count/Clear/Find/Insert;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString.
// N2 InventoryLocation.c:131 SetAttachment names a native slot, not a transform.
// N11 ScriptedLightBase.c:132-180 attaches a client light, not an inventory item.
// UniversalLight.c:47-91 owns its client light/memory points and cleanup.
// ActionTurnOnHelmetFlashlight.c:33-65 requires Mich2001Helmet; not a pack API.
// Do not use those APIs to simulate an unobserved backpack proxy/mount.
// Wave 13: a pair qualifies only when ALL hold: the operator setting
// HCSettings.EnableTapedPackMounts is on (a missing JSON bool zero-fills to false,
// the safe closed value), the pair has Checked=true in the mission-authored
// lights/pair-receipts.json (HCJsonFields presence guards, strict ids), and the
// HCTapedPackCatalog gate admits it (it admits nothing in shipped code).
class HCTapedPackMounts : HCModule
{
    protected static bool mHCCrossSlot;
    protected static bool mHCConfigured;
    protected static ref TStringArray mHCPermitted = new TStringArray;
    protected static bool mHCSettingOn;
    protected static int mHCReceiptMaxBytes;
    protected static ref TStringArray mHCChecked = new TStringArray;
    protected bool mHCStarted;
    protected ref HCOperationalStatus mHCStatus = new HCOperationalStatus;

    override string GetName() { return "TapedPackMounts"; }
    override bool IsEnabled(HCSettings settings) { return settings != null; }
    override HCOperationalStatus HCGetOperationalStatus() { return mHCStatus; }

    static void Reset()
    {
        mHCCrossSlot = false;
        mHCConfigured = false;
        mHCPermitted.Clear();
        mHCSettingOn = false;
        mHCReceiptMaxBytes = 0;
        mHCChecked.Clear();
    }

    // Called only by the server settings owner before module startup. Copy a
    // bounded, unique exact-ID list so later DTO mutation cannot grant access.
    static bool Configure(HCTapedLightMountSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        Reset();
        if (!settings || !settings.permittedPairIds) { return false; }
        if (settings.permittedPairIds.Count() > 2) { return false; }
        foreach (string pairId : settings.permittedPairIds)
        {
            if (!HCTapedPackCatalog.KnownPair(pairId) || mHCPermitted.Find(pairId) >= 0)
            {
                Reset();
                return false;
            }
            mHCPermitted.Insert(pairId);
        }
        mHCCrossSlot = settings.crossSlotLights;
        mHCConfigured = true;
        return true;
    }

    static bool CrossSlotEnabled()
    {
        return mHCConfigured && mHCCrossSlot;
    }

    static bool NativeSlotAvailable(string pairId)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!HCTapedPackCatalog.KnownPair(pairId)) { return false; }
        if (!HCBuildIdentity.Matches(HCBuildIdentity.SeenBuild())) { return false; }
        string slotName = HCTapedPackCatalog.SlotName(pairId);
        TStringArray hostSlots = new TStringArray;
        TStringArray lightSlots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgVehicles TortillaBag attachments", hostSlots);
        GetGame().ConfigGetTextArray("CfgVehicles UniversalLight inventorySlot", lightSlots);
        return hostSlots.Find(slotName) >= 0 && lightSlots.Find(slotName) >= 0;
    }

    static string PairRefusal(string pairId)
    {
        if (!HCTapedPackCatalog.KnownPair(pairId)) { return "unsupported_pack_pair"; }
        if (pairId == "tortilla_universal_cross")
        {
            if (!CrossSlotEnabled()) { return "cross_slot_disabled"; }
            if (mHCPermitted.Find(pairId) < 0) { return "cross_slot_pair_not_permitted"; }
        }
        if (!NativeSlotAvailable(pairId)) { return "pack_native_slot_unavailable"; }
        return HCTapedPackCatalog.Refusal(pairId);
    }

    static bool BindingAllowed(HCTapedLightBinding binding)
    {
        if (!GetGame() || !GetGame().IsServer() || !binding) { return false; }
        if (!mHCConfigured || binding.HostConfigRoot != "CfgVehicles") { return false; }
        if (!HCTapedPackCatalog.Matches(binding.PairId, binding.HostClass, binding.LightClass, binding.SlotName, binding.CrossSlot)) { return false; }
        if (binding.CrossSlot)
        {
            if (!CrossSlotEnabled() || mHCPermitted.Find(binding.PairId) < 0) { return false; }
        }
        // Deliberately cheap closed path: no repeated native config scans for
        // an unqualified pair, no fabricated measurement digest or binding.
        return PairQualified(binding.PairId);
    }

    static bool ReceiptChecked(string pairId)
    {
        return mHCChecked.Find(pairId) >= 0;
    }

    // "" when the pair is admitted, else the first refusal reason. Order keeps
    // the closed path cheap: no native config scan until every earlier gate holds.
    static string PairAdmission(string pairId)
    {
        if (!HCTapedPackCatalog.KnownPair(pairId)) { return "unsupported_pack_pair"; }
        if (!mHCConfigured) { return "pack_mounts_unconfigured"; }
        if (!mHCSettingOn) { return "setting_off"; }
        if (!ReceiptChecked(pairId)) { return "client_check_pending"; }
        if (pairId == "tortilla_universal_cross")
        {
            if (!CrossSlotEnabled()) { return "cross_slot_disabled"; }
            if (mHCPermitted.Find(pairId) < 0) { return "cross_slot_pair_not_permitted"; }
        }
        if (!HCTapedPackCatalog.Qualified(pairId)) { return HCTapedPackCatalog.Refusal(pairId); }
        if (!NativeSlotAvailable(pairId)) { return "pack_native_slot_unavailable"; }
        return "";
    }

    static bool PairQualified(string pairId)
    {
        return PairAdmission(pairId) == "";
    }

    static int AdmittedCount()
    {
        int admitted = 0;
        TStringArray ids = HCTapedPackCatalog.PairIds();
        foreach (string pairId : ids)
        {
            if (PairQualified(pairId)) { admitted = admitted + 1; }
        }
        return admitted;
    }

    // First refusal across the known pairs, for the one-line boot summary.
    static string FirstAdmissionReason()
    {
        TStringArray ids = HCTapedPackCatalog.PairIds();
        string reason = "";
        foreach (string pairId : ids)
        {
            if (reason == "") { reason = PairAdmission(pairId); }
        }
        return reason;
    }

    // Receipt file read: bounded by the manifest's MaxReceiptBytes, "" when unreadable.
    protected static string ReadReceipts()
    {
        string text;
        if (!HCGroupIO.Read("$mission:hollow-country/lights/pair-receipts.json", mHCReceiptMaxBytes, text)) { return ""; }
        return text;
    }

    // Native JsonFileLoader zero-fills missing fields, so callers guard presence.
    protected static HCTapedPairReceipts ParseReceipts(string text)
    {
        HCTapedPairReceipts parsed;
        string error;
        if (!JsonFileLoader<HCTapedPairReceipts>.LoadData(text, parsed, error)) { return null; }
        return parsed;
    }

    // Returns "" and records the checked pair ids, else a refusal reason with
    // nothing recorded. Unknown or duplicate ids and half-filled rows refuse the
    // whole file: a receipt file is all-or-nothing, never partially trusted.
    static string ApplyReceipts(string text)
    {
        mHCChecked.Clear();
        if (text == "") { return "receipts_unreadable"; }
        if (!HCJsonFields.Has(text, "SchemaVersion") || !HCJsonFields.Has(text, "Receipts")) { return "receipts_fields_missing"; }
        if (!HCJsonFields.Every(text, "PairId", 3) || !HCJsonFields.Every(text, "Checked", 3)) { return "receipts_fields_missing"; }
        if (!HCJsonFields.Every(text, "CheckDate", 3) || !HCJsonFields.Every(text, "Note", 3)) { return "receipts_fields_missing"; }
        HCTapedPairReceipts parsed = ParseReceipts(text);
        if (!parsed || !parsed.Receipts) { return "receipts_invalid"; }
        if (parsed.SchemaVersion != 1) { return "receipts_schema"; }
        TStringArray seen = new TStringArray;
        array<ref HCTapedPairReceipt> rows = parsed.Receipts;
        string refusal = "";
        foreach (HCTapedPairReceipt row : rows)
        {
            if (refusal == "" && (!row || !HCTapedPackCatalog.KnownPair(row.PairId))) { refusal = "receipt_unknown_pair"; }
            if (refusal == "" && seen.Find(row.PairId) >= 0) { refusal = "receipt_duplicate_pair"; }
            if (refusal == "" && row.Checked && (row.CheckDate == "" || row.Note == "")) { refusal = "receipt_check_incomplete"; }
            if (refusal == "")
            {
                seen.Insert(row.PairId);
                if (row.Checked) { mHCChecked.Insert(row.PairId); }
            }
        }
        if (refusal != "") { mHCChecked.Clear(); }
        return refusal;
    }

    // Startup-only. Skipped while the setting is off (no file read), and while
    // the manifest is not configured (no read limit exists yet).
    static string LoadReceipts()
    {
        mHCChecked.Clear();
        if (!mHCConfigured) { return "pack_mounts_unconfigured"; }
        if (!mHCSettingOn) { return ""; }
        return ApplyReceipts(ReadReceipts());
    }

    // Mission manifest read: bounded (file is under 16 KiB), "" when unreadable.
    protected static string ReadManifest()
    {
        string text;
        if (!HCGroupIO.Read("$mission:hollow-country/lights/backpack-mounts.json", 16384, text)) { return ""; }
        return text;
    }

    // Native JsonFileLoader zero-fills missing ints, so callers guard presence.
    protected static HCTapedPackManifest ParseManifest(string text)
    {
        HCTapedPackManifest manifest;
        string error;
        if (!JsonFileLoader<HCTapedPackManifest>.LoadData(text, manifest, error)) { return null; }
        return manifest;
    }

    // Returns "" once Configure() accepted the closed manifest defaults, else a
    // refusal reason with nothing configured. The file cannot qualify a pair.
    static string ApplyManifest(string text)
    {
        if (text == "") { return "mount_manifest_unreadable"; }
        if (!HCJsonFields.Has(text, "SchemaVersion") || !HCJsonFields.Has(text, "Qualified") || !HCJsonFields.Has(text, "SettingsContract")) { return "mount_manifest_fields_missing"; }
        if (!HCJsonFields.Check(text, "DefaultCrossSlotLights", 2, false) || !HCJsonFields.Check(text, "DefaultPermittedPairIds", 2, false) || !HCJsonFields.Check(text, "MaxPermittedPairIds", 2, false)) { return "mount_manifest_fields_missing"; }
        if (!HCJsonFields.Check(text, "MaxReceiptBytes", 2, false)) { return "mount_manifest_fields_missing"; }
        HCTapedPackManifest manifest = ParseManifest(text);
        if (!manifest || !manifest.SettingsContract || !manifest.SettingsContract.DefaultPermittedPairIds) { return "mount_manifest_invalid"; }
        if (manifest.SchemaVersion != 1) { return "mount_manifest_schema"; }
        if (manifest.Qualified) { return "mount_manifest_qualified_claim"; }
        HCTapedPackSettingsContract contract = manifest.SettingsContract;
        TStringArray ids = contract.DefaultPermittedPairIds;
        if (contract.MaxPermittedPairIds != 2 || ids.Count() > contract.MaxPermittedPairIds) { return "pack_mount_settings_refused"; }
        if (contract.MaxReceiptBytes <= 0) { return "pack_mount_settings_refused"; }
        HCTapedLightMountSettings preferences = new HCTapedLightMountSettings;
        preferences.crossSlotLights = contract.DefaultCrossSlotLights;
        foreach (string pairId : ids) { preferences.permittedPairIds.Insert(pairId); }
        if (!Configure(preferences)) { return "pack_mount_settings_refused"; }
        mHCReceiptMaxBytes = contract.MaxReceiptBytes;
        return "";
    }

    // Loads the manifest once per start; Reset() on stop makes the next start reload.
    static string LoadSettings()
    {
        if (mHCConfigured) { return ""; }
        return ApplyManifest(ReadManifest());
    }

    override void OnStart(HCSettings settings)
    {
        if (mHCStarted) { return; }
        mHCStarted = true;
        string loadReason = LoadSettings();
        string config = "loaded";
        if (loadReason != "") { config = loadReason; }
        // Set after LoadSettings(): Configure() resets this class's state first.
        mHCSettingOn = settings.EnableTapedPackMounts;
        string receiptReason = LoadReceipts();
        string receipts = "not_read";
        if (mHCSettingOn && receiptReason == "") { receipts = "ok"; }
        if (receiptReason != "") { receipts = receiptReason; }
        string reason = PairRefusal("tortilla_universal_mount");
        string crossReason = PairRefusal("tortilla_universal_cross");
        string crossSlot = HCV2Admission.OnOff(CrossSlotEnabled());
        string setting = HCV2Admission.OnOff(mHCSettingOn);
        int pairs = HCTapedPackCatalog.PairIds().Count();
        int permitted = mHCPermitted.Count();
        int checked = mHCChecked.Count();
        int qualified = AdmittedCount();
        // off: operator setting off. refused: setting on but no checked receipt,
        // an invalid receipt file or a closed catalogue gate. ready only once a
        // pair is admitted by code. degraded: the manifest itself failed.
        string state = "refused";
        string stateReason = FirstAdmissionReason();
        if (!mHCSettingOn) { state = "off"; stateReason = "setting_off"; }
        if (receiptReason != "") { stateReason = receiptReason; }
        if (qualified > 0) { state = "ready"; stateReason = "pairs_client_checked"; }
        if (loadReason != "") { state = "degraded"; stateReason = loadReason; }
        mHCStatus.HCPublish(state, stateReason);
        Print(HCV2Admission.Line("TapedPackMounts", mHCSettingOn, stateReason, qualified > 0));
        string line = "[HC TapedPackMounts] pairs=" + pairs.ToString() + " receipts_checked=" + checked.ToString();
        line = line + " admitted=" + qualified.ToString() + " setting=" + setting + " reason=" + stateReason;
        Print(line + " receipts=" + receipts + " runtime=PENDING");
        line = "[HC Plan] HC-52 pack_pairs=1 cross_slot=" + crossSlot + " qualified=" + qualified.ToString();
        line = line + " permitted=" + permitted.ToString() + " state=" + state + " reason=" + stateReason;
        Print(line + " authored=1 admitted=" + qualified.ToString() + " observed=0 config=" + config + " runtime=PENDING");
        Print("[HC Plan] HC-52 pair=tortilla_universal_mount state=refused reason=" + reason + " runtime=PENDING");
        Print("[HC Plan] HC-52 pair=tortilla_universal_cross state=refused reason=" + crossReason + " runtime=PENDING");
    }

    override void OnStop()
    {
        Reset();
        mHCStarted = false;
        mHCStatus.HCStop();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTapedPackMounts());
    }
}
