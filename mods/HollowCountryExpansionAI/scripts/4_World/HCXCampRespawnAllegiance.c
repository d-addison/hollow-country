// #267. Read-only respawn admission: no targets, alerts, rays, or extra scans.
// Installed Expansion ai_scripts.pbo: eAIGroup.c:671/685 GetFaction/GetName;
// Entities/DayZPlayerImplement.c:234 GetGroup (also used by HCXStance).
// Native scripts-1.30.164289 APIs are the existing camp/stance APIs only.

modded class HCXBetrayalStore
{
    // One bounded retained-row pass per nearby AI, one UTC read. Return -1 for
    // unavailable/backward-clock evidence rather than treating it as no grudge.
    int HCCampDanger(string groupKey, string faction, map<string, bool> members)
    {
        if (!m_Healthy || !m_Validated || !m_Data || !m_Data.Rows) { return -1; }
        int nowUtc = HCGroupClock.Utc();
        if (nowUtc < 1 || nowUtc < m_Data.LastUtc) { return -1; }
        string factionKey = "HC:faction:" + faction;
        foreach (HCXAIBetrayalRow row : m_Data.Rows)
        {
            if (row.GroupKey != groupKey && row.GroupKey != factionKey) { continue; }
            if (nowUtc - row.AtUtc < m_TtlSeconds && members.Contains(row.UID)) { return 1; }
        }
        return 0;
    }
}

modded class HCXEmoteObservation
{
    static int HCCampDanger(eAIBase actor, map<string, bool> members)
    {
        if (!HCXEmoteObservation.Ready() || !actor || !actor.GetGroup()) { return -1; }
        string faction = HCXFactions.Id(actor.GetGroup().GetFaction());
        return s_Store.HCCampDanger(actor.GetGroup().GetName(), faction, members);
    }
}

modded class HCXDefence
{
    // Admission only: do not invoke Hostile(), which needs native perception
    // and can seed targets. A retained, unexpired non-rescue grudge vetoes.
    static bool HCCampDanger(eAIBase actor, map<string, bool> members)
    {
        if (!s_Running || !actor || !actor.GetGroup()) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return true; }
        foreach (HCXGrudge grudge : s_Grudges)
        {
            if (!grudge || grudge.Group != actor.GetGroup() || grudge.Until <= nowMs || grudge.Kind == HCXDefencePolicy.KIND_RESCUE) { continue; }
            if (!grudge.Attacker || !grudge.Attacker.GetIdentity()) { return true; }
            if (members.Contains(grudge.Attacker.GetIdentity().GetId())) { return true; }
        }
        return false;
    }
}

class HCXCampRespawnAllegiance : HCCampAllegianceProvider
{
    override bool IsDanger(PlayerBase actor, HCCampAllegianceContext camp)
    {
        eAIBase ai = eAIBase.Cast(actor);
        if (!GetGame() || !GetGame().IsServer() || !HCXStance.Owns(ai)) { return true; }
        if (ai.HCXLivingRefused || HCXAIQualification.ProviderProblem() != "") { return true; }
        if (HCXStance.CampRelation(ai) < 0) { return true; }
        foreach (PlayerBase member : camp.OnlineMembers)
        {
            if (!member || !member.GetIdentity() || HCXStance.CampRelation(ai, member) < 0) { return true; }
        }
        if (HCXEmoteObservation.HCCampDanger(ai, camp.Members) != 0) { return true; }
        return HCXDefence.HCCampDanger(ai, camp.Members);
    }
}

// Extend the existing camp lifecycle, independent of HC module start order.
// Owns/Ready are checked at request time; stop removes the provider reference.
modded class HCCampRespawnModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer() && IsEnabled(settings))
        {
            HCCampAllegianceHook.Install(new HCXCampRespawnAllegiance);
        }
    }

    override void OnStop()
    {
        HCCampAllegianceHook.Install(null);
        super.OnStop();
    }
}
