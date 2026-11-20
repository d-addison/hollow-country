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
// Wave 16 (owner: "enable all features by default"): the one Mich2001Helmet pair is
// admitted UNVERIFIED at startup (the HCV2Admission pattern). Named opt-out: the
// operator file $profile:HollowCountry/acceptance/taped_helmet.disable (the same
// style as taped_light.disable). A missing native slot reports degraded with its
// reason. The exact-pair held action shares HC-7 custody and journal; native alignment
// remains unverified. Nothing
// here was observed in DayZ (runtime=PENDING).
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
        string state = "ready";
        string reason = "admitted_unverified";
        if (!NativeSlotAvailable())
        {
            state = "degraded";
            reason = "helmet_native_slot_unavailable";
        }
        if (!HCTapedLightAdmission.Admitted())
        {
            state = "off";
            reason = "taped_light_unavailable";
        }
        if (FileExist("$profile:HollowCountry/acceptance/taped_helmet.disable"))
        {
            state = "off";
            reason = "operator_disable_file";
        }
        HCTapedWearableCatalog.HCSetAdmitted(state == "ready");
        mHCStatus.HCPublish(state, reason);
        HCReached.Mark("taped_helmet.admission_logged");
        int authored = HCTapedWearableCatalog.Rows().Count();
        int unsupported = HCTapedWearableCatalog.CompatibilityQueue().Count();
        Print(HCV2Admission.Line("TapedHelmetMounts", state != "off", "helmet_mount_two_client_check", HCTapedWearableCatalog.Qualified()));
        string line = "[HC Plan] HC-23 helmet_mounts=" + authored.ToString() + " qualified=0 unsupported=" + unsupported.ToString() + " state=" + state + " reason=" + reason;
        Print(line + " unsupported_reason=unsupported_helmet_pair queue_reason=no_native_helmet_light_slot action=held_mount_remove_native_toggle geometry=native_proxy_unverified runtime=PENDING");
    }

    override void OnStop()
    {
        mHCStarted = false;
        HCTapedWearableCatalog.HCSetAdmitted(false);
        mHCStatus.HCStop();
    }
}

// Separate HC-7 qualification port: do not append wearable rows to the weapon
// catalogue or grant them the weapon adapter's default local-acceptance opt-in.
// The held action retains the same service/port, custody and journal. Ready
// follows native slot availability and unverified startup admission.
// There is deliberately no synthetic measurement digest or new range.
class HCTapedHelmetQualification : HCTapedLightQualification
{
    override bool Ready()
    {
        return HCTapedWearableCatalog.Admitted();
    }

    override HCTapedLightBinding Resolve(EntityAI host, ItemBase light)
    {
        if (!Ready() || !host || host.GetType() != "Mich2001Helmet") { return null; }
        HCTapedLightV1Qualification nativeQualification = new HCTapedLightV1Qualification;
        return nativeQualification.Resolve(host, light);
    }

    override bool HasLOS(PlayerBase actor, EntityAI host, HCTapedLightBinding binding)
    {
        return Ready() && actor && host && actor.GetItemInHands() == host && host.GetHierarchyRootPlayer() == actor;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTapedHelmetMounts());
    }
}
