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
// #210 native additions: 3_Game/Entities/EntityAI.c:882
// GetHierarchyRootPlayer, :885 GetHierarchyParent; Entities/Man.c:21
// GetIdentity, :147 ServerDropEntity; Object.c:467 GetType.
// Expansion xref/ai/4_World/DayZExpansion_AI/Entities/DayZPlayerImplement.c:234
// GetGroup. No driving controller is exposed by the inspected vehicle FSM:
// Classes/FSM/States/eAIState_Vehicles.c:35 rejects the formation leader;
// :46-58 considers passenger seats only. Entities/AI/eAIBase.c:4404
// Notify_Transport only queues entry (:7419-7425), not steering/throttle.
// No actor teleport, new AI owner, target assignment, door change or loot mint.
class HCW38SituationBinding
{
    string Id;
    string Lease;
    string Profile;
    // eAIGroup is not Managed: the group is reached only through Hold, from HCBegin until HCEnd.
    ref HCXAIGroupHold Hold;
    eAIWaypointBehavior Behaviour;
    ItemBase SmokeStock;
    ref HCXAIAgentHold SmokeOwner;
    ref HCW38SituationSmokeStock SmokeScan;
    int SmokeMember;
    int SmokeAttempts;
    bool SmokeDropped;
    bool SmokeDone;
    bool FactPublished;
    ref array<vector> Original = new array<vector>;
    ref array<ref HCXAIAgentHold> Members = new array<ref HCXAIAgentHold>;
    ref array<ZombieBase> Threats = new array<ZombieBase>;
    void ~HCW38SituationBinding() { HCXAIGroupHolds.Retire(Hold); }
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
    // Operator opt-out markers are probed once per process (restart to change one).
    protected static bool s_OffProbed;
    protected static bool s_SituationsOff;
    protected static bool s_ProfilesProbed;
    protected static bool s_RaidsOff;
    protected static bool s_TransitOff;
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
        if (!s_OffProbed)
        {
            s_OffProbed = true;
            s_SituationsOff = FileExist("$profile:HollowCountry/acceptance/w38_situations.disable");
        }
        if (s_SituationsOff) { return HCRefuse("SITUATION_OPERATOR_OFF"); }
        if (!s_Logged)
        {
            s_Logged = true;
            Print(HCV2Admission.Line("Situations", true, "w38_situations", false) + " runtime=PENDING");
        }
        HCXAISiteDirector director = HCXAISiteDirector.Active();
        if (!HCPolicy()) { return false; }
        if (!director || director.Phase() != "run") { return HCRefuse("SITUATION_SITE_DIRECTOR_PENDING"); }
        // HCWorldMaterializer.InterestRing creates leased parties only near
        // living observers. Do not consume one-shot story rows on an empty server.
        // Installed Object.c:517 IsAlive; EnScript.c:380 Count (cached players).
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() == 0) { return HCRefuse("SITUATION_NEEDS_PLAYER"); }
        if (players.Count() > HCSituationLimits.PACING_PLAYERS) { return HCRefuse("SITUATION_PLAYER_CAP"); }
        bool living;
        for (int playerIndex = 0; playerIndex < 16 && playerIndex < players.Count(); playerIndex++)
        {
            Man observer = players[playerIndex];
            if (observer && observer.IsAlive()) { living = true; break; }
        }
        if (!living) { return HCRefuse("SITUATION_NEEDS_PLAYER"); }
        if (s_Refusal == "SITUATION_SITE_DIRECTOR_PENDING" || s_Refusal == "SITUATION_NEEDS_PLAYER" || s_Refusal == "SITUATION_PLAYER_CAP") { s_Refusal = ""; }
        return true;
    }

    static string HCReason()
    {
        if (s_Refusal == "") { return "observed_actor_port_ready"; }
        return s_Refusal;
    }

    static bool HCCandidate(HCXAISiteState candidate)
    {
        if (!candidate || !candidate.Transient || !candidate.Materialized || !candidate.Qualified || candidate.Completed) { return false; }
        if (!HCWorldMaterializer.HCIdentity(candidate.ProposalId) || !candidate.Patrol || !HCXExpansionBridge.HCHoldAlive(candidate.Patrol.HCGroupHold())) { return false; }
        return HCXExpansionBridge.HCHoldCount(candidate.Patrol.HCGroupHold()) > 0 && candidate.Patrol.m_HCPendingMembers == 0;
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
        if (!candidate || !candidate.Patrol) { return false; }
        eAIGroup group = HCXExpansionBridge.HCHoldResolve(candidate.Patrol.HCGroupHold());
        // A dead handle or a bridge that is not READY resolves to null: the profile does not fit.
        if (!group) { return false; }
        if (HCXExpansionBridge.HCGroupCount(group) > s_Policy.MaxMembers || HCXExpansionBridge.HCGroupIsInCombat(group)) { return false; }
        if (candidate.PatrolPoints.Count() < 2 || candidate.PatrolPoints.Count() > s_Policy.MaxRouteNodes) { return false; }
        if (profile == "raid" || profile == "column") { return candidate.ProviderFaction == "HCRaiders"; }
        if (candidate.ProviderFaction == "HCRaiders") { return false; }
        eAIBase leader = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, 0));
        if (!leader || !HCXExpansionBridge.HCBaseIsAlive(leader)) { return false; }
        if (profile == "survivor") { return MiscGameplayFunctions.IsUnderRoof(leader) || HCWreckNear(HCXExpansionBridge.HCBaseGetPosition(leader)); }
        string surface;
        vector at = HCXExpansionBridge.HCBaseGetPosition(leader);
        GetGame().SurfaceGetType(at[0], at[2], surface);
        return surface == s_Policy.RoadSurface;
    }

    static bool HCProfileOn(string profile)
    {
        if (!s_ProfilesProbed)
        {
            s_ProfilesProbed = true;
            s_RaidsOff = FileExist("$profile:HollowCountry/acceptance/w38_raids.disable");
            s_TransitOff = FileExist("$profile:HollowCountry/acceptance/w38_transit.disable");
        }
        if ((profile == "raid" || profile == "column") && s_RaidsOff) { return false; }
        if ((profile == "roadside-position" || profile == "threatened-exodus") && s_TransitOff) { return false; }
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
        if (!states || states.Count() == 0) { HCRefuse("SITUATION_LIVE_PARTY_CATALOG_EMPTY"); return ""; }
        for (int visited = 0; visited < s_Policy.ScanRows && visited < states.Count(); visited++)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { return ""; }
            s_Cursor = s_Cursor % states.Count();
            HCXAISiteState candidate = states[s_Cursor];
            s_Cursor++;
            if (!HCCandidate(candidate) || HCUsed(candidate.ProposalId)) { continue; }
            if (!HCProfileFits(candidate, opportunity.Profile)) { continue; }
            if ((opportunity.Profile == "raid" || opportunity.Profile == "column") && !HCTarget(candidate)) { continue; }
            s_SelectedIndex = s_Cursor - 1;
            s_Refusal = "";
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
        if (!binding || !binding.Hold) { return; }
        HCXExpansionBridge.HCHoldClearWaypoints(binding.Hold);
        array<vector> original = binding.Original;
        foreach (vector point : original) { HCXExpansionBridge.HCHoldAddWaypoint(binding.Hold, point); }
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(binding.Hold, binding.Behaviour);
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
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { return null; }
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
        HCXExpansionBridge.HCHoldClearWaypoints(binding.Hold);
        HCXExpansionBridge.HCHoldAddWaypoint(binding.Hold, party.PatrolPoints[0]);
        HCXExpansionBridge.HCHoldAddWaypoint(binding.Hold, target.PatrolPoints[0]);
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(binding.Hold, eAIWaypointBehavior.HALT);
        return true;
    }

    // A one-point HALT is a native movement request; combat stays entirely
    // perception-owned. Restore the saved route on release, never SetPosition.
    static void HCHold(HCW38SituationBinding binding)
    {
        if (binding.Profile != "survivor") { return; }
        eAIBase sheltered = eAIBase.Cast(HCXExpansionBridge.HCHoldGetMember(binding.Hold, 0));
        if (!sheltered) { return; }
        HCXExpansionBridge.HCHoldClearWaypoints(binding.Hold);
        HCXExpansionBridge.HCHoldAddWaypoint(binding.Hold, HCXExpansionBridge.HCBaseGetPosition(sheltered));
        HCXExpansionBridge.HCHoldSetWaypointBehaviour(binding.Hold, eAIWaypointBehavior.HALT);
    }

    // Existing ShelterMeters is validated against the shared registry BEFORE
    // native allocation. Game.c:930 exposes a radius, no result-count argument.
    // PhysicalScanObjects/Cargo additionally cap post-query inspection; they
    // cannot cap native density/allocation inside the bounded sphere.
    static bool HCWreckNear(vector position)
    {
        float radius = s_Policy.ShelterMeters;
        if (radius != radius || !HCOperatorSettingsRegistry.HCValid("W38Situations.ShelterMeters", radius)) { return HCRefuse("SITUATION_SCAN_RADIUS_REFUSED"); }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { return false; }
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(position, radius, nearby, proxies);
        if (nearby.Count() > s_Policy.PhysicalScanObjects || proxies.Count() > s_Policy.PhysicalScanCargo) { return HCRefuse("SITUATION_WRECK_SCAN_CAP"); }
        foreach (Object shelter : nearby)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { return false; }
            // Reuse the reviewed vanilla wreck catalog; no vehicle creation,
            // salvage debit, extra supplies, movement or door changes.
            if (shelter && HCWreckSalvage.Reviewed(shelter.GetType())) { return true; }
        }
        return false;
    }

    static ItemBase HCLeaseSmoke(HCW38SituationBinding binding)
    {
        if (binding.SmokeStock) { return binding.SmokeStock; }
        // One retained member cursor per attempt. PhysicalScanObjects bounds
        // the entire inventory traversal, and the shared budget bounds each tick.
        if (binding.SmokeMember >= binding.Members.Count()) { return null; }
        eAIBase holder = HCXExpansionBridge.HCAgent(binding.Members[binding.SmokeMember]);
        if (!holder || !HCXExpansionBridge.HCBaseIsAlive(holder) || HCXExpansionBridge.HCBaseGetIdentity(holder) || !HCXExpansionBridge.HCHoldSame(binding.Hold, HCXExpansionBridge.HCDayZPlayerImplementGetGroup(holder)))
        {
            binding.SmokeMember++;
            binding.SmokeScan = null;
            return null;
        }
        if (!binding.SmokeScan)
        {
            binding.SmokeScan = new HCW38SituationSmokeStock;
            binding.SmokeScan.HCStart(holder, "");
        }
        ItemBase stock = binding.SmokeScan.HCStep(s_Policy.PhysicalScanObjects);
        if (stock)
        {
            binding.SmokeOwner = HCXExpansionBridge.HCAgentHold(holder);
            binding.SmokeStock = stock;
            binding.SmokeScan = null;
        }
        else if (binding.SmokeScan.Complete)
        {
            binding.SmokeMember++;
            binding.SmokeScan = null;
        }
        return stock;
    }

    static void HCSmokeFailed(HCW38SituationBinding binding, string reason)
    {
        // ScanRows also bounds retries after the initial signal attempt. A
        // refused budget preserves the same binding/item until this finite cap.
        if (binding.SmokeAttempts <= s_Policy.ScanRows) { return; }
        binding.SmokeDone = true;
        binding.SmokeScan = null;
        HCRefuse("SITUATION_SMOKE_RETRY_EXHAUSTED_" + reason);
    }

    static void HCSignals(HCW38SituationBinding binding)
    {
        if (!binding || binding.SmokeDone) { return; }
        // HCReady probes the marker before any binding exists; an unprobed marker reads as absent.
        if (s_SituationsOff || !HCProfileOn(binding.Profile)) { return; }
        if (!HCWorldMaterializer.HCIdentity(binding.Lease)) { return; }
        // Expansion removes killed members and GetMember indexes directly
        // (eAIGroup.c:1139): a wiped or destroyed group leaves smoke to body observation.
        if (!binding.Hold || HCXExpansionBridge.HCHoldCount(binding.Hold) == 0) { return; }
        binding.SmokeAttempts++;
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 1)) { HCSmokeFailed(binding, "BUDGET"); return; }
        eAIBase witness = eAIBase.Cast(HCXExpansionBridge.HCHoldGetMember(binding.Hold, 0));
        if (!witness || !HCXExpansionBridge.HCBaseIsAlive(witness)) { HCSmokeFailed(binding, "WITNESS"); return; }
        if (!binding.FactPublished)
        {
            binding.FactPublished = HCSituationSignals.HCPublish(HCXExpansionBridge.HCBaseGetPosition(witness));
            if (!binding.FactPublished && !s_FactPending)
            {
                s_FactPending = true;
                Print("[HC Situations] SITUATION_FACT_PLACE_PENDING discovery=native_perception runtime=PENDING");
            }
        }
        HCXAISiteDirector signalDirector = HCXAISiteDirector.Active();
        if (!signalDirector || signalDirector.MemberProblemFor(HCXExpansionBridge.HCBaseGetPosition(witness)) != "") { HCSmokeFailed(binding, "VISIBILITY"); return; }
        ItemBase signalStock = HCLeaseSmoke(binding);
        if (!signalStock)
        {
            if (!s_SmokePending)
            {
                s_SmokePending = true;
                Print("[HC Situations] SITUATION_SMOKE_STOCK_PENDING discovery=gunfire_and_shared_facts runtime=PENDING");
            }
            HCSmokeFailed(binding, "STOCK");
            return;
        }
        if (signalStock.IsPendingDeletion()) { HCSmokeFailed(binding, "STOCK_LOST"); return; }
        if (!binding.SmokeDropped)
        {
            // Ownership is captured while it is still in the leased actor's
            // inventory. Never adopt an item from the world or another owner.
            eAIBase smokeOwner = HCXExpansionBridge.HCAgent(binding.SmokeOwner);
            if (!smokeOwner || signalStock.GetHierarchyRootPlayer() != smokeOwner) { HCSmokeFailed(binding, "OWNERSHIP"); return; }
            if (signalDirector.MemberProblemFor(HCXExpansionBridge.HCBaseGetPosition(smokeOwner)) != "") { HCSmokeFailed(binding, "VISIBILITY"); return; }
            if (!HCXExpansionBridge.HCBaseServerDropEntity(smokeOwner, signalStock)) { HCSmokeFailed(binding, "DROP"); return; }
            binding.SmokeDropped = true;
        }
        if (signalStock.GetHierarchyRootPlayer() || signalStock.GetHierarchyParent()) { HCSmokeFailed(binding, "OWNERSHIP"); return; }
        if (vector.DistanceSq(signalStock.GetPosition(), HCXExpansionBridge.HCBaseGetPosition(witness)) > s_Policy.ShelterMeters * s_Policy.ShelterMeters) { HCSmokeFailed(binding, "DISTANCE"); return; }
        if (signalDirector.MemberProblemFor(signalStock.GetPosition()) != "") { HCSmokeFailed(binding, "VISIBILITY"); return; }
        if (!HCSituationSignals.HCSmoke(signalStock)) { HCSmokeFailed(binding, "NATIVE_STOCK"); return; }
        binding.SmokeDone = true;
        Print("[HC Situations] SITUATION_SMOKE_ACTIVATED lease=" + binding.Lease + " runtime=PENDING");
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
        eAIBase leader = eAIBase.Cast(HCXExpansionBridge.HCHoldGetMember(binding.Hold, 0));
        if (!leader) { return false; }
        int inspected = 0;
        string threatSurface;
        foreach (vector position : points)
        {
            if (inspected >= s_Policy.MaxRouteNodes || s_Threats.Count() >= s_Policy.MaxThreats) { break; }
            inspected++;
            if (vector.DistanceSq(position, HCXExpansionBridge.HCBaseGetPosition(leader)) > s_Policy.ShelterMeters * s_Policy.ShelterMeters) { continue; }
            if (binding.Profile == "roadside-position" || binding.Profile == "threatened-exodus")
            {
                GetGame().SurfaceGetType(position[0], position[2], threatSurface);
                if (threatSurface != s_Policy.RoadSurface) { continue; }
            }
            if (director.MemberProblemFor(position) != "") { continue; }
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_SITUATION_RUNTIME, 8)) { break; }
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
        binding.Hold = HCXExpansionBridge.HCHoldFollowHold(null, party.Patrol.HCGroupHold());
        if (!binding.Hold) { return false; }
        int memberCount = HCXExpansionBridge.HCHoldCount(binding.Hold);
        for (int memberIndex = 0; memberIndex < memberCount; memberIndex++)
        {
            eAIBase member = eAIBase.Cast(HCXExpansionBridge.HCHoldGetMember(binding.Hold, memberIndex));
            if (!member || !HCXExpansionBridge.HCBaseIsAlive(member)) { return false; }
            binding.Members.Insert(HCXExpansionBridge.HCAgentHold(member));
        }
        binding.Behaviour = HCXExpansionBridge.HCHoldGetWaypointBehaviour(binding.Hold);
        array<vector> route = HCXExpansionBridge.HCHoldGetWaypoints(binding.Hold);
        if (!route || route.Count() < 1 || route.Count() > s_Policy.MaxRouteNodes) { return false; }
        foreach (vector point : route) { binding.Original.Insert(point); }
        bool started;
        if (opportunity.Profile == "raid" || opportunity.Profile == "column") { started = HCRaid(party, binding); }
        else { started = HCThreaten(party, binding); }
        if (!started) { return false; }
        HCHold(binding);
        s_Active = binding;
        HCXConvoyRuntime.HCOffer(binding);
        HCSignals(binding);
        Print("[HC Situations] started profile=" + binding.Profile + " lease=" + binding.Lease + " runtime=PENDING");
        return true;
    }

    static string HCObserve(HCSituationState opportunity)
    {
        if (!opportunity || !s_Active || opportunity.Id != s_Active.Id) { return ""; }
        HCSignals(s_Active);
        array<ref HCXAIAgentHold> members = s_Active.Members;
        if (!members || members.Count() == 0) { return ""; }
        foreach (HCXAIAgentHold memberHold : members)
        {
            eAIBase member = HCXExpansionBridge.HCAgent(memberHold);
            if (!member || HCXExpansionBridge.HCBaseIsPendingDeletion(member) || HCXExpansionBridge.HCBaseIsAlive(member)) { return ""; }
        }
        // Only still-present native dead bodies establish death. Group cleanup,
        // route requests, deletion and timers never establish rescue/departure.
        return "dead";
    }

    static void HCEnd(HCSituationState opportunity)
    {
        if (!opportunity || !s_Active || s_Active.Id != opportunity.Id) { return; }
        HCXConvoyRuntime.HCRelease(s_Active.Id);
        HCRestore(s_Active);
        HCXAIGroupHolds.Retire(s_Active.Hold);
        s_Active.Hold = null;
        // Real infected/loot remain under native lifetime and combat ownership;
        // never delete a visible actor or recreate a spent threat on restart.
        s_Active = null;
    }
}
