// HC-14 bounded content admission receipt, not a gameplay/CE controller.
// Infected calls Check once per module start and caches the result; HC-62 emits
// HCPlanLine through the fixed content status path. No per-actor/tick logging.
// Source metadata and config readiness never prove a CE spawn or client asset.
// Native evidence: installed scripts-1.30.164289, relative paths below:
// 3_Game/Global/Game.c:449 ConfigGetText, :539 ConfigGetInt,
// :612 ConfigIsExisting, :1120 IsServer, :1437 IsKindOf.
// HCBuildIdentity.SeenBuild reuses the shared installed build accessor.
// 3_Game/gameplay.c:636 GetGame (server-owned startup context only).
// 1_Core/proto/EnConvert.c:30 int.ToString; EnString.c:113 Substring,
// :171 ToLower, :199 Length, :448 Get (bounded model normalization).
// N8 ZombieBase.c:113 returns false for IsZombieMilitary; civilian clerk base
// inherits it. ZombieFemaleBase.c:139-152 soldier/eastSoldier return true.
// Config ancestry here cannot establish the method result on a live actor.
// N10 3_Game/CE/CentralEconomy.c:379-495 offers creation/debug operations;
// :710-717 diagnostics do not return active event-child configuration. None
// are invoked. Refuse live CE observation/mutation rather than invent an API.
class HCNativeVariantAdmission
{
    // Authored count and expected entries mirror variants.json;
    // no runtime manifest/config-tree scan.
    int Authored = 20;
    int ConfigVerified;
    int ConfigRefused;
    // The unresolved stock UrbanB_BlueBright spelling is NOT renamed to C.
    int Unresolved = 1;
    bool Preference;
    string State = "off";
    string Refusal = "CE_RUNTIME_DISABLE_UNAVAILABLE";

    static HCNativeVariantAdmission Check(bool preference)
    {
        HCNativeVariantAdmission receipt = new HCNativeVariantAdmission;
        receipt.Preference = HCV2Admission.Admitted(preference);
        if (!receipt.Preference) { return receipt; }
        receipt.HCInspect();
        return receipt;
    }

    // HCV2 admission reports the preference and unqualified experiment. The
    // separate receipt below reports actual config checks and CE uncertainty.
    string HCAdmissionLine()
    {
        return HCV2Admission.Line("NativeInfectedVariants", Preference, "HC-14-N8-N10", false);
    }

    string HCPlanLine()
    {
        string line = "[HC Plan] HC-14 native_variants=" + Authored.ToString() + " unresolved=" + Unresolved.ToString() + " population_delta=0";
        line = line + " state=" + State + " scope=config_only authored=" + Authored.ToString();
        line = line + " config_verified=" + ConfigVerified.ToString() + " config_refused=" + ConfigRefused.ToString();
        line = line + " ce_admitted=unknown observed=unknown refusal=" + Refusal;
        line = line + " ce_observation=refused:CE_EVENT_INTROSPECTION_UNAVAILABLE";
        return line + " seasonal=refused:LIVE_SEASONAL_CE_MUTATION_UNSUPPORTED runtime=PENDING";
    }

    protected void HCInspect()
    {
        State = "refused";
        Refusal = "SERVER_CONTEXT_REQUIRED";
        if (!GetGame() || !GetGame().IsServer()) { return; }
        string build = HCBuildIdentity.SeenBuild();
        Refusal = "NATIVE_BUILD_UNSUPPORTED";
        if (!HCInfectedProfiles.NativeBuildSupported(build)) { return; }
        Refusal = "none";
        // Fixed selected roster from the pinned addon config.bin; no config-tree scan.
        // Stock types.xml uses Zmbm_Mummy; config/script define ZmbM_Mummy.
        HCInspectCandidate("ZmbF_ArmyOfficer", "ZmbF_SoldierNormal_Base", "\\DZ\\characters\\zombies\\ArmyOfficer_fat_f.p3d", "InfectedSoldier_Officer");
        HCInspectCandidate("ZmbF_ClerkFat_Black", "ZmbF_ClerkFat_Base", "\\DZ\\characters\\zombies\\clerkB_fat_f.p3d", "InfectedFemale");
        HCInspectCandidate("ZmbF_ClerkFat_BluePattern", "ZmbF_ClerkFat_Base", "\\DZ\\characters\\zombies\\clerkB_fat_f.p3d", "InfectedFemale");
        HCInspectCandidate("ZmbF_ClerkFat_GreyPattern", "ZmbF_ClerkFat_Base", "\\DZ\\characters\\zombies\\clerkB_fat_f.p3d", "InfectedFemale");
        HCInspectCandidate("ZmbF_ClerkFat_White", "ZmbF_ClerkFat_Base", "\\DZ\\characters\\zombies\\clerkB_fat_f.p3d", "InfectedFemale");
        HCInspectCandidate("ZmbF_MilkMaidOld_Green", "ZmbF_MilkMaidOld_LT_Base", "\\DZ\\characters\\zombies\\milkmaid_old_f.p3d", "InfectedFemale");
        HCInspectCandidate("ZmbF_eastSoldier_Heavy_Navy", "ZmbF_eastSoldier_Normal_Navy", "dz\\characters\\zombies\\eastSoldier_normal_Navy_f.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbF_eastSoldier_Normal_Navy", "ZmbF_eastSoldier_Base", "dz\\characters\\zombies\\eastSoldier_normal_Navy_f.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbF_usSoldier_Heavy_Woodland", "ZmbF_usSoldier_normal_Woodland", "\\DZ\\characters\\zombies\\ZmbF_usSoldier_normal.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbF_usSoldier_normal_Woodland", "ZmbF_usSoldier_normal_Base", "\\DZ\\characters\\zombies\\ZmbF_usSoldier_normal.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbM_HunterOld_Autumn", "ZmbM_HunterOld_Base", "\\DZ\\characters\\zombies\\Hunter_old_M.p3d", "InfectedMHunter");
        HCInspectCandidate("ZmbM_HunterOld_Winter", "ZmbM_HunterOld_Base", "\\DZ\\characters\\zombies\\Hunter_old_M.p3d", "InfectedMHunter");
        HCInspectCandidate("ZmbM_NBC_Grey", "ZmbM_SoldierNormal_Base", "\\DZ\\characters\\zombies\\NBCInfected_Grey.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbM_NBC_White", "ZmbF_ParamedicNormal_Base", "\\DZ\\characters\\zombies\\NBCInfected_Yellow.p3d", "InfectedFParamedic");
        HCInspectCandidate("ZmbM_PatrolNormal_Winter", "ZmbM_PatrolNormal_Base", "\\DZ\\characters\\zombies\\Patrol_normal_winter_m.p3d", "InfectedMSoldier");
        HCInspectCandidate("ZmbM_PolicemanSpecForce", "ZmbM_PolicemanSpecForce_Base", "\\DZ\\characters\\zombies\\PolicemanSpecialForce_Normal_m.p3d", "InfectedMPolice");
        HCInspectCandidate("ZmbM_PrisonerSkinny", "ZmbM_PrisonerSkinny_Base", "\\DZ\\characters\\zombies\\prisoner_skinny_m.p3d", "InfectedMale");
        HCInspectCandidate("ZmbM_Santa", "ZmbM_priestPopSkinny_Base", "\\DZ\\characters\\zombies\\santa.p3d", "InfectedPriest");
        HCInspectCandidate("ZmbM_usSoldier_Officer_Convoy", "ZmbM_usSoldier_Officer_Desert", "\\DZ\\characters\\zombies\\ArmyOfficer_fat_m.p3d", "InfectedSoldier_Officer");
        HCInspectCandidate("Zmbm_Mummy", "ZombieMaleBase", "\\DZ\\characters\\zombies\\Mummy.p3d", "InfectedMMummy");
        if (ConfigVerified != Authored || ConfigRefused != 0) { return; }
        State = "ready";
        // Ready means inspected config only. CE consumption, entitlement on
        // both clients and all model/audio/native transition trials are pending.
        Refusal = "CE_EVENT_INTROSPECTION_UNAVAILABLE";
    }

    static string HCNormalizeModel(string model)
    {
        model.ToLower();
        if (model.Length() > 0 && model.Get(0) == "\\")
        {
            model = model.Substring(1, model.Length() - 1);
        }
        return model;
    }

    protected void HCInspectCandidate(string typeName, string nativeBase, string expectedModel, string expectedProfile)
    {
        string path = "CfgVehicles " + typeName;
        string model;
        string agentProfile;
        string dlcTag;
        string failure = "none";
        if (!GetGame().ConfigIsExisting(path)) { failure = "NATIVE_CLASS_MISSING"; }
        else if (HCConfigHelper.GetInt(path + " scope", 0) != 2) { failure = "NATIVE_SCOPE_NOT_PUBLIC"; }
        else if (!GetGame().IsKindOf(typeName, nativeBase)) { failure = "NATIVE_PROFILE_ANCESTRY_MISMATCH"; }
        else if (!GetGame().ConfigGetText(path + " model", model) || HCNormalizeModel(model) != HCNormalizeModel(expectedModel)) { failure = "NATIVE_MODEL_MISMATCH"; }
        else if (!GetGame().ConfigGetText(path + " aiAgentTemplate", agentProfile) || agentProfile != expectedProfile) { failure = "NATIVE_AGENT_PROFILE_MISMATCH"; }
        else if (GetGame().ConfigIsExisting(path + " DLC"))
        {
            if (!GetGame().ConfigGetText(path + " DLC", dlcTag) || dlcTag != "") { failure = "NATIVE_DLC_TAG_UNVERIFIED"; }
        }
        if (failure != "none")
        {
            ConfigRefused++;
            if (Refusal == "none") { Refusal = failure + ":" + typeName; }
            return;
        }
        ConfigVerified++;
    }
}
