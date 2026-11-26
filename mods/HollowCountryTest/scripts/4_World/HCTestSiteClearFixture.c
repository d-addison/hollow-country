// Dev-only bounded clear. No synthetic death, hold or counter calls.
// Native scripts-1.30.164289: Object.c:215/287/517 IsPendingDeletion/GetPosition/IsAlive,
// :1015 SetHealth, :1128-1138 ProcessDirectDamage (source is EntityAI; coefficient multiplies
// CfgAmmo damage). EntityAI.c:1104 EEKilled(Object killer). Game.c:612 ConfigIsExisting,
// :1535 GetTime, :1550 GetCallQueue; 2_GameLib/tools.c:61 CallLater;
// 3_Game/Entities/Man.c:21 GetIdentity (disconnected requesters are refused).
// Core natives: 1_Core/proto/EnMath.c:553 Min; EnConvert.c:210 DistanceSq;
// EnString.c:113/199/240 Substring/Length/IndexOf (prefix copies only three characters).
// Native weapons_projectiles config.bin: CfgAmmo Bullet_556x45, Bullet_Base child, scope 1;
// DamageSystem.c:10-13 FIRE_ARM; check the live config too. Killer attribution still needs a native EEKilled experiment.
class HCTestSiteClearFixture
{
    protected static ref HCTestSiteClearFixture s_Run;
    static int HCMode;
    protected static string s_PreviousSite;
    // Engine handles and the patrol are weak; never keep a group/member across callbacks.
    protected PlayerBase m_Requester;
    protected HCXAISitePatrol m_Patrol;
    protected vector m_Anchor;
    protected string m_Site = "none";
    protected string m_Kind = "site";
    protected string m_Mode = "attributed";
    protected string m_Last = "none";
    protected int m_Started;
    protected int m_LastKill;
    protected int m_Kills;
    protected int m_Limit;
    protected int m_HeldMs;
    protected int m_LastTick;
    protected bool m_Done;
    protected DayZPlayerImplement m_ExpectedVictim;
    protected bool m_Attributed;

    static bool HCStart(PlayerBase requester, out string reason)
    {
        reason = "busy";
        if (s_Run && !s_Run.m_Done)
        {
            string busyMode = "attributed";
            if (HCMode == 1) { busyMode = "health"; }
            Print("[HC Test] fx_site_clear site=none mode=" + busyMode + " result=refused:busy kills=0 elapsed_s=0 last=none");
            return false;
        }
        s_Run = new HCTestSiteClearFixture;
        s_Run.m_Requester = requester;
        s_Run.m_Started = GetGame().GetTime();
        s_Run.m_LastTick = s_Run.m_Started;
        if (HCMode == 1) { s_Run.m_Mode = "health"; }
        reason = "requester-unavailable";
        if (!requester || requester.IsPendingDeletion() || !requester.IsAlive() || !requester.GetIdentity()) { s_Run.HCFinish("refused:" + reason); return false; }
        reason = "mode";
        if (HCMode < 0 || HCMode > 1) { s_Run.HCFinish("refused:" + reason); return false; }
        reason = "ammo-unavailable";
        if (HCMode == 0 && !GetGame().ConfigIsExisting("CfgAmmo Bullet_556x45")) { s_Run.HCFinish("refused:" + reason); return false; }
        reason = "no-patrol";
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director || director.Phase() != "run") { s_Run.HCFinish("refused:not-ready"); reason = "not-ready"; return false; }
        array<ref HCXAISiteState> states = director.States();
        float bestScore = float.MAX;
        int bounded = Math.Min(states.Count(), 4096);
        for (int index = 0; index < bounded; index++)
        {
            HCXAISiteState state = states[index];
            if (!state || !state.Patrol) { continue; }
            HCXAISitePatrol patrol = state.Patrol;
            if (!patrol.m_HCLive || patrol.m_HCFinished) { continue; }
            if (patrol.HCDeathHeld() || patrol.m_HCPendingMembers > 0) { reason = "not-ready"; continue; }
            HCXAIGroupHold candidateHold = patrol.HCGroupHold();
            int count = HCXExpansionBridge.HCHoldCount(candidateHold);
            if (count < 1 || count > 16) { continue; }
            float distanceSq = float.MAX;
            vector anchor;
            for (int slot = 0; slot < count; slot++)
            {
                DayZPlayerImplement member = HCXExpansionBridge.HCHoldGetMember(candidateHold, slot);
                if (!member || member.IsPendingDeletion() || !member.IsAlive()) { continue; }
                float memberSq = vector.DistanceSq(member.GetPosition(), requester.GetPosition());
                if (memberSq < distanceSq) { distanceSq = memberSq; anchor = member.GetPosition(); }
            }
            if (distanceSq > 250000) { continue; }
            string siteId = patrol.m_HCSiteId;
            if (siteId.Length() < 3 || siteId.Length() > 96) { continue; }
            bool zoneSite = siteId.Substring(0, 3) == "zg-";
            float score = distanceSq;
            if (!zoneSite) { score += 1000000; }
            if (!zoneSite && patrol.m_HCSiteId != "police-chernogorsk") { score += 1000000; }
            if (patrol.m_HCSiteId == s_PreviousSite) { score += 10000000; }
            if (score >= bestScore) { continue; }
            bestScore = score;
            s_Run.m_Patrol = patrol;
            s_Run.m_Limit = count;
            s_Run.m_Anchor = anchor;
        }
        if (!s_Run.m_Patrol) { s_Run.HCFinish("refused:" + reason); return false; }
        s_Run.m_Site = s_Run.m_Patrol.m_HCSiteId;
        if (s_Run.m_Site.IndexOf("zg-") == 0) { s_Run.m_Kind = "zone"; }
        s_PreviousSite = s_Run.m_Site;
        reason = "started";
        Print("[HC Test] fx_site_clear site=" + s_Run.m_Site + " mode=" + s_Run.m_Mode + " start=1 reason=live-patrol-selected");
        s_Run.HCTick();
        return true;
    }

    static void HCObserveDeath(DayZPlayerImplement victim, Object killer)
    {
        if (!s_Run || s_Run.m_Done || victim != s_Run.m_ExpectedVictim) { return; }
        s_Run.m_Attributed = killer && killer == s_Run.m_Requester;
    }

    protected void HCFinish(string result)
    {
        m_Done = true;
        int elapsed = (GetGame().GetTime() - m_Started) / 1000;
        Print("[HC Test] fx_site_clear site=" + m_Site + " mode=" + m_Mode + " result=" + result + " kills=" + m_Kills.ToString() + " elapsed_s=" + elapsed.ToString() + " last=" + m_Last);
        m_ExpectedVictim = null;
        m_Requester = null;
        m_Patrol = null;
    }

    void HCTick()
    {
        if (HCServer.HCMissionFinishing()) { HCFinish("refused:mission-finishing"); return; }
        if (m_Done) { return; }
        int now = GetGame().GetTime();
        if (m_Kills > 0 && m_Patrol && !m_Patrol.m_HCLive)
        {
            // Lifecycle observation only: report parsing verifies cleared-at/despawned/abandoned.
            m_Last = "patrol-not-live";
            HCFinish("terminal");
            return;
        }
        if (now - m_Started >= 180000) { HCFinish("timeout"); return; }
        if (!m_Patrol || m_Patrol.m_HCFinished) { HCFinish("refused:patrol-unavailable"); return; }
        if (!m_Requester || m_Requester.IsPendingDeletion() || !m_Requester.IsAlive() || !m_Requester.GetIdentity()) { HCFinish("refused:requester-unavailable"); return; }
        if (vector.DistanceSq(m_Requester.GetPosition(), m_Anchor) > 250000) { HCFinish("refused:requester-range"); return; }
        bool held = m_Patrol.HCDeathHeld();
        if (held) { m_HeldMs += now - m_LastTick; m_Last = "death-held"; }
        m_LastTick = now;
        if (!held && (m_Kills == 0 || now - m_LastKill >= 6000))
        {
            if (m_Kills >= m_Limit || m_Kills >= 16) { HCFinish("refused:member-budget"); return; }
            if (m_Patrol.m_HCPendingMembers > 0) { HCFinish("refused:not-ready"); return; }
            // Fresh weak snapshot before each damage call. Never touch the group after damage.
            array<DayZPlayerImplement> members = new array<DayZPlayerImplement>;
            HCXAIGroupHold hold = m_Patrol.HCGroupHold();
            int count = HCXExpansionBridge.HCHoldCount(hold);
            if (count > 16) { HCFinish("refused:member-limit"); return; }
            DayZPlayerImplement victim;
            float nearestSq = 250000;
            for (int slot = 0; slot < count; slot++)
            {
                DayZPlayerImplement member = HCXExpansionBridge.HCHoldGetMember(hold, slot);
                if (!member || member.IsPendingDeletion() || !member.IsAlive()) { continue; }
                members.Insert(member);
                float distanceSq = vector.DistanceSq(member.GetPosition(), m_Requester.GetPosition());
                if (distanceSq < nearestSq) { nearestSq = distanceSq; victim = member; }
            }
            if (victim)
            {
                m_ExpectedVictim = victim;
                m_Attributed = false;
                if (m_Mode == "health") { victim.SetHealth("", "", 0); }
                else { victim.ProcessDirectDamage(DamageType.FIRE_ARM, m_Requester, "", "Bullet_556x45", "0 0 0", 1000); }
                if (victim && !victim.IsPendingDeletion() && victim.IsAlive()) { HCFinish("refused:damage-not-lethal"); return; }
                m_Kills++;
                m_LastKill = now;
                m_ExpectedVictim = null;
                m_Last = "victim-dead";
                if (m_Attributed) { m_Last = "requester-eekilled"; }
                int left = 0;
                foreach (DayZPlayerImplement observed : members)
                {
                    if (observed && !observed.IsPendingDeletion() && observed.IsAlive()) { left++; }
                }
                Print("[HC Test] fx_site_clear site=" + m_Site + " kind=" + m_Kind + " mode=" + m_Mode + " kill=" + m_Kills.ToString() + " members_left=" + left.ToString() + " held_ms=" + m_HeldMs.ToString());
                m_HeldMs = 0;
                if (m_Mode == "attributed" && !m_Attributed) { HCFinish("refused:attribution-unconfirmed"); return; }
            }
        }
        // Exactly one non-repeating chain; mission finishing is checked before any re-arm.
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTick, 1000, false);
    }
}

modded class HCAdminModule
{
    override bool HCCommand(PlayerIdentity sender, string command, int value, int ticket)
    {
        // Numeric transport: default/0 = mode=attributed, 1 = mode=health.
        HCTestSiteClearFixture.HCMode = value;
        bool done = super.HCCommand(sender, command, value, ticket);
        HCTestSiteClearFixture.HCMode = 0;
        return done;
    }
}

// Native PlayerBase.c:1214 EEKilled override. Observe the engine event on the native
// ancestor; never invoke EEKilled manually or credit a counter here.
modded class PlayerBase
{
    override void EEKilled(Object killer)
    {
        HCTestSiteClearFixture.HCObserveDeath(this, killer);
        super.EEKilled(killer);
    }
}
