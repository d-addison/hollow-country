// HC-23: startup-only catalogue receipt, no inventory or light controller.
// Native scripts-1.30.164289 evidence (relative to the inspected script root):
// 3_Game/Global/Game.c:558 ConfigGetTextArray,1120 IsServer;
// 1_Core/proto/EnDebug.c:96 Print; EnConvert.c:30 int.ToString;
// 1_Core/proto/EnScript.c:380,394 array Count/Find.
// Native light ownership remains UniversalLight.c:47-91 (under
// 4_World/Entities/ItemBase/Switchable_Base/): AttachOnMemoryPoint at 52,
// client OnWorkStart/OnWorkStop, FadeOut at 85. No transform/light API is called.
// ActionTurnOnHelmetFlashlight.c:33-65 (N11) uses helmetFlashlight natively.
// See the manifest for exact installed config hashes and all pending checks.
class HCTapedHelmetMounts : HCModule
{
    protected bool mHCStarted;
    protected ref HCOperationalStatus mHCStatus = new HCOperationalStatus;

    override string GetName() { return "TapedHelmetMounts"; }
    override bool IsEnabled(HCSettings settings) { return settings != null; }
    override HCOperationalStatus HCGetOperationalStatus() { return mHCStatus; }

    // Static config is an additional refusal check, never mounted geometry proof.
    bool NativeSlotAvailable()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!HCBuildIdentity.Matches(HCBuildIdentity.SeenBuild())) { return false; }
        TStringArray hostSlots = new TStringArray;
        TStringArray lightSlots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgVehicles Mich2001Helmet attachments", hostSlots);
        GetGame().ConfigGetTextArray("CfgVehicles UniversalLight inventorySlot", lightSlots);
        return hostSlots.Find("helmetFlashlight") >= 0 && lightSlots.Find("helmetFlashlight") >= 0;
    }

    override void OnStart(HCSettings settings)
    {
        if (mHCStarted) { return; }
        mHCStarted = true;
        string reason = "helmet_mount_two_client_pending";
        if (!NativeSlotAvailable()) { reason = "helmet_native_slot_unavailable"; }
        mHCStatus.HCPublish("off", reason);
        int authored = HCTapedWearableCatalog.Rows().Count();
        int unsupported = HCTapedWearableCatalog.CompatibilityQueue().Count();
        Print(HCV2Admission.Line("TapedHelmetMounts", false, reason, false));
        Print("[HC Plan] HC-23 helmet_mounts=" + authored.ToString() + " qualified=0 unsupported=" + unsupported.ToString() + " state=off reason=" + reason + " unsupported_reason=unsupported_helmet_pair queue_reason=no_native_helmet_light_slot runtime=PENDING");
    }

    override void OnStop()
    {
        mHCStarted = false;
        mHCStatus.HCStop();
    }
}

// Separate HC-7 qualification port: do not append wearable rows to the weapon
// catalogue or grant them the weapon adapter's default local-acceptance opt-in.
// Lead integration must retain the same service/port, custody and journal. No
// binding is minted until native/two-client acceptance supplies the missing
// evidence. There is deliberately no synthetic measurement digest or new range.
class HCTapedHelmetQualification : HCTapedLightQualification
{
    override bool Ready()
    {
        return HCTapedWearableCatalog.Qualified();
    }

    override HCTapedLightBinding Resolve(EntityAI host, ItemBase light)
    {
        return null;
    }
}
