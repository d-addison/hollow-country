// Authored DTOs only. No entity pointers, target identities or player positions
// enter persistence. Schema/build/world mismatches quarantine instead of wiping.
// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:380 Count, :407 Insert;
// Config fallback Print: 1_Core/proto/EnDebug.c:96.
// the new retirement fields belong only to our JSON DTO, never vanilla storage.
class HCInfectedConfig
{
    int SchemaVersion = 1;
    bool EnableCEAdoption = true;
    bool EnableContactGuard = true;
    bool EnableNativePackRoutes = true;
    bool EnableInvestigation = true;
    bool EnableSupplementaryChains = true;
    bool EnableMemberRecovery = true;
    bool EnableVariantPolicies = true;
    bool EnableHordeStimulusRoutes = true;
    // Enabled preference; empty maps are an unqualified template, not a roster.
    // Explicit stance maps are required before variant policy selection.
    ref array<int> CivilianVariants = new array<int>;
    ref array<int> MilitaryVariants = new array<int>;
    bool RunPolicySelfTests = false;
    int MaxTracked = 24;
    int MaxVoiceQueue = 16;
    int MaxVoicePerTick = 8;
    int VoiceCooldownSeconds = 10;
    int SaveIntervalSeconds = 60;
    int MaxInvestigators = 2;

    int HordeCooldownSeconds = 180;
    ref HCC1Doors Doors = new HCC1Doors;
    ref HCC1Reach Reach = new HCC1Reach;
    ref HCC1Vision Vision = new HCC1Vision;
    ref HCC1Memory Memory = new HCC1Memory;
    ref HCC1Chain Chain = new HCC1Chain;
    ref HCC1Navigation Navigation = new HCC1Navigation;
    ref HCC1LOD LevelOfDetail = new HCC1LOD;

    protected static bool s_HCTuningInvalidLogged;
    void HCNormalizeTunables()
    {
        HCC1Range.s_Invalid = false;
        HordeCooldownSeconds = HCC1Range.Value(HordeCooldownSeconds, 1, 86400, 180);
        if (!Doors) { Doors = new HCC1Doors; }
        Doors.Normalize();
        if (!Reach) { Reach = new HCC1Reach; }
        Reach.Normalize();
        if (!Vision) { Vision = new HCC1Vision; }
        Vision.Normalize();
        if (!Memory) { Memory = new HCC1Memory; }
        Memory.Normalize();
        if (!Chain) { Chain = new HCC1Chain; }
        Chain.Normalize();
        if (!Navigation) { Navigation = new HCC1Navigation; }
        Navigation.Normalize();
        if (!LevelOfDetail) { LevelOfDetail = new HCC1LOD; }
        LevelOfDetail.Normalize();
        if (Memory.CohortBase + Memory.CohortHeat > 6) { Memory.CohortBase = 3; Memory.CohortHeat = 3; HCC1Range.s_Invalid = true; }
        if (Memory.ResponseBase + Memory.ResponseHeat > 12) { Memory.ResponseBase = 6; Memory.ResponseHeat = 6; HCC1Range.s_Invalid = true; }
        if (HCC1Range.s_Invalid && !s_HCTuningInvalidLogged)
        {
            s_HCTuningInvalidLogged = true;
            Print("[HC Infected] tunables=invalid_fields_defaulted first=" + HCC1Range.s_Detail + " runtime=PENDING");
        }
        HCInfectedTuning.Set(this);
    }

    bool IsValid()
    {
        HCNormalizeTunables();
        if (!HCInfectedProfiles.ValidateMap(CivilianVariants, false))
            return false;
        if (!HCInfectedProfiles.ValidateMap(MilitaryVariants, false))
            return false;
        if (!(SchemaVersion == 1 && MaxTracked >= 1 && MaxTracked <= 24))
            return false;
        if (!(MaxVoiceQueue >= 1 && MaxVoiceQueue <= 32 && MaxVoicePerTick >= 1 && MaxVoicePerTick <= 8))
            return false;
        if (!(VoiceCooldownSeconds >= 10 && VoiceCooldownSeconds <= 60))
            return false;
        return SaveIntervalSeconds >= 30 && SaveIntervalSeconds <= 300 && MaxInvestigators >= 1 && MaxInvestigators <= 2;
    }
}

// Server-only static qualification, one per complex path. Each *Qualified() is
// false until accepted native runtime evidence (DayZDiag plus normal PBO/server
// test) is recorded for that exact path; flipping one is a source change, never
// an operator setting, persisted value or client input. Pattern follows
// HCInfectedProfiles.ContactGuardQualified().
// Local acceptance only: a server operator may create the matching marker file
// under $profile:HollowCountry/acceptance/ (named at each *OptIn() below) so the
// owner's local server run can exercise that one path. Each *Admitted() is
// Qualified OR marker, server-only, probes the marker once per process, caches
// the answer and logs one EXPERIMENTAL line only when the marker opens the path.
// A path whose marker is absent behaves, and logs, exactly as before. Markers are
// independent and are never auto-opened: horde_routes steers native packs, so it
// is only meaningful with pack_routes (HCInfectedAdmission.Resolve already keeps
// it closed with reason horde_stimulus_routes_requires_pack_routes otherwise);
// ecology migration (on unless ecology_migration.disable) additionally needs pack_routes,
// horde_routes and, for its clue sources, investigation or supplementary_chains.
class HCInfectedQualification
{
    protected static bool s_CEAdoptionChecked;
    protected static bool s_CEAdoptionOptIn;

    protected static bool s_NativePackRoutesChecked;
    protected static bool s_NativePackRoutesOptIn;

    protected static bool s_InvestigationChecked;
    protected static bool s_InvestigationOptIn;

    protected static bool s_SupplementaryChainsChecked;
    protected static bool s_SupplementaryChainsOptIn;

    protected static bool s_MemberRecoveryChecked;
    protected static bool s_MemberRecoveryOptIn;

    protected static bool s_HordeStimulusRoutesChecked;
    protected static bool s_HordeStimulusRoutesOptIn;

    // Evidence required: accepted native CE-membership transfer, restart and ownership run.
    static bool CEAdoptionQualified()
    {
        return false;
    }

    static bool CEAdoptionOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_ce_adoption.disable");
    }

    static bool CEAdoptionAdmitted()
    {
        if (CEAdoptionQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_CEAdoptionChecked)
        {
            s_CEAdoptionChecked = true;
            s_CEAdoptionOptIn = CEAdoptionOptIn();
            if (s_CEAdoptionOptIn)
                Print("[HollowCountry] V1 admission feature=CEAdoption preference=on gate=infected_ce_adoption qualified=0 result=admitted unverified: infected_ce_adoption has no recorded native verdict; opt out with acceptance/infected_ce_adoption.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_CEAdoptionOptIn;
    }

    // Evidence required: accepted native pack path, ownership and release run.
    static bool NativePackRoutesQualified()
    {
        return false;
    }

    static bool NativePackRoutesOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_pack_routes.disable");
    }

    static bool NativePackRoutesAdmitted()
    {
        if (NativePackRoutesQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_NativePackRoutesChecked)
        {
            s_NativePackRoutesChecked = true;
            s_NativePackRoutesOptIn = NativePackRoutesOptIn();
            if (s_NativePackRoutesOptIn)
                Print("[HollowCountry] V1 admission feature=NativePackRoutes preference=on gate=infected_pack_routes qualified=0 result=admitted unverified: infected_pack_routes has no recorded native verdict; opt out with acceptance/infected_pack_routes.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_NativePackRoutesOptIn;
    }

    // Evidence required: accepted native frozen-observation search path and perception run.
    static bool InvestigationQualified()
    {
        return false;
    }

    static bool InvestigationOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_investigation.disable");
    }

    static bool InvestigationAdmitted()
    {
        if (InvestigationQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_InvestigationChecked)
        {
            s_InvestigationChecked = true;
            s_InvestigationOptIn = InvestigationOptIn();
            if (s_InvestigationOptIn)
                Print("[HollowCountry] V1 admission feature=Investigation preference=on gate=infected_investigation qualified=0 result=admitted unverified: infected_investigation has no recorded native verdict; opt out with acceptance/infected_investigation.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_InvestigationOptIn;
    }

    // Evidence required: accepted two-client hearing and relay audibility run.
    static bool SupplementaryChainsQualified()
    {
        return false;
    }

    static bool SupplementaryChainsOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_supplementary_chains.disable");
    }

    static bool SupplementaryChainsAdmitted()
    {
        if (SupplementaryChainsQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_SupplementaryChainsChecked)
        {
            s_SupplementaryChainsChecked = true;
            s_SupplementaryChainsOptIn = SupplementaryChainsOptIn();
            if (s_SupplementaryChainsOptIn)
                Print("[HollowCountry] V1 admission feature=SupplementaryChains preference=on gate=infected_supplementary_chains qualified=0 result=admitted unverified: infected_supplementary_chains has no recorded native verdict; opt out with acceptance/infected_supplementary_chains.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_SupplementaryChainsOptIn;
    }

    // Evidence required: accepted native identity, death/corpse and restart reconciliation run.
    static bool MemberRecoveryQualified()
    {
        return false;
    }

    static bool MemberRecoveryOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_member_recovery.disable");
    }

    static bool MemberRecoveryAdmitted()
    {
        if (MemberRecoveryQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_MemberRecoveryChecked)
        {
            s_MemberRecoveryChecked = true;
            s_MemberRecoveryOptIn = MemberRecoveryOptIn();
            if (s_MemberRecoveryOptIn)
                Print("[HollowCountry] V1 admission feature=MemberRecovery preference=on gate=infected_member_recovery qualified=0 result=admitted unverified: infected_member_recovery has no recorded native verdict; opt out with acceptance/infected_member_recovery.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_MemberRecoveryOptIn;
    }

    // Evidence required: accepted native cohort retarget path and stall/cooldown run.
    static bool HordeStimulusRoutesQualified()
    {
        return false;
    }

    static bool HordeStimulusRoutesOptIn()
    {
        return !FileExist("$profile:HollowCountry/acceptance/infected_horde_routes.disable");
    }

    static bool HordeStimulusRoutesAdmitted()
    {
        if (HordeStimulusRoutesQualified())
            return true;
        if (!GetGame() || !GetGame().IsServer())
            return false;
        if (!s_HordeStimulusRoutesChecked)
        {
            s_HordeStimulusRoutesChecked = true;
            s_HordeStimulusRoutesOptIn = HordeStimulusRoutesOptIn();
            if (s_HordeStimulusRoutesOptIn)
                Print("[HollowCountry] V1 admission feature=HordeStimulusRoutes preference=on gate=infected_horde_routes qualified=0 result=admitted unverified: infected_horde_routes has no recorded native verdict; opt out with acceptance/infected_horde_routes.disable; EXPERIMENTAL; runtime acceptance PENDING");
        }
        return s_HordeStimulusRoutesOptIn;
    }
}

// Per-path capability admission = operator preference AND explicit qualification.
// Every field defaults closed. Unknown qualification fails closed for that path
// only; native behavior is retained. Operator preferences are never rewritten.
class HCInfectedAdmission
{
    bool CEAdoption;
    bool NativePackRoutes;
    bool Investigation;
    bool SupplementaryChains;
    bool MemberRecovery;
    bool HordeStimulusRoutes;
    string CEAdoptionReason = "ce_adoption_unqualified";
    string NativePackRoutesReason = "native_pack_routes_unqualified";
    string InvestigationReason = "investigation_unqualified";
    string SupplementaryChainsReason = "supplementary_chains_unqualified";
    string MemberRecoveryReason = "member_recovery_unqualified";
    string HordeStimulusRoutesReason = "horde_stimulus_routes_unqualified";

    static string DisabledReason()
    {
        return "disabled_by_preference";
    }

    static bool Admitted(bool requested, bool qualified)
    {
        return requested && qualified;
    }

    static string Reason(bool requested, bool qualified, string unqualified)
    {
        if (!requested)
            return DisabledReason();
        if (!qualified)
            return unqualified;
        return "admitted";
    }

    static string Flag(bool value)
    {
        if (value)
            return "1";
        return "0";
    }

    static string Segment(string path, string reason, bool admitted)
    {
        bool requested = reason != DisabledReason();
        return path + " requested=" + Flag(requested) + " admitted=" + Flag(admitted) + " reason=" + reason;
    }

    static HCInfectedAdmission Resolve(HCInfectedConfig config, bool ceQualified, bool routesQualified, bool investigationQualified, bool chainsQualified, bool recoveryQualified, bool stimulusQualified)
    {
        HCInfectedAdmission admission = new HCInfectedAdmission;
        admission.CEAdoption = Admitted(config.EnableCEAdoption, ceQualified);
        admission.CEAdoptionReason = Reason(config.EnableCEAdoption, ceQualified, "ce_adoption_unqualified");
        admission.NativePackRoutes = Admitted(config.EnableNativePackRoutes, routesQualified);
        admission.NativePackRoutesReason = Reason(config.EnableNativePackRoutes, routesQualified, "native_pack_routes_unqualified");
        admission.Investigation = Admitted(config.EnableInvestigation, investigationQualified);
        admission.InvestigationReason = Reason(config.EnableInvestigation, investigationQualified, "investigation_unqualified");
        admission.SupplementaryChains = Admitted(config.EnableSupplementaryChains, chainsQualified);
        admission.SupplementaryChainsReason = Reason(config.EnableSupplementaryChains, chainsQualified, "supplementary_chains_unqualified");
        admission.MemberRecovery = Admitted(config.EnableMemberRecovery, recoveryQualified);
        admission.MemberRecoveryReason = Reason(config.EnableMemberRecovery, recoveryQualified, "member_recovery_unqualified");
        // Cohort stimulus retargets steer native packs; they need admitted pack routes.
        admission.HordeStimulusRoutes = Admitted(config.EnableHordeStimulusRoutes, stimulusQualified) && admission.NativePackRoutes;
        admission.HordeStimulusRoutesReason = Reason(config.EnableHordeStimulusRoutes, stimulusQualified, "horde_stimulus_routes_unqualified");
        if (config.EnableHordeStimulusRoutes && stimulusQualified && !admission.NativePackRoutes)
            admission.HordeStimulusRoutesReason = "horde_stimulus_routes_requires_pack_routes";
        return admission;
    }

    static HCInfectedAdmission Evaluate(HCInfectedConfig config)
    {
        return Resolve(config, HCInfectedQualification.CEAdoptionAdmitted(), HCInfectedQualification.NativePackRoutesAdmitted(), HCInfectedQualification.InvestigationAdmitted(), HCInfectedQualification.SupplementaryChainsAdmitted(), HCInfectedQualification.MemberRecoveryAdmitted(), HCInfectedQualification.HordeStimulusRoutesAdmitted());
    }

    // Bounded one-line report: requested vs admitted vs reason for every path.
    string Describe()
    {
        string text = HCInfectedAdmission.Segment("ce_adoption", CEAdoptionReason, CEAdoption) + "; " + HCInfectedAdmission.Segment("native_pack_routes", NativePackRoutesReason, NativePackRoutes) + "; " + HCInfectedAdmission.Segment("investigation", InvestigationReason, Investigation);
        text = text + "; " + HCInfectedAdmission.Segment("supplementary_chains", SupplementaryChainsReason, SupplementaryChains) + "; " + HCInfectedAdmission.Segment("member_recovery", MemberRecoveryReason, MemberRecovery) + "; " + HCInfectedAdmission.Segment("horde_stimulus_routes", HordeStimulusRoutesReason, HordeStimulusRoutes);
        return text;
    }
}

class HCInfectedClue
{
    vector Origin;
    float Observed;
    float Expires;
    float Strength = 1;
    int Provenance = 1; // 1=locally emitted native voice; 2=direct visual sample.
    int Hops = 0;
    int EventId;

    bool IsLive(float now)
    {
        return HCInfectedPolicy.AcceptClue(now, Observed, Expires, Provenance, Strength, Hops);
    }
}

class HCInfectedActor
{
    ZombieBase InfectedEntity;
    int GroupId = 0;
    bool EverAssigned = false; // A retired member is never adopted again this session.
    bool RecoveredMember = false;
    float NextVoice = 0;
    int LastEventId = -1;
    float LastEventAt = -1;
    ref HCInfectedClue Clue;
    ref HCInfectedClue Visual;
    int SearchAttempts;
    float NextSearch;
    float NextVisualSample;
    ref HCNativeInfectedPack SearchPack;
    ref HCInfectedClue Heard;
    float NextHearing;
    int HeardRootId;
    bool HeardExternally;
    string Profile;
    float ClueLifetime;
    int BaseVariant = -1;
    int RequestedVariant = -1;
    int SearchAnchorLimit;
    bool ConfirmedDead;
    // #135 shared LOD sample written only by the infected LOD cursor
    // (Infected/LOD/HCInfectedLOD.c). Tier -1 and distance -1 mean unknown.
    int LODTier = -1;
    float LODDistance = -1;
    float LODAt = -1;

    void InitializeProfile(HCInfectedConfig config)
    {
        // Called once at registration. Injury never changes base personality.
        if (config.EnableVariantPolicies)
        {
            RequestedVariant = HCInfectedProfiles.ConfiguredVariant(InfectedEntity, config);
            BaseVariant = HCInfectedPolicy.ResolveVariant(RequestedVariant);
        }
        RefreshProfile();
    }

    void RefreshProfile()
    {
        // Recognizable *existing* CE appearance/location distribution is kept.
        // These traits affect logical group attention, not native senses/stats.
        Profile = "civilian_searcher";
        if (InfectedEntity.IsZombieMilitary())
        {
            Profile = "military_reactive";
        }
        bool injured = InfectedEntity.GetHealth("LeftLeg", "Health") <= 0 || InfectedEntity.GetHealth("RightLeg", "Health") <= 0;
        if (injured)
        {
            Profile = "native_injured";
        }
        int stance = InfectedEntity.HCIndividualStance();
        ClueLifetime = HCInfectedPolicy.ProfileLifetime(InfectedEntity.IsZombieMilitary(), injured, stance);
        SearchAnchorLimit = HCInfectedPolicy.SearchAnchorBudget(InfectedEntity.IsZombieMilitary(), injured);
        if (BaseVariant >= 0)
        {
            Profile = HCInfectedProfiles.DescriptorName(BaseVariant);
            ClueLifetime = HCInfectedPolicy.VariantLifetime(BaseVariant, stance, injured);
            SearchAnchorLimit = HCInfectedPolicy.VariantAnchorBudget(BaseVariant, injured);
            if (injured)
                Profile = "native_injured";
        }
    }
}

class HCInfectedVoice
{
    ZombieBase Emitter;
    ref HCInfectedClue Clue;
}

class HCHordeRecord
{
    int Id;
    int State = -1;
    int Reserved = -1;
    int Living = -1;
    // 1=durable prepared reservation; 2=committed; 3=aborted/unresolved.
    int AdoptionStage = -1;
    int CreatedUtc;
    int LastSignalUtc;
    vector Anchor = "999999 999999 999999";
    // Actual member centroid, never a synthetic waypoint or hidden player target.
    vector PreviousAnchor = "999999 999999 999999";
    bool HasRoute = false;
    vector RouteEnd;
    // 1=frozen sensed clue; 2=measured room investigation. No invented migration.
    int RoutePurpose;
    int RouteResult;
    int RoutePlanned;
    int RouteCompleted;
    // Empty on legacy/unproven CE identity; never infer missing identities.
    ref array<ref HCHordeMemberId> MemberIds = new array<ref HCHordeMemberId>;
    // Durable ambiguity latch. It is never silently cleared on restart.
    bool RecoveryConflicted;
    // Optional schema-2 extension: absent legacy fields retain their spent
    // reservation until a real terminal lifecycle refunds it. No store wipe.
    bool BudgetReleased = false;
    int RetiredUtc;
}

class HCInfectedSnapshot
{
    int SchemaVersion = -1;
    string Build;
    string WorldName;
    int Epoch = 0;
    int Generation = 0;
    int SavedUtc = 0;
    int Reserved = -1;
    ref array<ref HCHordeRecord> Groups;
}

class HCInfectedClock
{
    static int UtcSeconds()
    {
        int year, month, day, hour, minute, second;
        GetYearMonthDayUTC(year, month, day);
        GetHourMinuteSecondUTC(hour, minute, second);
        // Signed 32-bit seconds; reject unsupported clock years explicitly.
        if (year < 2026 || year > 2037 || month < 1 || month > 12 || day < 1 || day > 31)
            return -1;
        int days = 0;
        for (int y = 1970; y < year; y++)
        {
            days += 365;
            if (y % 4 == 0)
                days++;
        }
        for (int m = 1; m < month; m++)
        {
            int length = 31;
            if (m == 4 || m == 6 || m == 9 || m == 11)
                length = 30;
            if (m == 2)
            {
                length = 28;
                if (year % 4 == 0)
                    length = 29;
            }
            days += length;
        }
        return (days + day - 1) * 86400 + hour * 3600 + minute * 60 + second;
    }
}

class HCInfectedStore
{
    static const string ROOT = "$profile:HollowCountry";
    static const string DIRECTORY = "$profile:HollowCountry/Infected";

    static bool ReadBounded(string path, out string content)
    {
        FileHandle handle = OpenFile(path, FileMode.READ);
        if (!handle)
            return false;
        // The stock JsonFileLoader reads up to 100MB. This module allows 64KiB.
        ReadFile(handle, content, 65537);
        CloseFile(handle);
        return content.Length() > 0 && content.Length() <= 65536;
    }

    static bool ValidPosition(vector position)
    {
        for (int i = 0; i < 3; i++)
        {
            if (!(position[i] >= -200000 && position[i] <= 200000))
                return false;
        }
        return true;
    }

    static bool Validate(HCInfectedSnapshot snapshot, string world, int memberCap, int groupCap, int now)
    {
        if (!snapshot || !snapshot.Groups || !HCBuildIdentity.Matches(snapshot.Build))
            return false;
        if (!HCInfectedPolicy.ValidSnapshotHeader(snapshot.SchemaVersion, snapshot.WorldName == world, snapshot.Epoch, snapshot.Groups.Count(), snapshot.Reserved, memberCap, snapshot.SavedUtc, now))
            return false;
        if (snapshot.Generation < 1 || snapshot.Generation > 1000000 || snapshot.Groups.Count() > groupCap)
            return false;
        int total = 0;
        for (int i = 0; i < snapshot.Groups.Count(); i++)
        {
            HCHordeRecord group = snapshot.Groups[i];
            if (!group)
                return false;
            if (!HCInfectedPolicy.ValidGroupRecord(group.Id, i, group.Reserved, group.Living, group.State, group.CreatedUtc, group.LastSignalUtc, snapshot.SavedUtc))
                return false;
            if (!HCInfectedPolicy.ValidAdoptionRecord(group.AdoptionStage, group.State, group.RecoveryConflicted))
                return false;
            if (group.BudgetReleased)
            {
                if (group.State != 5 || group.HasRoute || group.RetiredUtc < group.CreatedUtc || group.RetiredUtc > snapshot.SavedUtc)
                {
                    return false;
                }
            }
            else if (group.RetiredUtc != 0)
            {
                return false;
            }
            if (!ValidPosition(group.Anchor) || !ValidPosition(group.PreviousAnchor))
                return false;
            if (!HCHordeRecovery.ValidateRoster(group))
                return false;
            for (int olderGroup = 0; olderGroup < i; olderGroup++)
            {
                foreach (HCHordeMemberId member : group.MemberIds)
                {
                    foreach (HCHordeMemberId previousMember : snapshot.Groups[olderGroup].MemberIds)
                    {
                        if (member.SameId(previousMember))
                            return false;
                    }
                }
            }
            if (!HCInfectedPolicy.ValidRouteMetadata(group.RoutePurpose, group.RouteResult, group.RoutePlanned, group.RouteCompleted, group.HasRoute))
                return false;
            if (group.RoutePlanned > 0 && !ValidPosition(group.RouteEnd))
                return false;
            if (!group.BudgetReleased)
            {
                total += group.Reserved;
            }
        }
        return total == snapshot.Reserved;
    }

    // Native LoadData zero-fills absent int sentinels (-1 reads 0); only ints
    // were observed natively.
    // Check every horde object at Groups[] depth, not just the first key in
    // the document; zero Living remains legitimate when explicitly stored.
    static bool HCFieldsPresent(string text)
    {
        if (!HCJsonFields.Has(text, "SchemaVersion") || !HCJsonFields.Has(text, "Reserved")) { return false; }
        return HCJsonFields.Every(text, "Living", 3) && HCJsonFields.Every(text, "Reserved", 3) && HCJsonFields.Every(text, "AdoptionStage", 3);
    }

    static bool LoadSlot(string path, out HCInfectedSnapshot snapshot, string world, int memberCap, int groupCap, int now)
    {
        string content, error;
        snapshot = new HCInfectedSnapshot;
        if (!ReadBounded(path, content) || !JsonFileLoader<HCInfectedSnapshot>.LoadData(content, snapshot, error))
        {
            return false;
        }
        if (!HCFieldsPresent(content))
        {
            Print("[HC Infected] refused journal reason=missing_horde_sentinel_fields; preserving files; runtime=PENDING");
            return false;
        }
        return Validate(snapshot, world, memberCap, groupCap, now);
    }

    // Validated snapshot exactly as stored. A journal whose lifecycle paths are
    // not admitted stays evidence: no restart interpretation is applied to it.
    static bool LoadVerbatim(out HCInfectedSnapshot snapshot, string world, int memberCap, int groupCap, int now)
    {
        string pathA = DIRECTORY + "/hordes-a.json";
        string pathB = DIRECTORY + "/hordes-b.json";
        bool existsA = FileExist(pathA);
        bool existsB = FileExist(pathB);
        if (!existsA && !existsB)
        {
            snapshot = new HCInfectedSnapshot;
            snapshot.SchemaVersion = 2;
            snapshot.Build = HCBuildIdentity.Canonical();
            snapshot.WorldName = world;
            snapshot.Epoch = 1;
            snapshot.Reserved = 0;
            snapshot.Groups = new array<ref HCHordeRecord>;
            return now > 0;
        }
        HCInfectedSnapshot a, b;
        // Any present corrupt slot quarantines. Never silently roll back a spent
        // reservation by falling back to an older generation.
        if (existsA && !LoadSlot(pathA, a, world, memberCap, groupCap, now))
            return false;
        if (existsB && !LoadSlot(pathB, b, world, memberCap, groupCap, now))
            return false;
        snapshot = a;
        if (!a || (b && b.Generation > a.Generation))
            snapshot = b;
        if (a && b)
        {
            HCInfectedSnapshot older = a;
            if (snapshot == a)
                older = b;
            bool ordinaryPair = HCInfectedPolicy.ValidGenerationPair(snapshot.Generation, older.Generation, snapshot.Epoch, older.Epoch, snapshot.SavedUtc, older.SavedUtc, snapshot.Reserved, older.Reserved, snapshot.Groups.Count(), older.Groups.Count());
            bool refundPair = HCInfectedPolicy.RefundedGenerationPair(snapshot.Generation, older.Generation, snapshot.Epoch, older.Epoch, snapshot.SavedUtc, older.SavedUtc, snapshot.Reserved, older.Reserved, snapshot.Groups.Count(), older.Groups.Count());
            if (!ordinaryPair && !refundPair)
            {
                return false;
            }
            int newlyRefunded = 0;
            for (int i = 0; i < older.Groups.Count(); i++)
            {
                HCHordeRecord previous = older.Groups[i];
                HCHordeRecord current = snapshot.Groups[i];
                // A new intent can replace only a durably refunded terminal
                // record, after cooldown; Id remains the bounded slot number.
                bool reused = previous.CreatedUtc != current.CreatedUtc;
                if (reused)
                {
                    if (!HCInfectedPolicy.MayReuseHorde(previous.State, previous.BudgetReleased, previous.RetiredUtc, current.CreatedUtc))
                    {
                        return false;
                    }
                    if (current.Id != previous.Id || current.AdoptionStage != 1 || current.BudgetReleased || current.CreatedUtc <= older.SavedUtc)
                    {
                        return false;
                    }
                    continue;
                }
                if (previous.BudgetReleased && !current.BudgetReleased)
                {
                    return false;
                }
                if (previous.BudgetReleased && previous.RetiredUtc != current.RetiredUtc)
                {
                    return false;
                }
                if (!previous.BudgetReleased && current.BudgetReleased)
                {
                    newlyRefunded += previous.Reserved;
                }
                if (!HCInfectedPolicy.ValidAdoptionStagePair(previous.AdoptionStage, current.AdoptionStage))
                    return false;
                bool normalAdvance = HCInfectedPolicy.CanAdvanceRecord(previous.Id, current.Id, previous.Reserved, current.Reserved, previous.Living, current.Living, previous.State, current.State, previous.CreatedUtc, current.CreatedUtc);
                bool adoptionCommit = HCInfectedPolicy.CommitAdoptionRecord(previous.Id, current.Id, previous.Reserved, current.Reserved, previous.Living, current.Living, previous.State, current.State, previous.CreatedUtc, current.CreatedUtc, previous.AdoptionStage, current.AdoptionStage);
                if (!normalAdvance && !adoptionCommit)
                    return false;
                if (!HCHordeRecovery.SameRoster(previous, current))
                    return false;
            }
            if (refundPair && older.Reserved - snapshot.Reserved > newlyRefunded)
            {
                return false;
            }
        }
        return true;
    }

    static void ApplyRestart(HCInfectedSnapshot snapshot)
    {
        foreach (HCHordeRecord group : snapshot.Groups)
        {
            // Native CE identity cannot be proved across restart. Preserve each
            // reservation; never infer membership from classname or proximity.
            group.AdoptionStage = HCInfectedPolicy.AdoptionAfterRestart(group.AdoptionStage);
            if (group.AdoptionStage == 3)
                group.RecoveryConflicted = true;
            group.State = HCInfectedPolicy.AfterRestart(group.State);
            if (group.HasRoute)
                group.RouteResult = 5; // Restart interrupts native intent, never replays it.
            group.HasRoute = false; // RouteEnd remains historical, never active intent.
        }
    }

    static bool Load(out HCInfectedSnapshot snapshot, string world, int memberCap, int groupCap, int now)
    {
        if (!LoadVerbatim(snapshot, world, memberCap, groupCap, now))
            return false;
        ApplyRestart(snapshot);
        return true;
    }

    static bool Save(HCInfectedSnapshot snapshot, int memberCap, int groupCap)
    {
        snapshot.Generation++;
        snapshot.SavedUtc = HCInfectedClock.UtcSeconds();
        if (!Validate(snapshot, snapshot.WorldName, memberCap, groupCap, snapshot.SavedUtc))
            return false;
        string content, error;
        if (!JsonFileLoader<HCInfectedSnapshot>.MakeData(snapshot, content, error) || content.Length() > 65536)
            return false;
        string path = DIRECTORY + "/hordes-a.json";
        if (snapshot.Generation % 2 == 0)
            path = DIRECTORY + "/hordes-b.json";
        FileHandle handle = OpenFile(path, FileMode.WRITE);
        if (!handle)
            return false;
        FPrint(handle, content);
        CloseFile(handle);
        string readback;
        return ReadBounded(path, readback) && readback == content;
    }
}
