// HC-5/#148/#139: observed gestures and durable betrayal, no dialogue.
// Existing provider calls below retain their prior citations. New provider
// emote/cease-fire calls go through the installed native HCXSignalProvider.
// LC-T403..406 / EXP-L1/L2/L3/L6. Installed Expansion addons/ai_scripts.pbo:
// 4_World/DayZExpansion_AI/Classes/Targets/eAIPlayerTargetInformation.c:58 CalculateThreat;
// Classes/Targets/eAIEntityTargetInformation.c:24 GetEntity; eAITargetInformationState.c:7-21
// public threat/LOS state (active threat otherwise decays slowly:58-102);
// Entities/AI/eAIBase.c:4118 eAI_OnNoiseEvent, :9755 RaiseWeapon (clears queued shots),
// :10860-10874 Expansion_SetEmote/Expansion_PlayEmote; :9743 CanRaiseWeapon;
// Entities/DayZPlayerImplement.c:22 member slot, :234 GetGroup;
// Classes/eAIGroup.c:671 GetFaction, :685 GetName, :1123 IsInCombat;
// Classes/Patrols/eAIDynamicPatrol.c:637 stable configured group name;
// 3_Game/DayZExpansion_AI/Factions/eAIFaction.c:104 guard semantics.
// Native scripts-1.30.164289: 3_Game/Global/DayZPhysics.c:199 RaycastRV;
// 4_World/Entities/DayZPlayerImplement.c:4005 IsRaised;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive, :630,636 weapon tests;
// 3_Game/Entities/Man.c:21 GetIdentity, :81 GetHumanInventory;
// 3_Game/Systems/Inventory/HumanInventory.c:16 GetEntityInHands;
// 4_World/Entities/ManBase/PlayerBase.c:1892 GetEmoteManager, :3925 IsUnconscious;
// 4_World/Classes/EmoteManager.c:1026 CanPlayEmote;
// 3_Game/constants.c:368,393 greeting/hold; Global/Game.c:1535 GetTime.
// Raid death hook: native 4_World/Entities/ManBase/PlayerBase.c:1214
// EEKilled(Object killer); :1255 EEHitBy (exact parameters retained below);
// Expansion GetGroup reference is listed above.
class HCXStance
{
    static bool Owns(eAIBase ai)
    {
        return HCXAIQualification.EncountersEnabled() && ai && HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai) && HCXFactions.Known(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai))));
    }
    static int Relation(eAIBase ai, PlayerBase player)
    {
        string theirs = "Travellers";
        if (HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player))
        {
            string mapped = HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player)));
            if (mapped != "") { theirs = mapped; }
        }
        return HCXFactions.Relation(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai))), theirs);
    }
    // A fresh character has no PlayerBase yet. Ordinary HC human accounts use
    // the same Travellers fallback as Relation; live members retain their faction.
    // Caller must first establish Owns(ai); unknown actors are never neutralised.
    static int CampRelation(eAIBase ai, PlayerBase player = null)
    {
        if (player) { return HCXStance.Relation(ai, player); }
        return HCXFactions.Relation(HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai))), "Travellers");
    }
    // Hostile factions may be fought in legitimate self-defence even when a
    // hit/kill defence record exists. Betrayal requires a non-hostile relation.
    static bool HCRememberKill(eAIBase actor, PlayerBase player)
    {
        if (!actor || !player) { return false; }
        return HCXStance.Relation(actor, player) >= 0;
    }
    static bool RaisedWeapon(PlayerBase player)
    {
        EntityAI hands = player.GetHumanInventory().GetEntityInHands();
        return player.IsRaised() && hands && (hands.IsWeapon() || hands.IsMeleeWeapon());
    }
    // Fresh geometry supplements provider LOS, never discovers a player itself.
    static bool Visible(eAIBase ai, PlayerBase player)
    {
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>();
        vector chest = player.GetPosition() + Vector(0, 1.2, 0);
        bool blocked = DayZPhysics.RaycastRV(HCXExpansionBridge.HCBaseGetPosition(ai) + Vector(0, 1.6, 0), chest, contact, normal, component, hits, null, ai);
        if (!blocked) { return true; }
        return hits.Find(player) >= 0 && vector.Distance(contact, chest) < 0.8;
    }
}
class HCXWarning
{
    int Started = -1;
    int LastSeen = -1;
    bool Hostile;
    int LastWaveSerial;
    int NextWarning;
}
// Extend the existing HC defence record, not a second hit classifier. This
// accessor is declared before the hook that calls it; rescue policy stays owned
// by HCXDefence.OnHit. The later eAIBase link calls super before reading it.
modded class HCXDefence
{
    static bool HCHitRecorded(eAIBase actor, PlayerBase player)
    {
        if (!s_Running || !actor || !player) { return false; }
        HCXGrudge grudge = HCXDefence.Find(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor), player);
        if (!grudge || grudge.Until <= GetGame().GetTime()) { return false; }
        return grudge.Kind == HCXDefencePolicy.KIND_HIT || grudge.Kind == HCXDefencePolicy.KIND_KILL;
    }
}


// Actor-local latch: count admission once, after the existing fairness/provider
// checks succeed. Merely revisiting an actor on a tick is not a use.
modded class eAIBase
{
    bool HCXLivingUseAdmitted;
}

class HCXLivingModule : HCModule
{
    protected ref HCXCheckpointProps m_Checkpoints;
    protected int m_ActorCursor;
    protected string m_Refusal;
    protected bool m_Started;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    override string GetName() { return "v2-expansion-living-world"; }

    // Wave 16: started = OnStart ran; a provider/fairness refusal seen on a live actor is a real degradation
    // and reports its own text (bounded to 128 characters by HCOperationalStatus).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Started, "", m_Refusal, "living_world_providers_installed");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }
    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Factions", true, "EXP-L2", HCV2Gates.Qualified("EXP-L2")));
        Print(HCV2Admission.Line("Stance", true, "EXP-L3", HCV2Gates.Qualified("EXP-L3")));
        Print(HCV2Admission.Line("AskForNews", false, "EXP-L6", false));
        Print(HCV2Admission.Line("Checkpoints", true, "EXP-L1", HCV2Gates.Qualified("EXP-L1")));
        HCXAIQualification.SetEncountersEnabled(true);
        HCAskForNews.Configure(false);
        HCXEmoteObservation.Start();
        HCXNativeSignalProvider provider = new HCXNativeSignalProvider();
        HCXEmoteObservation.Install(provider);
        m_Checkpoints = new HCXCheckpointProps();
        m_Checkpoints.Start();
        m_Refusal = "";
        if (!HCXEmoteObservation.Ready())
        {
            m_Refusal = "emote_provider_or_betrayal_store_unavailable";
            Print("[HollowCountry] Living AI admission refused: " + m_Refusal + "; runtime=PENDING");
        }
        m_Started = true;
    }
    override void OnTick(float deltaTime)
    {
        if (m_Checkpoints) { m_Checkpoints.Step(); }
        // Report store/provider faults even when there are no retained actors.
        // This is status only: a disk fault must never disable surrender control.
        if (!HCXEmoteObservation.Ready() && m_Refusal == "")
        {
            m_Refusal = "emote_provider_or_betrayal_store_unavailable";
            Print("[HollowCountry] Living AI admission refused: " + m_Refusal + "; runtime=PENDING");
        }
        else if (HCXEmoteObservation.Ready() && m_Refusal == "emote_provider_or_betrayal_store_unavailable") { m_Refusal = ""; }
        // One actor checked per tick. No world/player discovery scan.
        array<eAIBase> actors = HCXExpansionBridge.HCBaseGetAll();
        if (!actors || actors.Count() == 0) { return; }
        m_ActorCursor = m_ActorCursor % actors.Count();
        eAIBase actor = actors[m_ActorCursor];
        m_ActorCursor++;
        if (!HCXStance.Owns(actor)) { return; }
        HCXEmoteObservation.Tick(actor);
        HCReached.Mark("living_ai.actor");
        string problem = HCXAIQualification.ProviderProblem();
        if (problem == "" && (!actor.HCXAI_Fair() || actor.m_eAI_LootingBehavior != 0)) { problem = "actor finite-ammo/fairness/looting NONE assertion"; }
        bool controlFault = problem != "";
        if (problem == "" && !HCXEmoteObservation.Ready()) { problem = "emote_provider_or_betrayal_store_unavailable"; }
        if (problem != m_Refusal)
        {
            m_Refusal = problem;
            if (problem != "") { Print("[HollowCountry] Living AI admission refused: " + problem); }
        }
        if (controlFault)
        {
            actor.HCXLivingRefused = true;
            HCXExpansionBridge.HCBaseRaiseWeapon(actor, false);
            // Safety stop for provider setting drift, never an inventory move.
            HCXExpansionBridge.HCBaseSetLootingBehavior(actor, 0);
        }
        else
        {
            actor.HCXLivingRefused = false;
            if (HCXEmoteObservation.Ready() && !actor.HCXLivingUseAdmitted)
            {
                actor.HCXLivingUseAdmitted = true;
                HCModuleReadiness.HCUse("v2-expansion-living-world", "actor_admitted");
            }
        }
    }
    override void OnStop()
    {
        m_Started = false;
        HCAskForNews.Configure(false);
        HCXEmoteObservation.Stop();
        HCXAIQualification.SetEncountersEnabled(false);
    }
}
modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        HCXLivingModule livingModule = new HCXLivingModule();
        Register(livingModule);
    }
}
// Expansion AI hook implementations live in HCXExpansionBridge.c.
