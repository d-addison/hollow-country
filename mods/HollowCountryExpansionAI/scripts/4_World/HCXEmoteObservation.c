// HC-5/#148/#139. Source implementation; DayZ/two-client acceptance PENDING.
// Native scripts-1.30.164289 API evidence inspected locally:
// 4_World/Classes/EmoteManager.c:127 m_bEmoteIsPlaying, :144 m_CurrentGestureID,
// :236 GetGesture returns INPUT slot (not executed ID), :629 OnCallbackEnd,
// :640-687 PlayEmote updates executed ID and returns actual playing state,
// :692-717 CreateEmoteCallback creates/sets playing; :1328 IsEmotePlaying includes REQUESTS.
// 4_World/Entities/ManBase/PlayerBase.c:1892 GetEmoteManager,
// :2116 SetSurrenderState, :8962 IsSurrendered; :3925 IsUnconscious;
// 3_Game/Global/Game.c:1119/1120 IsClient/IsServer, :1535 GetTime;
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:368 GetId;
// 3_Game/constants.c:368/393/407 greeting/hold/surrender constants;
// 4_World/Classes/EmoteClasses/EmoteClasses.c:2-6 greeting, :315-319 hold,
// :428-432 surrender use those native IDs. Clock: existing HCGroupClock.Utc.
// Installed Expansion ai_scripts.pbo: Entities/AI/eAIBase.c:9743 CanRaiseWeapon,
// :9755 RaiseWeapon(false) clears queued shots; :1276 eAI_CanFire requires raised;
// :10860/10867 Expansion_SetEmote/Expansion_PlayEmote (void; verify callback).
// Classes/FSM/States/Fighting/eAIState_Fighting_Melee.c:53 requires raised;
// Classes/Melee/eAIMeleeFightLogic_LightHeavy.c:260-276 gates new melee on raised.
// Expansion Classes/eAIGroup.c:671 GetFaction, :685 GetName.
// Existing HCXStance Owns/Visible/GetGroup/GetName seams retain their citations.
// Extend the DTO already loaded by HCXAISiteDirector; no parallel settings file.
modded class HCXAISitePolicy
{
    int BetrayalRetentionSeconds = 172800;
    int MaxBetrayalRows = 128;
    int MaxSignalWorkPerSecond = 8;
}
// One weak target per actor, no global player map or discovery. Only observed
// surrender sets this latch. Retained maintenance and native control paths use
// the observation, never poll unseen players' gesture/surrender state.

modded class EmoteManager
{
    protected int m_HCSignalSerial;
    protected int m_HCGreetingSerial;

    override protected void CreateEmoteCallback(typename callbacktype, int id, int mask, bool fullbody)
    {
        EmoteCB previous = m_Callback;
        super.CreateEmoteCallback(callbacktype, id, mask, fullbody);
        if (GetGame() && GetGame().IsServer() && m_Callback && m_Callback != previous && m_bEmoteIsPlaying)
        {
            // Count actual new callbacks, never failed/replayed PlayEmote calls.
            // Saturation refuses future waves rather than wrapping/replaying.
            if (m_HCSignalSerial < 2147483647)
            {
                m_HCSignalSerial++;
                if (m_CurrentGestureID == EmoteConstants.ID_EMOTE_GREETING) { m_HCGreetingSerial = m_HCSignalSerial; }
            }
        }
    }
    int HCSignalSerial() { return m_HCSignalSerial; }
    // Greeting-only callback acknowledgement for rendezvous baselines. Generic
    // callers retain HCSignalSerial; this token alone does not prove perception.
    int HCSignalGreetingSerial()
    {
        if (m_HCSignalSerial == 2147483647) { return 0; }
        return m_HCGreetingSerial;
    }
    int HCSignalGesture()
    {
        if (!m_bEmoteIsPlaying || m_HCSignalSerial == 2147483647) { return 0; }
        return m_CurrentGestureID;
    }
}
class HCXSignalProvider
{
    bool Ready() { return false; }
    // Must cancel queued shots AND inhibit provider ranged/melee combat against
    // this surrendered target, including subsequent provider updates. Return true
    // only on actual success. Threat zeroing alone never constitutes cease-fire.
    bool CeaseFire(eAIBase actor, PlayerBase player) { return false; }
    void Release(eAIBase actor, PlayerBase player) {}
    bool Emote(eAIBase actor, int gesture) { return false; }
    // Existing retained actor loop owns maintenance. No new global/player scan.
    void Tick(eAIBase actor) {}
    void Stop() {}
}
class HCXNativeSignalProvider : HCXSignalProvider
{
    override bool Ready() { return true; }
    override bool CeaseFire(eAIBase actor, PlayerBase player)
    {
        return actor && actor.HCXSignalCease(player);
    }
    override void Release(eAIBase actor, PlayerBase player)
    {
        if (actor) { actor.HCXSignalRelease(player); }
    }
    override bool Emote(eAIBase actor, int gesture)
    {
        if (!actor || !HCXExpansionBridge.HCBaseGetEmoteManager(actor)) { return false; }
        HCXExpansionBridge.HCBaseRaiseWeapon(actor, false);
        if (!HCXExpansionBridge.HCBaseGetEmoteManager(actor).CanPlayEmote(gesture)) { return false; }
        int before = HCXExpansionBridge.HCBaseGetEmoteManager(actor).HCSignalSerial();
        HCXExpansionBridge.HCBaseExpansion_SetEmote(actor, gesture, true, 1500);
        HCXExpansionBridge.HCBaseExpansion_PlayEmote(actor);
        return HCXExpansionBridge.HCBaseGetEmoteManager(actor).HCSignalSerial() > before && HCXExpansionBridge.HCBaseGetEmoteManager(actor).HCSignalGesture() == gesture;
    }
    override void Tick(eAIBase actor)
    {
        if (actor && actor.HCXSignalBlocked()) { HCXExpansionBridge.HCBaseRaiseWeapon(actor, false); }
    }
}
class HCXEmoteObservation
{
    protected static ref HCXSignalProvider s_Provider;
    protected static ref HCXBetrayalStore s_Store;
    protected static ref HCUnitBudget s_Units = new HCUnitBudget();
    protected static ref HCWorkBudget s_Work = new HCWorkBudget();
    protected static ref HCUnitBudget s_Events = new HCUnitBudget();
    protected static int s_EventMinute = -1;
    protected static int s_Frame = -1;
    protected static int s_MaxWork = 8;
    protected static bool s_Running;
    protected static bool s_StoreRefused;
    protected static bool s_ControlRefused;

    static void Start()
    {
        if (!GetGame() || !GetGame().IsServer() || s_Running) { return; }
        s_Running = true;
        s_Frame = -1;
        s_EventMinute = -1;
        s_StoreRefused = false;
        s_ControlRefused = false;
        HCSignalCooldown.Reset();
        s_Store = new HCXBetrayalStore();
        HCXAISitePolicy policy = HCXAISiteDirector.LoadPolicy();
        s_MaxWork = 8;
        bool configured = HCXEmoteObservation.ApplyPolicy(policy);
        if (configured) { s_Store.Open(HCGroupClock.Utc()); }
        else { Print("[HC Plan] HC-5 betrayal config refused: check expansion-ai-sites.json retention/row/work limits; runtime=PENDING"); }
        Print(HCV2Admission.Line("HC-5", true, "EXP-L3", false));
        HCXEmoteObservation.LogState();
    }
    // Boot 044: a profile policy written before HC-5 has none of the three
    // keys and they loaded as 0, which refused (quarantined) the store. A 0
    // means absent: use the default and say so once per key per start.
    static int PolicyInt(string key, int given, int fallback)
    {
        if (given != 0) { return given; }
        Print("[HC Plan] HC-5 policy " + key + " absent; default " + fallback.ToString() + " runtime=PENDING");
        return fallback;
    }
    static bool ApplyPolicy(HCXAISitePolicy policy)
    {
        if (!policy) { return false; }
        int work = HCXEmoteObservation.PolicyInt("MaxSignalWorkPerSecond", policy.MaxSignalWorkPerSecond, 8);
        int rows = HCXEmoteObservation.PolicyInt("MaxBetrayalRows", policy.MaxBetrayalRows, 128);
        int ttl = HCXEmoteObservation.PolicyInt("BetrayalRetentionSeconds", policy.BetrayalRetentionSeconds, 172800);
        if (work < 1 || work > 32) { return false; }
        s_MaxWork = work;
        return s_Store.Configure(rows, ttl);
    }
    static bool Install(HCXSignalProvider provider)
    {
        if (!GetGame() || !GetGame().IsServer() || !s_Running || s_Provider || !provider || !provider.Ready()) { return false; }
        s_Provider = provider;
        HCXEmoteObservation.LogState();
        return true;
    }
    static void LogState()
    {
        string signals = "refused:provider_control_unverified";
        if (s_Provider && s_Provider.Ready()) { signals = "supported:runtime_pending"; }
        string storeState = "quarantined";
        int rows = 0;
        if (s_Store)
        {
            rows = s_Store.Count();
            if (s_Store.Healthy()) { storeState = "ready"; }
        }
        Print("[HC Plan] HC-5 signals=" + signals + " betrayal_store=" + storeState + " text=off rows=" + rows.ToString() + " gesture_work_per_second<=" + s_MaxWork.ToString() + " betrayal_events_per_minute<=32 runtime=PENDING");
    }
    static void Stop()
    {
        s_Running = false;
        if (s_Provider) { s_Provider.Stop(); }
        s_Provider = null;
        s_Store = null;
        s_Frame = -1;
        s_EventMinute = -1;
        HCSignalCooldown.Reset();
    }
    static bool ControlReady()
    {
        return GetGame() && GetGame().IsServer() && s_Running && s_Provider && s_Provider.Ready();
    }
    static bool Ready()
    {
        return HCXEmoteObservation.ControlReady() && s_Store && s_Store.Healthy();
    }
    static bool Work()
    {
        if (!GetGame() || !GetGame().IsServer() || !HCXEmoteObservation.ControlReady()) { return false; }
        int frame = GetGame().GetTime() / 1000;
        if (s_Frame != frame)
        {
            s_Frame = frame;
            s_Units.HCReset(s_MaxWork);
            s_Work.HCReset(s_MaxWork);
        }
        return s_Units.HCTake(1) && s_Work.HCContinue();
    }
    static void Tick(eAIBase actor)
    {
        // Cleanup/cease-fire maintenance must not starve behind gesture work.
        // Caller owns its existing one-actor retained cursor/budget.
        if (s_Running && s_Provider && actor) { s_Provider.Tick(actor); }
    }
    static bool EventWork()
    {
        // Durability must not depend on gesture time/work. Shared deterministic
        // unit accounting caps new events at 32 per server minute, no clock IO.
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return false; }
        int minute = nowMs / 60000;
        if (s_EventMinute != minute)
        {
            s_EventMinute = minute;
            s_Events.HCReset(32);
        }
        return s_Events.HCTake(1);
    }
    static void Remember(eAIBase actor, PlayerBase player, string faction = "")
    {
        if (!s_Running || !GetGame() || !GetGame().IsServer() || !s_Store || !actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || !player || !player.GetIdentity()) { return; }
        if (HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) == HCXExpansionBridge.HCDayZPlayerImplementGetGroup(player)) { return; }
        if (!s_Store.ValidKey(HCXExpansionBridge.HCGroupGetName(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor))) || !s_Store.ValidKey(player.GetIdentity().GetId())) { return; }
        // Repeated EEHitBy callbacks for an existing receipt are a cheap no-op.
        // Explicit later Remember calls on the store can refresh retention.
        if (s_Store.Has(HCXExpansionBridge.HCGroupGetName(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)), player.GetIdentity().GetId()) && (faction == "" || s_Store.HasFaction(faction, player.GetIdentity().GetId()))) { return; }
        if (!HCXEmoteObservation.EventWork())
        {
            HCXEmoteObservation.RefuseControl("betrayal_event_cap");
            return;
        }
        int eventUtc = HCGroupClock.Utc();
        bool saved = s_Store.Remember(HCXExpansionBridge.HCGroupGetName(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)), player.GetIdentity().GetId(), eventUtc);
        if (saved && faction != "") { saved = s_Store.RememberFaction(faction, player.GetIdentity().GetId(), eventUtc); }
        if (!saved && !s_Store.Healthy() && !s_StoreRefused)
        {
            s_StoreRefused = true;
            Print("[HC Plan] HC-5 signals=refused betrayal_store=quarantined text=off runtime=PENDING");
        }
    }
    static bool Grudge(eAIBase actor, PlayerBase player)
    {
        if (!s_Running || !s_Store || !actor || !HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor) || !player || !player.GetIdentity()) { return false; }
        if (s_Store.Has(HCXExpansionBridge.HCGroupGetName(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)), player.GetIdentity().GetId())) { return true; }
        string faction = HCXFactions.Id(HCXExpansionBridge.HCGroupGetFaction(HCXExpansionBridge.HCDayZPlayerImplementGetGroup(actor)));
        return s_Store.HasFaction(faction, player.GetIdentity().GetId());
    }
    static bool Surrender(eAIBase actor, PlayerBase player, bool observed)
    {
        if (!HCXEmoteObservation.ControlReady() || !actor || !player || !observed) { return false; }
        if (HCXDefence.HCHitRecorded(actor, player))
        {
            // A new attack also releases a prior surrender latch immediately.
            // The owner's bounded defence deadline survives raised hands.
            s_Provider.Release(actor, player);
            return false;
        }
        bool surrendered = player.IsSurrendered();
        if (!surrendered) { s_Provider.Release(actor, player); return false; }
        if (!HCStancePolicy.CeaseForSurrender(GetGame().IsServer(), observed, surrendered)) { return false; }
        if (s_Provider.CeaseFire(actor, player)) { return true; }
        HCXEmoteObservation.RefuseControl("cease_fire_failed");
        return false;
    }
    static void RefuseControl(string reason)
    {
        if (s_ControlRefused) { return; }
        s_ControlRefused = true;
        Print("[HC Plan] HC-5 signals=refused:" + reason + " betrayal_store=unchanged text=off runtime=PENDING");
    }
    // Caller supplies native LOS plus fresh geometry (as CalculateThreat does).
    // Never discovers a player or reads gestures without that perception proof.
    static bool HCObservedGreeting(eAIBase actor, PlayerBase player, bool observed, int baseline)
    {
        if (!observed || baseline < 0 || !HCXEmoteObservation.ControlReady() || !actor || !player || !player.GetEmoteManager()) { return false; }
        return player.GetEmoteManager().HCSignalGesture() == EmoteConstants.ID_EMOTE_GREETING && player.GetEmoteManager().HCSignalSerial() > baseline;
    }
    static int Wave(eAIBase actor, PlayerBase player, bool observed, int consumed)
    {
        if (!observed || !HCXEmoteObservation.Ready() || !actor || !player || !player.GetEmoteManager()) { return consumed; }
        int serial = player.GetEmoteManager().HCSignalSerial();
        bool greeting = player.GetEmoteManager().HCSignalGesture() == EmoteConstants.ID_EMOTE_GREETING;
        bool neutral = HCXStance.Relation(actor, player) >= 0;
        bool grudge = HCXEmoteObservation.Grudge(actor, player);
        // Non-greeting gestures never count. Consume an observed greeting even
        // if cooldown/provider refuses, so standing in the same wave cannot replay.
        if (!observed || !greeting || serial <= consumed) { return consumed; }
        bool allowed = HCStancePolicy.ReplyWave(GetGame().IsServer(), observed, neutral, HCXStance.RaisedWeapon(player), grudge, serial, consumed, GetGame().GetTime(), 0);
        if (allowed && HCSignalCooldown.Allowed(player) && HCXEmoteObservation.Work())
        {
            if (s_Provider.Emote(actor, EmoteConstants.ID_EMOTE_GREETING)) { HCSignalCooldown.Claim(player); }
            else { HCXEmoteObservation.RefuseControl("emote_failed"); }
        }
        return serial;
    }
    static bool Warn(eAIBase actor, PlayerBase player)
    {
        // HCXWarning.NextWarning owns the per-actor warning interval. Greeting
        // replies must never suppress this actor or a neighbour's warning.
        if (!HCXEmoteObservation.Work()) { return false; }
        if (s_Provider.Emote(actor, EmoteConstants.ID_EMOTE_HOLD)) { return true; }
        HCXEmoteObservation.RefuseControl("emote_failed");
        return false;
    }
}
// Expansion AI hook implementations live in HCXExpansionBridge.c.
