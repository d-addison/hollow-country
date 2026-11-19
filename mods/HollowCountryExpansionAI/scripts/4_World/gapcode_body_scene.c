// Original death producer; no provider code copied. Native snapshot 1.30.164289:
// 3_Game/gameplay.c:636 GetGame; Global/Game.c:1120 IsServer;
// Entities/Object.c:517 IsAlive; Entities/Man.c:21 GetIdentity;
// Entities/EntityAI.c:1104 EEKilled; 1_Core/proto/EnScript.c:380 Count, :94 Cast;
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print.
// Expansion xref/ai/4_World/DayZExpansion_AI/Entities/AI/eAIBase.c:1368-1374
// EEKilled forwards to native; Entities/DayZPlayerImplement.c:234 GetGroup,
// :431-438 defers group cleanup to next frame; Classes/eAIGroup.c:1139
// GetMember, :1185 Count; Classes/Patrols/eAIDynamicPatrol.c:45 m_Group.
// Other calls are HC interfaces. No inventory, actor or route mutations.
class HCGapBodySceneProducer : HCBodyStoryProducer
{
    override bool HCReady()
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        return director && director.Phase() == "run" && HCSituationSource.HCState() && HCSituationSource.HCStore();
    }

    static HCSituationState HCStory(string lease)
    {
        HCSceneChainState source = HCSituationSource.HCState();
        if (!source || !source.Stories) { return null; }
        HCSituationState first = source.Stories.HCFirstSurvivor;
        if (first && first.Lease == lease && first.Phase == "active") { return first; }
        array<ref HCSituationState> situations = source.Stories.HCSituations;
        if (!situations) { return null; }
        foreach (HCSituationState situation : situations)
        {
            if (situation && situation.Lease == lease && situation.Phase == "active") { return situation; }
        }
        return null;
    }

    static void HCObserve(eAIBase corpse)
    {
        HCBodyStories stories = HCBodyStories.Get();
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCWorldModule world = HCWorldModule.Get();
        if (!stories || !director || director.Phase() != "run" || !world || !corpse) { return; }
        if (corpse.IsAlive() || corpse.GetIdentity() || !stories.HCCanObserveOwnedDeath()) { return; }
        eAIGroup group = corpse.GetGroup();
        if (!group) { return; }
        array<ref HCXAISiteState> sites = director.States();
        foreach (HCXAISiteState site : sites)
        {
            if (!site || !site.Transient || !site.Materialized || site.Completed || !site.Patrol || site.Patrol.m_Group != group) { continue; }
            HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(site.ProposalId);
            HCWorldProposal proposal = HCWorldMaterializer.HCBodyProposal(site.ProposalId);
            HCSituationState story = HCGapBodySceneProducer.HCStory(site.ProposalId);
            if (!identity || !proposal || !story || identity.HCGeneration() != world.Epoch()) { stories.HCRefuse("OWNED_DEATH_WITHOUT_RETAINED_SITUATION"); return; }
            if (!HCGapBodySceneProducer.HCPublish(corpse, group, site, proposal, story, world, stories))
            {
                stories.HCRefuse("OWNED_DEATH_WORLD_FACT_UNAVAILABLE");
            }
            return;
        }
    }

    static bool HCPublish(eAIBase corpse, eAIGroup group, HCXAISiteState site, HCWorldProposal proposal, HCSituationState story, HCWorldModule world, HCBodyStories stories)
    {
        // Count the actual still-associated native members at the death callback.
        // Include the casualty even if a provider link already excluded it.
        int survivors;
        int total;
        bool countedCorpse;
        int members = group.Count();
        if (members > proposal.ActorCap || site.Patrol.m_HCPendingMembers > 0) { return false; }
        for (int memberIndex = 0; memberIndex < members; memberIndex++)
        {
            DayZPlayerImplement member = group.GetMember(memberIndex);
            if (!member) { continue; }
            total++;
            if (member == corpse) { countedCorpse = true; }
            if (member.IsAlive()) { survivors++; }
        }
        if (!countedCorpse) { total++; }
        // Existing fact vocabulary and delayed lead policy, at the party's
        // admitted named place. No killer identity or live coordinates are news.
        string place = proposal.PlaceId;
        if (!HCLeadPolicy.KnownPlace(place)) { return false; }
        string kind = proposal.FactionId + "_survivors_" + survivors.ToString() + "_of_" + total.ToString();
        int observedAt = HCWorldClock.UTC();
        if (!world.AddFact(kind, place, 1)) { return false; }
        int publishedAt = HCWorldClock.UTC();
        array<ref HCWorldFact> facts = new array<ref HCWorldFact>;
        world.GetRecentFacts(HCWorldLimits.FACT_LIFETIME, facts);
        foreach (HCWorldFact fact : facts)
        {
            if (fact.Kind != kind || fact.PlaceId != place || fact.At < observedAt || fact.At > publishedAt) { continue; }
            stories.HCQueueOwnedDeath(story.Id, fact, corpse);
            return true;
        }
        return false;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        HCGapBodySceneProducer producer = new HCGapBodySceneProducer;
        HCBodyStories.HCBindProducer(producer);
        super.RegisterModules();
    }
}

modded class eAIBase
{
    protected bool m_HCGapBodyDeathSent;
    override void EEKilled(Object killer)
    {
        super.EEKilled(killer);
        if (m_HCGapBodyDeathSent || !GetGame() || !GetGame().IsServer()) { return; }
        m_HCGapBodyDeathSent = true;
        if (!HCBodyStories.Get()) { return; } // EnableLeads opt-out
        HCGapBodySceneProducer.HCObserve(this);
    }
}
