// #147 spec -> plan -> tasks: borrow a live HC-10 party, save HC-38 intent,
// request finite native walking/threat placement, observe, restore its route.
// Original integration; Expansion sources inspected, never copied.
// Expansion xref/ai/4_World/DayZExpansion_AI/Classes/eAIGroup.c:
// :213 AddWaypoint, :222 GetWaypoints, :241 ClearWaypoints,
// :251 SetWaypointBehaviour, :304 GetWaypointBehaviour, :1123 IsInCombat,
// :1139 GetMember, :1185 Count. Combat targets remain perception-owned.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:703 CreateObjectEx,
// :1120 IsServer, :1180 SurfaceGetType; gameplay.c:636 GetGame;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive, :215 IsPendingDeletion;
// 4_World/Static/MiscGameplayFunctions.c:1094 IsUnderRoof;
// 3_Game/CE/CentralEconomy.c:18 ECE_INITAI, :38 ECE_PLACE_ON_SURFACE;
// 1_Core/proto/EnScript.c:380 Count, :385 Clear, :394 Find, :407 Insert;
// 1_Core/proto/EnDebug.c:96 Print; EnSystem.c:397 FileExist; EnScript.c:463 Remove.
// Native Game.c:930 GetObjectsAtPosition3D; EnConvert.c:210 DistanceSq.
// No actor teleport, new AI owner, target assignment, door change or loot mint.
class HCW38SituationBinding
{
    string Id;
    string Lease;
    string Profile;
    eAIGroup Group;
    eAIWaypointBehavior Behaviour;
    ref array<vector> Original = new array<vector>;
    ref array<eAIBase> Members = new array<eAIBase>;
    ref array<ZombieBase> Threats = new array<ZombieBase>;
}

class HCW38SituationRuntime
{
    protected static ref HCW38SituationPolicy s_Policy;
    protected static ref HCW38SituationBinding s_Active;
    protected static bool s_Logged;
    protected static int s_Cursor;
    protected static int s_SelectedIndex = -1;
    protected static int s_TargetCursor;
    protected static string s_Refusal;
    protected static bool s_SmokePending;
    protected static bool s_FactPending;
    protected static ref array<ZombieBase> s_Threats = new array<ZombieBase>;

    static bool HCRefuse(string reason)
    {
        if (s_Refusal != reason)
        {
            s_Refusal = reason;
            Print("[HC Situations] waiting reason=" + reason + " runtime=PENDING");
        }
        return false;
    }

    static HCW38SituationPolicy HCPolicy()
    {
        s_Policy = HCW38SituationPolicy.HCGet();
        if (!s_Policy) { HCRefuse("SITUATION_POLICY_INVALID"); }
        return s_Policy;
    }

    static bool HCReady()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (FileExist("$profile:HollowCountry/acceptance/w38_situations.disable")) { return HCRefuse("SITUATION_OPERATOR_OFF"); }
        if (!s_Logged)
        {
            s_Logged = true;
            Print(HCV2Admission.Line("Situations", true, "w38_situations", false) + " runtime=PENDING");
            Print("[HC Situations] SITUATION_VEHICLE_DRIVING_PORT_MISSING road_branch=walking_caravan runtime=PENDING");
        }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!HCPolicy()) { return false; }
        if (!director || director.Phase() != "run") { return HCRefuse("SITUATION_SITE_DIRECTOR_PENDING"); }
        return true;
    }

    static string HCReason()
    {
        if (s_Refusal == "") { return "SITUATION_SITE_DIRECTOR_PENDING"; }
        return s_Refusal;
    }

    static bool HCCandidate(HCXAISiteState candidate)
    {
        if (!candidate || !candidate.Transient || !candidate.Materialized || !candidate.Qualified || candidate.Completed) { return false; }
        if (!HCWorldMaterializer.HCIdentity(candidate.ProposalId) || !candidate.Patrol || !candidate.Patrol.m_Group) { return false; }
        return candidate.Patrol.m_Group.Count() > 0 && candidate.Patrol.m_HCPendingMembers == 0;
    }

    static bool HCUsed(string lease)
    {
        HCSceneChainState source = HCSituationSource.HCState();
        if (!source || !source.Stories) { return true; }
        if (source.Stories.HCFirstSurvivor && source.Stories.HCFirstSurvivor.Lease == lease) { return true; }
        array<ref HCSituationState> history = source.Stories.HCSituations;
        if (history)
        {
            foreach (HCSituationState prior : history)
            {
                if (prior && prior.Lease == lease) { return true; }
            }
        }
        return false;
    }

    static bool HCProfileFits(HCXAISiteState candidate, string profile)
    {
        eAIGroup group = candidate.Patrol.m_Group;
        if (group.Count() > s_Policy.MaxMembers || group.IsInCombat()) { return false; }
        if (candidate.PatrolPoints.Count() < 2 || candidate.PatrolPoints.Count() > s_Policy.MaxRouteNodes) { return false; }
        if (profile == "raid" || profile == "column") { return candidate.ProviderFaction == "HCRaiders"; }
        if (candidate.ProviderFaction == "HCRaiders") { return false; }
        eAIBase leader = eAIBase.Cast(group.GetMember(0));
        if (!leader || !leader.IsAlive()) { return false; }
        if (profile == "survivor") { return MiscGameplayFunctions.IsUnderRoof(leader); }
        string surface;
        vector at = leader.GetPosition();
        GetGame().SurfaceGetType(at[0], at[2], surface);
        return surface == s_Policy.RoadSurface;
    }

    static bool HCProfileOn(string profile)
    {
        if ((profile == "raid" || profile == "column") && FileExist("$profile:HollowCountry/acceptance/w38_raids.disable")) { return false; }
        if ((profile == "roadside-position" || profile == "threatened-exodus") && FileExist("$profile:HollowCountry/acceptance/w38_transit.disable")) { return false; }
        return true;
    }

    static bool HCRaidCooled(string profile)
    {
        if (profile != "raid" && profile != "column") { return true; }
        int cooldown = HCCampRaidSituation.HCCooldown(profile);
        if (cooldown < 0) { return HCRefuse("SITUATION_RAID_PROFILE_PENDING"); }
        HCSceneChainState source = HCSituationSource.HCState();
        if (!source || !source.Stories) { return false; }
        array<ref HCSituationState> history = source.Stories.HCSituations;
        if (!history) { return true; }
        int now = HCGroupClock.Utc() - 1577836800;
        if (now < 1 || now > 999000000) { return false; }
        foreach (HCSituationState prior : history)
        {
            if (!prior || prior.Phase == "pending") { continue; }
            if (prior.Profile != "raid" && prior.Profile != "column") { continue; }
            // EndsAt is a durable upper bound, not an invented closure time.
            // Conservative cooldown survives restart without a new store.
            if (now < prior.EndsAt + cooldown) { return false; }
        }
        return true;
    }

    static string HCSelect(HCSituationState opportunity)
    {
        if (!opportunity || !HCProfileOn(opportunity.Profile) || !HCReady() || s_Active) { return ""; }
        if (!HCRaidCooled(opportunity.Profile)) { return ""; }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() == 0) { return ""; }
        for (int visited = 0; visited < s_Policy.ScanRows && visited < states.Count(); visited++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return ""; }
            s_Cursor = s_Cursor % states.Count();
            HCXAISiteState candidate = states[s_Cursor];
            s_Cursor++;
            if (!HCCandidate(candidate) || HCUsed(candidate.ProposalId)) { continue; }
            if (!HCProfileFits(candidate, opportunity.Profile)) { continue; }
            if ((opportunity.Profile == "raid" || opportunity.Profile == "column") && !HCTarget(candidate)) { continue; }
            s_SelectedIndex = s_Cursor - 1;
            return candidate.ProposalId;
        }
        HCRefuse("SITUATION_MATCHING_LIVE_PARTY_PENDING");
        return "";
    }

    static HCXAISiteState HCFind(string lease)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!director) { return null; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || s_SelectedIndex < 0 || s_SelectedIndex >= states.Count()) { return null; }
        HCXAISiteState candidate = states[s_SelectedIndex];
        if (HCCandidate(candidate) && candidate.ProposalId == lease) { return candidate; }
        return null;
    }

    static void HCRestore(HCW38SituationBinding binding)
    {
        if (!binding || !binding.Group) { return; }
        binding.Group.ClearWaypoints();
        array<vector> original = binding.Original;
        foreach (vector point : original) { binding.Group.AddWaypoint(point); }
        binding.Group.SetWaypointBehaviour(binding.Behaviour);
    }

    static HCXAISiteState HCTarget(HCXAISiteState party)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        HCHoldouts camps = HCHoldouts.Get();
        if (!camps || !director) { return null; }
        array<ref HCXAISiteState> states = director.States();
        if (!states || states.Count() == 0) { return null; }
        for (int checked = 0; checked < s_Policy.ScanRows && checked < states.Count(); checked++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return null; }
            s_TargetCursor = s_TargetCursor % states.Count();
            HCXAISiteState target = states[s_TargetCursor];
            s_TargetCursor++;
            if (!HCCandidate(target) || target == party || target.ProviderFaction == party.ProviderFaction) { continue; }
            HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(target.ProposalId);
            HCAICampRoutineView view = camps.HCRoutineView(identity);
            if (!view || !view.Home || view.Supply < 1 || view.Population < 1) { continue; }
            if (view.Home.State != "OCCUPIED" && view.Home.State != "ALERT") { continue; }
            if (HCWorldFactionCatalog.Relation("raiders", view.Home.FactionId) != -1) { continue; }
            if (target.PatrolPoints.Count() < 1) { continue; }
            if (vector.DistanceSq(party.PatrolPoints[0], target.PatrolPoints[0]) > s_Policy.MaxRaidMeters * s_Policy.MaxRaidMeters) { continue; }
            return target;
        }
        return null;
    }

    static bool HCRaid(HCXAISiteState party, HCW38SituationBinding binding)
    {
        HCXAISiteState target = HCTarget(party);
        if (!target) { return HCRefuse("SITUATION_HOSTILE_CAMP_PENDING"); }
        // The camp ledger remembers this home. No enemy entity/target is fed
        // to the AI; native perception discovers opponents while walking.
        binding.Group.ClearWaypoints();
        binding.Group.AddWaypoint(party.PatrolPoints[0]);
        binding.Group.AddWaypoint(target.PatrolPoints[0]);
        binding.Group.SetWaypointBehaviour(eAIWaypointBehavior.HALT);
        return true;
    }

    // A one-point HALT is a native movement request; combat stays entirely
    // perception-owned. Restore the saved route on release, never SetPosition.
    static void HCHold(HCW38SituationBinding binding)
    {
        if (binding.Profile != "survivor") { return; }
        eAIBase sheltered = eAIBase.Cast(binding.Group.GetMember(0));
        if (!sheltered) { return; }
        binding.Group.ClearWaypoints();
        binding.Group.AddWaypoint(sheltered.GetPosition());
        binding.Group.SetWaypointBehaviour(eAIWaypointBehavior.HALT);
    }

    static void HCSignals(HCW38SituationBinding binding)
    {
        eAIBase witness = eAIBase.Cast(binding.Group.GetMember(0));
        if (!witness) { return; }
        if (!HCSituationSignals.HCPublish(witness.GetPosition()) && !s_FactPending)
        {
            s_FactPending = true;
            Print("[HC Situations] SITUATION_FACT_PLACE_PENDING discovery=native_perception runtime=PENDING");
        }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(witness.GetPosition(), s_Policy.ShelterMeters, nearby, proxies);
        // Native query allocates before this bound; target-load cost unmeasured.
        if (nearby.Count() > s_Policy.PhysicalScanObjects) { return; }
        HCXAISiteDirector signalDirector = HCXAISiteDirector.Active();
        if (!signalDirector) { return; }
        foreach (Object signalCandidate : nearby)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 1)) { return; }
            if (!SmokeGrenadeBase.Cast(signalCandidate)) { continue; }
            if (signalDirector.MemberProblemFor(signalCandidate.GetPosition()) != "") { continue; }
            if (HCSituationSignals.HCSmoke(signalCandidate)) { return; }
        }
        if (!s_SmokePending)
        {
            s_SmokePending = true;
            Print("[HC Situations] SITUATION_SMOKE_STOCK_PENDING discovery=gunfire_and_shared_facts runtime=PENDING");
        }
    }

    static bool HCThreaten(HCXAISiteState party, HCW38SituationBinding binding)
    {
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        int threatIndex = s_Threats.Count() - 1;
        while (threatIndex >= 0)
        {
            ZombieBase existingThreat = s_Threats[threatIndex];
            if (!existingThreat || existingThreat.IsPendingDeletion() || !existingThreat.IsAlive()) { s_Threats.Remove(threatIndex); }
            threatIndex = threatIndex - 1;
        }
        if (s_Threats.Count() >= s_Policy.MaxThreats) { return HCRefuse("SITUATION_THREAT_CAP"); }
        array<vector> points = party.PatrolPoints;
        eAIBase leader = eAIBase.Cast(binding.Group.GetMember(0));
        if (!leader) { return false; }
        int inspected = 0;
        string threatSurface;
        foreach (vector position : points)
        {
            if (inspected >= s_Policy.MaxRouteNodes || s_Threats.Count() >= s_Policy.MaxThreats) { break; }
            inspected++;
            if (vector.DistanceSq(position, leader.GetPosition()) > s_Policy.ShelterMeters * s_Policy.ShelterMeters) { continue; }
            if (binding.Profile == "roadside-position" || binding.Profile == "threatened-exodus")
            {
                GetGame().SurfaceGetType(position[0], position[2], threatSurface);
                if (threatSurface != s_Policy.RoadSurface) { continue; }
            }
            if (director.MemberProblemFor(position) != "") { continue; }
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATIONS, 8)) { break; }
            // Placement is a qualified existing navmesh point, checked out of
            // every player's sight by the existing site director immediately
            // before creation. No combat target is assigned to the infected.
            ZombieBase infected = ZombieBase.Cast(GetGame().CreateObjectEx(s_Policy.InfectedClass, position, ECE_INITAI | ECE_PLACE_ON_SURFACE));
            if (infected) { binding.Threats.Insert(infected); s_Threats.Insert(infected); }
        }
        return binding.Threats.Count() > 0;
    }

    static bool HCBegin(HCSituationState opportunity)
    {
        if (!opportunity || !HCProfileOn(opportunity.Profile) || !HCReady() || s_Active || opportunity.Phase != "intent") { return false; }
        HCXAISiteState party = HCFind(opportunity.Lease);
        if (!party || !HCProfileFits(party, opportunity.Profile)) { return false; }
        HCW38SituationBinding binding = new HCW38SituationBinding;
        binding.Id = opportunity.Id;
        binding.Lease = opportunity.Lease;
        binding.Profile = opportunity.Profile;
        binding.Group = party.Patrol.m_Group;
        int memberCount = binding.Group.Count();
        for (int memberIndex = 0; memberIndex < memberCount; memberIndex++)
        {
            eAIBase member = eAIBase.Cast(binding.Group.GetMember(memberIndex));
            if (!member || !member.IsAlive()) { return false; }
            binding.Members.Insert(member);
        }
        binding.Behaviour = binding.Group.GetWaypointBehaviour();
        array<vector> route = binding.Group.GetWaypoints();
        if (!route || route.Count() < 1 || route.Count() > s_Policy.MaxRouteNodes) { return false; }
        foreach (vector point : route) { binding.Original.Insert(point); }
        bool started;
        if (opportunity.Profile == "raid" || opportunity.Profile == "column") { started = HCRaid(party, binding); }
        else { started = HCThreaten(party, binding); }
        if (!started) { return false; }
        HCHold(binding);
        s_Active = binding;
        HCSignals(binding);
        Print("[HC Situations] started profile=" + binding.Profile + " lease=" + binding.Lease + " runtime=PENDING");
        return true;
    }

    static string HCObserve(HCSituationState opportunity)
    {
        if (!opportunity || !s_Active || opportunity.Id != s_Active.Id) { return ""; }
        array<eAIBase> members = s_Active.Members;
        if (!members || members.Count() == 0) { return ""; }
        foreach (eAIBase member : members)
        {
            if (!member || member.IsPendingDeletion() || member.IsAlive()) { return ""; }
        }
        // Only still-present native dead bodies establish death. Group cleanup,
        // route requests, deletion and timers never establish rescue/departure.
        return "dead";
    }

    static void HCEnd(HCSituationState opportunity)
    {
        if (!opportunity || !s_Active || s_Active.Id != opportunity.Id) { return; }
        HCRestore(s_Active);
        // Real infected/loot remain under native lifetime and combat ownership;
        // never delete a visible actor or recreate a spent threat on restart.
        s_Active = null;
    }
}
