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
class HCTapedPackMounts : HCModule
{
    protected static bool mHCCrossSlot;
    protected static bool mHCConfigured;
    protected static ref TStringArray mHCPermitted = new TStringArray;
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
        if (!HCTapedPackCatalog.Qualified(binding.PairId)) { return false; }
        return NativeSlotAvailable(binding.PairId);
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
        HCTapedPackManifest manifest = ParseManifest(text);
        if (!manifest || !manifest.SettingsContract || !manifest.SettingsContract.DefaultPermittedPairIds) { return "mount_manifest_invalid"; }
        if (manifest.SchemaVersion != 1) { return "mount_manifest_schema"; }
        if (manifest.Qualified) { return "mount_manifest_qualified_claim"; }
        HCTapedPackSettingsContract contract = manifest.SettingsContract;
        TStringArray ids = contract.DefaultPermittedPairIds;
        if (contract.MaxPermittedPairIds != 2 || ids.Count() > contract.MaxPermittedPairIds) { return "pack_mount_settings_refused"; }
        HCTapedLightMountSettings preferences = new HCTapedLightMountSettings;
        preferences.crossSlotLights = contract.DefaultCrossSlotLights;
        foreach (string pairId : ids) { preferences.permittedPairIds.Insert(pairId); }
        if (!Configure(preferences)) { return "pack_mount_settings_refused"; }
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
        string reason = PairRefusal("tortilla_universal_mount");
        string crossReason = PairRefusal("tortilla_universal_cross");
        string crossSlot = HCV2Admission.OnOff(CrossSlotEnabled());
        int permitted = mHCPermitted.Count();
        int qualified = 0;
        if (HCTapedPackCatalog.Qualified("tortilla_universal_mount")) { qualified = qualified + 1; }
        if (CrossSlotEnabled() && HCTapedPackCatalog.Qualified("tortilla_universal_cross")) { qualified = qualified + 1; }
        // off: cross-slot setting off. refused: setting on, no per-pair client
        // check receipt exists. ready only once a pair is qualified by code.
        string state = "off";
        string stateReason = "cross_slot_disabled";
        if (CrossSlotEnabled()) { state = "refused"; stateReason = "client_check_pending"; }
        if (qualified > 0) { state = "ready"; stateReason = "pairs_client_checked"; }
        if (loadReason != "") { state = "degraded"; stateReason = loadReason; }
        mHCStatus.HCPublish(state, stateReason);
        Print(HCV2Admission.Line("TapedPackMounts", false, stateReason, false));
        string line = "[HC Plan] HC-52 pack_pairs=1 cross_slot=" + crossSlot + " qualified=" + qualified.ToString();
        line = line + " permitted=" + permitted.ToString() + " state=" + state + " reason=" + stateReason;
        Print(line + " authored=1 admitted=0 observed=0 config=" + config + " runtime=PENDING");
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
