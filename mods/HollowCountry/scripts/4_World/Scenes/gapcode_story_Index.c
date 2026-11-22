// HC-42. Authored JSON-lines paging, not a procedural scenery provider.
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist,
// :417 OpenFile, :425 ReadFile, :443 CloseFile; EnString.c:113 Substring,
// :199 Length, :271 IndexOfFrom, :319 TrimInPlace; EnScript.c:380 Count,
// :407 array.Insert, :877 map.Find, :917 map.Contains, :926 map.Insert;
// EnDebug.c:96 Print; EnConvert.c:30 ToString.
// 3_Game/tools/JsonFileLoader.c:69 LoadData. No Expansion calls.
// Native qualification remains PENDING: source review admits only an attempt
// through the unchanged native observer/ground/door/footprint preflight.
class HCGapcodeStoryRegistry : HCOperatorSettingsRegistry
{
    static void HCRegisterStoryIndex()
    {
        HCInit();
        if (HCFind("StoryIndex.ReadLinesPerTick")) { return; }
        HCAdd("StoryIndex.ReadLinesPerTick", "int", 16, 1, 32, "HCGapcodeStoryLimits");
        HCAdd("StoryIndex.MaxSites", "int", 1024, 1, 1024, "HCGapcodeStoryLimits");
        HCAdd("StoryIndex.MaxCandidates", "int", 2048, 1, 2048, "HCGapcodeStoryLimits");
        HCAdd("StoryIndex.MaxLineBytes", "int", 8192, 1024, 8192, "HCGapcodeStoryLimits");
        HCAdd("StoryIndex.MaxFileBytes", "int", 2097152, 8192, 2097152, "HCGapcodeStoryLimits");
    }
}

class HCGapcodeStoryLimits
{
    int ReadLinesPerTick = 16;
    int MaxSites = 1024;
    int MaxCandidates = 2048;
    int MaxLineBytes = 8192;
    int MaxFileBytes = 2097152;

    static HCGapcodeStoryLimits HCLoad()
    {
        HCGapcodeStoryRegistry.HCRegisterStoryIndex();
        HCGapcodeStoryLimits limits = new HCGapcodeStoryLimits;
        string path = "$profile:HollowCountry/story-index.json";
        if (!FileExist(path)) { return limits; }
        string image;
        string error;
        HCGapcodeStoryLimits decoded;
        if (!HCGroupIO.Read(path, 4096, image) || !JsonFileLoader<HCGapcodeStoryLimits>.LoadData(image, decoded, error) || !decoded) { return null; }
        // Missing fields retain defaults; explicit bad values refuse the input.
        if (HCJsonFields.Has(image, "ReadLinesPerTick")) { limits.ReadLinesPerTick = decoded.ReadLinesPerTick; }
        if (HCJsonFields.Has(image, "MaxSites")) { limits.MaxSites = decoded.MaxSites; }
        if (HCJsonFields.Has(image, "MaxCandidates")) { limits.MaxCandidates = decoded.MaxCandidates; }
        if (HCJsonFields.Has(image, "MaxLineBytes")) { limits.MaxLineBytes = decoded.MaxLineBytes; }
        if (HCJsonFields.Has(image, "MaxFileBytes")) { limits.MaxFileBytes = decoded.MaxFileBytes; }
        if (!HCOperatorSettingsRegistry.HCValid("StoryIndex.ReadLinesPerTick", limits.ReadLinesPerTick)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("StoryIndex.MaxSites", limits.MaxSites)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("StoryIndex.MaxCandidates", limits.MaxCandidates)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("StoryIndex.MaxLineBytes", limits.MaxLineBytes)) { return null; }
        if (!HCOperatorSettingsRegistry.HCValid("StoryIndex.MaxFileBytes", limits.MaxFileBytes)) { return null; }
        return limits;
    }
}

class HCGapcodeStoryHeader
{
    int SchemaVersion;
    string WorldName;
    string Package;
}

class HCGapcodeStorySite
{
    string Id;
    string LocalityId;
    string AnchorSource;
    string SourceRef;
    vector Anchor;
    bool SourceReviewed;
}

class HCGapcodeStoryCandidate
{
    string Id;
    string Kit;
    string SiteId;
    string Variant;
    bool Qualified;
    string NativeReceipt;
}

class HCStartupStoryIndex : HCStartupOwner
{
    HCGapcodeStoryIndex Index;
    override bool HCNeedsWork() { return Index && Index.HCLoading(); }
    override void HCSlice() { if (Index && Index.HCLoading()) { Index.HCStep(null); } }
}

class HCGapcodeStoryIndex : Managed
{
    protected ref HCGapcodeStoryLimits m_Limits;
    protected FileHandle m_Input;
    protected bool m_InputOpen;
    protected bool m_Loading;
    protected bool m_Reading;
    // At most one 32 KiB chunk plus an unfinished bounded row. Scan by offset
    // rather than copying the remaining chunk after every decoded row.
    protected string m_Buffer;
    protected int m_BufferCursor;
    protected int m_ReadChunks;
    protected ref map<string, bool> m_AdmittedKits = new map<string, bool>;
    protected int m_LineCursor;
    protected int m_LoadBatches;
    protected int m_LoadGuardYields;
    protected bool m_RowComma;
    protected bool m_HaveRow;
    protected HCScenesModule m_Owner;
    protected ref HCStartupStoryIndex m_StartupIndex;
    protected ref map<string, ref HCGapcodeStorySite> m_Sites = new map<string, ref HCGapcodeStorySite>;
    protected ref array<ref HCGapcodeStoryCandidate> m_Pairs = new array<ref HCGapcodeStoryCandidate>;
    protected ref map<string, bool> m_Ids = new map<string, bool>;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected string m_Header;
    protected int m_Phase;
    protected int m_Bytes;
    protected int m_Cursor;
    protected int m_Qualified;
    protected bool m_Complete;
    protected bool m_Off;
    protected bool m_Logged;
    protected string m_Reason = "HC42_INDEX_LOADING";
    protected ref HCGapcodeStoryCandidate m_Selected;

    string HCReason() { return m_Reason; }
    bool HCOff() { return m_Off; }
    bool HCHasSelectedPlan() { return m_Selected != null; }
    // Loading streams and parses the source. The startup adapter only enters while
    // loading; selection and native clearance remain on scene ticks.
    bool HCLoading() { return m_Loading; }
    bool HCNeedsStep() { return m_Loading || (m_Complete && m_Qualified > 0 && !m_Selected); }
    // Operational readiness is source admission, independent of transient
    // selection/observer clearance. Native placement acceptance stays pending.
    bool HCReady() { return m_Complete && m_Qualified > 0; }

    void HCStart()
    {
        m_Off = FileExist("$profile:HollowCountry/acceptance/story_index.disable");
        if (m_Off) { HCRefuse("HC42_OPERATOR_OFF"); return; }
        m_Limits = HCGapcodeStoryLimits.HCLoad();
        if (!m_Limits) { HCRefuse("HC42_INDEX_CONFIG_INVALID"); return; }
        m_Input = OpenFile("$mission:hollow-country/events/story-sites.json", FileMode.READ);
        if (m_Input) { m_InputOpen = true; }
        if (!m_InputOpen) { HCRefuse("HC42_INDEX_MISSING"); return; }
        // Read and decode on separate bounded visits. The pump supplies the
        // shared frame deadline; normal ticks retain STORY_INDEX admission.
        m_Reading = true;
        m_Loading = true;
        m_StartupIndex = new HCStartupStoryIndex;
        m_StartupIndex.Index = this;
        HCStartupPump.HCRegister(m_StartupIndex, "story_index");
        Print(HCV2Admission.Line("HC-42 indexed stories", true, "HC42_KIT_SITE_SURVEY", false) + " runtime=PENDING");
    }

    void HCStop()
    {
        if (m_InputOpen) { CloseFile(m_Input); m_InputOpen = false; }
        m_Loading = false;
        m_Reading = false;
        m_Buffer = "";
        m_BufferCursor = 0;
    }

    void HCLog()
    {
        if (m_Logged) { return; }
        m_Logged = true;
        string report = "[HC Scenes] HC-42 index sites=" + m_Sites.Count().ToString() + " candidates=" + m_Pairs.Count().ToString() + " qualified=" + m_Qualified.ToString();
        report = report + " load_rows=" + m_LineCursor.ToString() + " load_batches=" + m_LoadBatches.ToString() + " guard_yields=" + m_LoadGuardYields.ToString();
        report = report + " read_chunks=" + m_ReadChunks.ToString() + " read_bytes=" + m_Bytes.ToString();
        Print(report + " runtime=PENDING");
    }

    bool HCRefuse(string reason)
    {
        if (m_Reason != reason) { Print("[HC Scenes] HC-42 reason=" + reason + " runtime=PENDING"); }
        // Shared readiness reports boot and first admission. A later streaming
        // refusal must also leave a false receipt rather than only a pending boot.
        if (m_StartupIndex)
        {
            Print("[HC Ready] module=Scenes enabled=true ready=false reason=" + HCReached.Token(reason) + " runtime=PENDING");
        }
        m_Reason = reason;
        m_Selected = null;
        HCStop();
        HCLog();
        return false;
    }

    // Stream format is the repository's one-object-per-line authored index.
    // Reject reformatting/multiline rows, truncation, duplicate IDs and dangling
    // candidates instead of silently considering a partial file operational.
    bool HCLine(string line)
    {
        line.TrimInPlace();
        if (line == "") { return true; }
        if (m_Phase == 0)
        {
            if (line == "\"Sites\": [")
            {
                m_Header.TrimInPlace();
                if (m_Header.Length() < 2) { return false; }
                m_Header = m_Header.Substring(0, m_Header.Length() - 1) + "}";
                HCGapcodeStoryHeader header;
                string headerError;
                if (!JsonFileLoader<HCGapcodeStoryHeader>.LoadData(m_Header, header, headerError) || !header) { return false; }
                if (header.SchemaVersion != 1 || header.WorldName != "chernarusplus" || header.Package != "HC-42") { return false; }
                m_Header = "";
                m_Phase = 1;
                return true;
            }
            if (m_Header.Length() + line.Length() > m_Limits.MaxLineBytes) { return false; }
            m_Header = m_Header + line;
            return true;
        }
        if (m_Phase == 1 && line == "],")
        {
            if (!m_HaveRow || m_RowComma) { return false; }
            m_HaveRow = false;
            m_Phase = 2;
            return true;
        }
        if (m_Phase == 2 && line == "\"Candidates\": [") { m_Phase = 3; return true; }
        if (m_Phase == 3 && line == "]")
        {
            if (!m_HaveRow || m_RowComma) { return false; }
            m_Phase = 4;
            return true;
        }
        if (m_Phase == 4 && line == "}") { m_Phase = 5; return true; }
        if (m_Phase != 1 && m_Phase != 3) { return false; }
        if (m_HaveRow && !m_RowComma) { return false; }
        int length = line.Length();
        m_RowComma = line.Substring(length - 1, 1) == ",";
        if (m_RowComma) { line = line.Substring(0, length - 1); }
        m_HaveRow = true;
        string error;
        if (m_Phase == 1)
        {
            HCGapcodeStorySite site;
            if (!JsonFileLoader<HCGapcodeStorySite>.LoadData(line, site, error) || !site) { return false; }
            if (m_Sites.Count() >= m_Limits.MaxSites || m_Sites.Contains(site.Id) || !HCEventDirector.TextValid(site.Id, 48) || site.LocalityId == "") { return false; }
            if (!HCJsonFields.Has(line, "Anchor") || !HCJsonFields.Has(line, "SourceReviewed") || !HCEventRuntimePolicy.PositionValid(site.Anchor)) { return false; }
            m_Sites.Insert(site.Id, site);
            return true;
        }
        HCGapcodeStoryCandidate pair;
        if (!JsonFileLoader<HCGapcodeStoryCandidate>.LoadData(line, pair, error) || !pair) { return false; }
        if (m_Pairs.Count() >= m_Limits.MaxCandidates || m_Ids.Contains(pair.Id) || !HCEventDirector.TextValid(pair.Id, 96) || (pair.Variant != "primary" && pair.Variant != "regional")) { return false; }
        HCGapcodeStorySite anchor;
        if (!m_Sites.Find(pair.SiteId, anchor)) { return false; }
        // Kit definitions are immutable: admit each distinct kit once instead
        // of allocating its full prop array for every candidate in the index.
        if (!m_AdmittedKits.Contains(pair.Kit))
        {
            if (!HCSceneKits.Find(pair.Kit)) { return false; }
            m_AdmittedKits.Insert(pair.Kit, true);
        }
        m_Ids.Insert(pair.Id, true);
        m_Pairs.Insert(pair);
        // 'qualified' here counts admitted source pairs, NEVER native receipts.
        if (HCSourceValid(anchor)) { m_Qualified = m_Qualified + 1; }
        return true;
    }

    static bool HCSourceValid(HCGapcodeStorySite site)
    {
        if (!site || !site.SourceReviewed || site.SourceRef == "" || site.LocalityId == "") { return false; }
        if (site.AnchorSource != "stock mapgrouppos.xml" && site.AnchorSource != "HCEventReviewedSites.Curated") { return false; }
        return HCEventRuntimePolicy.PositionValid(site.Anchor) && site.Anchor[1] != 0;
    }

    // <=configured lines OR <=one candidate/preflight on a later tick.
    // Checkpoint-safe: only temporary index/diagnostic state changes here.
    // Preflight/Layout read config, observers, objects, doors and terrain;
    // they create no native objects and mutate no persisted scene state.
    void HCStep(HCScenesModule owner)
    {
        if (owner) { m_Owner = owner; }
        if (m_Loading)
        {
            // On normal ticks, one shared unit per batch; frame catch-up instead
            // uses the shared frame deadline and the same line/time caps. The tick pool is usually spent
            // by earlier consumers, and one unit per line read the 1075-line index at ~1 line/s.
            // STORY_INDEX, not SITUATIONS: Events claims that slot's starved take every tick.
            if (!HCStartupPump.HCInSlice() && !HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_STORY_INDEX, 1)) { return; }
            m_LoadBatches++;
            // Retain the configured row ceiling; leave room for the final JSON row.
            m_Work.HCReset(m_Limits.ReadLinesPerTick, HCStartupPump.HCSliceMs(Math.Min(HCPerfConfig.HCGet().SliceMs, 2)));
            string line;
            for (int row = 0; row < m_Limits.ReadLinesPerTick; row++)
            {
                // The loop already caps rows, so an early refusal is the 2 ms
                // cooperative guard. Count it to distinguish time from line caps
                // in the native completion receipt; one JSON row is atomic.
                if (!m_Work.HCContinue()) { m_LoadGuardYields++; return; }
                int end = m_Buffer.IndexOfFrom(m_BufferCursor, "\n");
                if (end < 0 && m_Reading)
                {
                    if (row > 0) { return; } // Keep native reads separate from JSON decode.
                    // Compact only at a chunk boundary; preserve a split JSON
                    // row byte-for-byte. A read is the last operation this visit.
                    int tail = m_Buffer.Length() - m_BufferCursor;
                    if (tail > m_Limits.MaxLineBytes) { HCRefuse("HC42_INDEX_INVALID"); return; }
                    if (tail > 0) { m_Buffer = m_Buffer.Substring(m_BufferCursor, tail); }
                    else { m_Buffer = ""; }
                    m_BufferCursor = 0;
                    string chunk;
                    int read = ReadFile(m_Input, chunk, 32768);
                    m_ReadChunks++;
                    if (read < 0 || read > 32768 || read != chunk.Length()) { HCRefuse("HC42_INDEX_INVALID"); return; }
                    m_Bytes = m_Bytes + read;
                    if (m_Bytes > m_Limits.MaxFileBytes) { HCRefuse("HC42_INDEX_INVALID"); return; }
                    if (read > 0) { m_Buffer = m_Buffer + chunk; return; }
                    CloseFile(m_Input);
                    m_InputOpen = false;
                    m_Reading = false;
                    return; // Final unterminated row is decoded on a later visit.
                }
                if (end < 0) { end = m_Buffer.Length(); }
                if (m_BufferCursor >= m_Buffer.Length())
                {
                    HCStop();
                    if (m_Phase != 5 || m_Pairs.Count() < 1) { HCRefuse("HC42_INDEX_INVALID"); return; }
                    m_Complete = true;
                    m_Reason = "HC42_PAIR_SELECTION_PENDING";
                    if (m_Qualified < 1) { HCRefuse("HC42_NO_QUALIFIED_PAIR"); return; }
                    HCLog();
                    return;
                }
                int length = end - m_BufferCursor;
                if (length > m_Limits.MaxLineBytes) { HCRefuse("HC42_INDEX_INVALID"); return; }
                line = "";
                if (length > 0) { line = m_Buffer.Substring(m_BufferCursor, length); }
                m_BufferCursor = end;
                if (end < m_Buffer.Length()) { m_BufferCursor++; }
                m_LineCursor++;
                if (!HCLine(line)) { HCRefuse("HC42_INDEX_INVALID"); return; }
            }
            return;
        }
        if (!owner || !m_Complete || m_Qualified < 1 || m_Selected) { return; }
        if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_STORY_INDEX, 1)) { return; }
        if (m_Cursor >= m_Pairs.Count()) { m_Cursor = 0; }
        HCGapcodeStoryCandidate candidate = m_Pairs[m_Cursor];
        m_Cursor = m_Cursor + 1;
        HCGapcodeStorySite source;
        if (!m_Sites.Find(candidate.SiteId, source) || !HCSourceValid(source)) { return; }
        HCEventSite placement = HCPlacement(source);
        if (!owner.SiteAvailable(placement.Position)) { return; }
        array<vector> positions;
        int variant;
        HCSceneKit candidateKit = HCSceneKits.Find(candidate.Kit);
        if (!HCSceneKits.Preflight(candidateKit, placement, positions, variant))
        {
            owner.PreflightRefused("HC42-index", HCSceneKits.Refusal());
            return;
        }
        m_Selected = candidate;
        m_Reason = "";
    }

    static HCEventSite HCPlacement(HCGapcodeStorySite source)
    {
        HCEventSite site = new HCEventSite;
        site.Id = source.Id;
        site.WorldName = "chernarusplus";
        site.Position = source.Anchor;
        site.Destination = source.Anchor;
        site.Reviewed = true;
        site.Surveyed = false;
        site.Provenance = "HC42-admitted-unverified";
        site.SourceSha256 = source.SourceRef;
        return site;
    }

    static bool HCPinnedSite(HCEventSite site)
    {
        if (!site || !site.Reviewed || site.Surveyed || site.WorldName != "chernarusplus") { return false; }
        if (site.Provenance != "HC42-admitted-unverified" || site.Id == "" || site.SourceSha256 == "") { return false; }
        if (site.RewardCache || site.ItemClass != "" || !HCEventRuntimePolicy.PositionValid(site.Position)) { return false; }
        return site.Position == site.Destination && site.Position[1] != 0;
    }

    HCSceneChainDefinition HCTakePlan(int sequence, array<string> legacyIds)
    {
        if (!HCReady() || !m_Selected) { return null; }
        HCGapcodeStoryCandidate selected = m_Selected;
        m_Selected = null;
        HCGapcodeStorySite source;
        if (!m_Sites.Find(selected.SiteId, source)) { return null; }
        m_Reason = "HC42_PAIR_SELECTION_PENDING";
        HCEventSite pinnedSite = HCPlacement(source);
        if (!m_Owner || !m_Owner.SiteAvailable(pinnedSite.Position)) { return null; }
        array<vector> pinPositions;
        int pinVariant;
        HCSceneKit selectedKit = HCSceneKits.Find(selected.Kit);
        if (!HCSceneKits.Preflight(selectedKit, pinnedSite, pinPositions, pinVariant))
        {
            m_Owner.PreflightRefused("HC42-index", HCSceneKits.Refusal());
            return null;
        }
        HCSceneChainDefinition plan = new HCSceneChainDefinition;
        plan.Id = HCStoryPolicy.HCIdentity(sequence, legacyIds);
        plan.SiteId = selected.SiteId;
        plan.IndexedCandidate = selected.Id;
        plan.IndexedSite = pinnedSite;
        HCSceneStageDefinition stage = new HCSceneStageDefinition;
        stage.Kit = selected.Kit;
        stage.DelaySeconds = 0;
        stage.Objective = HCEventReviewedSites.SceneMission(plan.IndexedSite, plan.Id + "-" + stage.Kit, 43200);
        plan.Stages.Insert(stage);
        return plan;
    }
}

// Extend the existing kit admission seam only; all placement/layout/cleanup
// methods remain the original implementation. Persisted sites can resume even
// when the current index is missing: the complete old plan stays authoritative.
modded class HCSceneKits
{
    override static bool Reviewed(HCEventSite site)
    {
        return super.Reviewed(site) || HCGapcodeStoryIndex.HCPinnedSite(site);
    }
}

// HC-19 remains the ONLY identity/clock/window/retirement/save owner.
// Substitute just its new-arrival plan source; never rewrite retained rows.
modded class HCStorySchedule
{
    protected HCGapcodeStoryIndex m_IndexedStories;

    void HCBindIndex(HCGapcodeStoryIndex index) { m_IndexedStories = index; }

    override string HCWaitReason()
    {
        if (!m_IndexedStories) { return super.HCWaitReason(); }
        if (!m_IndexedStories.HCReady() || !m_IndexedStories.HCHasSelectedPlan()) { return m_IndexedStories.HCReason(); }
        return "arrival_due";
    }

    override bool HCStep(int now, array<string> releasedIds)
    {
        if (!m_Ready || !m_IndexedStories) { return super.HCStep(now, releasedIds); }
        HCSceneChain candidate = HCCandidate();
        if (candidate && (candidate.Complete || candidate.Cancelled) && releasedIds && releasedIds.Find(candidate.Id) >= 0) { return super.HCStep(now, releasedIds); }
        if (now < m_State.LastNow || now < 1 || now > 999000000) { return HCRefuse("world-clock"); }
        // Advance HC-19's retained cursor even while no arrival is eligible.
        if (m_State.Chains.Count() > 0)
        {
            if (m_Cursor >= m_State.Chains.Count()) { m_Cursor = 0; }
            m_Cursor = m_Cursor + 1;
        }
        HCStoryProgress progress = m_State.Stories;
        if (!HCArrivalDue(now)) { return false; }
        if (progress.NextSequence >= 999999999) { return HCRefuse("sequence-exhausted"); }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return false; }
        HCSceneChainDefinition plan = m_IndexedStories.HCTakePlan(progress.NextSequence, progress.LegacyIds);
        if (!plan) { return false; }
        HCSceneChain arrived = new HCSceneChain;
        arrived.Id = plan.Id;
        arrived.StorySequence = progress.NextSequence;
        arrived.Director = HCEventDirector.Initialize(m_State.WorldName, arrived.Id);
        HCSceneChains.Schedule(arrived, plan.Stages[0], now);
        m_State.Catalog.Chains.Insert(plan);
        m_State.Chains.Insert(arrived);
        progress.NextSequence = progress.NextSequence + 1;
        progress.NextArrival = now + m_Config.ArrivalSeconds;
        if (!HCCommit(now)) { return false; }
        Print("[HC Scenes] HC-42 pinned id=" + plan.Id + " candidate=" + plan.IndexedCandidate + " site=" + plan.SiteId + " runtime=PENDING");
        return true;
    }
}
