// W5-PERF-6: <=4 ledger proposals/ring tick; population from AILimits.
// Native time/player cache evidence: HCWorkBudget.c (Game.c:914/945/1535).
// LC-T402 / #98, EXP-L1 + EXP-P2. Native evidence (installed snapshot):
// scripts-1.30.164289/3_Game/Global/Game.c:945 GetPlayers;
// 3_Game/Entities/Man.c:21 GetIdentity; Entities/Object.c:287 GetPosition,
// :517 IsAlive; 1_Core/proto/EnConvert.c:30 int.ToString;
// EnScript.c:380,385,394,407,470 array Count/Clear/Find/Insert/
// RemoveOrdered; EnDebug.c:96 Print. All other calls are project interfaces.
// Queue/cooldowns are process-local, never body persistence. Durable outcomes
// use HCWorldModule.AddFact and its existing verified temp/backup/copy store.
// HC-10 / #143-147, #139: no concurrent live copy of a party/cargo.
// Native persistence evidence: scripts-1.30.164289/1_Core/proto/EnSystem.c:
// 397 FileExist, 525 MakeDirectory, 528 DeleteFile, 531 CopyFile;
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData. Startup reads use
// HCWorldStore; tick writes use HCStagedSaveImage with verified readback.
// In process only Result confirms absence. On restart Persist=false provider
// bodies cannot survive; unresolved claims finish unknown, without cargo replay.
// HC has no dependency on the optional provider. No entities or inventory here.
class HCWorldProposal
{
    string Id;
    string FactionId;
    string PlaceId;
    vector Position;
    int ActorCap;
    string Kind;
    ref HCAIPartyIdentity Identity;
    // Runtime diagnostic carried to add-on consumers; never a custody decision.
    bool Fixture;
}

class HCWorldProposalLease
{
    ref HCWorldProposal Proposal;
    string RowId;
    int RowIndex = -1;
    float Created;
    bool Claimed;
    int CustodyRevision;
    int ResultRevision;
    bool Finished;
    bool Materialized;
    int Survivors;
    bool OutcomeApplied;
    bool Fixture;
}

// w29-debugmap #194: detached read-only row for the `materializer-proposals`
// debug layer (an ACTIVE proposal lease, not an eligible ledger candidate). No
// party identity, faction id or lease handle leaves the owner.
class HCDebugProposalRow
{
    string Id;
    string PlaceId;
    string Kind;
    vector Position;
    int ActorCap;
    string State = "queued";
    int AgeSeconds;
}

// Narrow READ-ONLY ledger seam, authored here without editing world owners'
// files. Returns fresh proposals, never retained ledger rows. Fixed indices
// use configured holdout/party spans for cooldowns (fixed for this process). The place anchor is deliberately NOT a house or player position.
modded class HCWorldModule
{
    HCWorldProposal MaterializerRow(int rowIndex)
    {
        if (!m_Running || !m_Data || rowIndex < 0 || rowIndex >= HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties) { return null; }
        HCWorldProposal row = new HCWorldProposal;
        if (rowIndex < HCAILimits.Get().MaxHoldouts)
        {
            if (rowIndex >= m_Data.Holdouts.Count()) { return null; }
            HCWorldHoldout holdout = m_Data.Holdouts[rowIndex];
            if (!holdout || (holdout.State != "OCCUPIED" && holdout.State != "ALERT") || holdout.Occupants < 1) { return null; }
            if (!HCHoldouts.HCAllowsMaterializer(holdout)) { return null; }
            row.Id = "holdout:" + holdout.Id;
            row.FactionId = holdout.FactionId;
            row.PlaceId = holdout.PlaceId;
            row.ActorCap = holdout.Occupants;
            row.Kind = "HOLDOUT";
            row.Identity = HCAIPartyIdentity.HCCreate(row.Id, "camp:" + holdout.Id, holdout.PlaceId, "stationary:" + holdout.Id, "cargo:" + holdout.Id, Epoch());
        }
        else
        {
            int partyIndex = rowIndex - HCAILimits.Get().MaxHoldouts;
            if (partyIndex >= m_Data.Parties.Count()) { return null; }
            HCWorldParty party = m_Data.Parties[partyIndex];
            if (!party || party.Materialized || !party.Route || party.Edge < 0 || party.Edge >= party.Route.Count() || party.Size < 1) { return null; }
            row.Id = "party:" + party.Id;
            row.FactionId = party.FactionId;
            row.PlaceId = party.Route[party.Edge];
            row.ActorCap = party.Size;
            row.Kind = party.Kind;
            row.Identity = HCAIPartyIdentity.HCCreate(row.Id, "home:" + party.Home, party.Home, "route:" + party.Id, "cargo:" + party.Id, Epoch());
        }
        HCWorldPlace place = m_Data.Place(row.PlaceId);
        HCWorldFaction faction = m_Data.Faction(row.FactionId);
        if (!place || !faction || faction.Strength < 1 || !row.Identity) { return null; }
        row.Position = place.Position;
        if (row.ActorCap > faction.Strength) { row.ActorCap = faction.Strength; }
        if (row.ActorCap > HCAILimits.Maximum(row.Kind)) { row.ActorCap = HCAILimits.Maximum(row.Kind); }
        return row;
    }
}

class HCWorldMaterializer : HCModule
{
    protected ref HCWorldActivityCounters m_Activity = new HCWorldActivityCounters("rings rows proposals claims materialized traces refused prerequisite cap no_players budget cooldown row_unavailable custody ring faction population sequence reserve provider_timeout");
    static const int MAX_PLAYERS = 32;
    static const int ROWS_PER_RING = 32;
    static const int PROVIDER_TIMEOUT = 120;
    static const int RING_SECONDS = 30;
    static const int LOG_SECONDS = 600;
    static const int ROW_COOLDOWN = 21600;
    protected static HCWorldMaterializer s_Instance;
    protected ref array<ref HCWorldProposalLease> m_Active = new array<ref HCWorldProposalLease>;
    protected ref array<ref HCWorldProposalLease> m_Undelivered = new array<ref HCWorldProposalLease>;
    protected ref array<float> m_Cooldowns = new array<float>;
    protected float m_Clock;
    protected float m_RingSeconds;
    protected float m_LogSeconds;
    protected int m_PlayerCursor;
    protected int m_RowCursor;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref HCUnitBudget m_UnitBudget = new HCUnitBudget;
    protected ref HCAIPartyCustodyData m_Custody;
    protected bool m_CustodyReady;
    protected string m_CustodyText;
    protected ref HCStagedSaveImage m_CustodyImage = new HCStagedSaveImage;
    protected ref HCWorldCustodySaveJob m_CustodyJob;
    protected int m_CustodyRevision;
    protected int m_CustodyCommitted;
    protected int m_CustodySnapshotRevision;
    protected string m_CustodySnapshot;
    protected int m_CustodyStage;
    protected float m_CustodyStepTime = -1;
    protected ref HCWorkBudget m_CustodyStepBudget = new HCWorkBudget;
    protected bool m_CustodyFailurePrinted;
    protected string m_CustodyPath = "$profile:HollowCountry/ai-custody.json";
    protected int m_DuplicateRefused;
    protected int m_Proposals;
    protected int m_Materialized;
    protected int m_Traces;
    protected bool m_Running;
    protected bool m_AdmissionPrinted;
    protected bool m_StartedOnce;
    protected int m_CustodyNextLeaseSeen = 1;
    protected int m_CustodyReadRetries;
    protected bool m_CustodyRetryRead;
    protected string m_CustodyLoadFault;
    protected string m_CustodyRetainedSource;
    protected bool m_CustodyKeepTmp;
    protected int m_CustodyArchiveScans;
    protected static const int HC_ARCHIVE_SCAN_LIMIT = 64;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "Materializer"; }
    // World is a feature phase owner. Reverse shutdown must resolve custody
    // before World's final flush; readiness is captured after all start hooks.
    override int StartupPhase() { return HC_PHASE_ADDON; }
    protected bool m_Stopping;
    protected int m_StopFolded;
    protected int m_StopUnavailable;
    static const int HC_REJECTED_SLOTS = 8;

    // Wave 16: a running materializer whose party custody could not be read keeps the AI budget blocked
    // (HCAIBudget.Block above): that is a real degradation, never ready.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        string fault = "";
        if (m_Running && !m_CustodyReady)
        {
            fault = m_CustodyLoadFault;
            if (fault == "") { fault = "custody_unreadable_ai_budget_blocked"; }
        }
        HCModuleReadiness.HCDerive(m_Operational, m_Running, "", fault, "materializer_custody_loaded");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableEncounters; }

    override void OnStart(HCSettings settings)
    {
        if (m_Running || !IsEnabled(settings)) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Materializer", true, "EXP-L1", HCV2Gates.Qualified("EXP-L1")));
            m_AdmissionPrinted = true;
        }
        m_Active.Clear();
        m_Cooldowns.Clear();
        for (int cooldownIndex = 0; cooldownIndex < HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties; cooldownIndex++) { m_Cooldowns.Insert(0); }
        m_Clock = 0;
        m_RingSeconds = 0;
        m_LogSeconds = 0;
        m_CustodyReadRetries = 0;
        m_CustodyArchiveScans = 0;
        HCWorldStore.HCResetCompareBudget();
        m_CustodyRetryRead = false;
        m_CustodyStepTime = -1;
        m_CustodyStage = 0;
        m_CustodyRevision = 0;
        m_CustodyCommitted = 0;
        m_CustodyImage = new HCStagedSaveImage;
        m_CustodyJob = new HCWorldCustodySaveJob;
        m_CustodyJob.Owner = this;
        HCSaveScheduler.HCRegister(m_CustodyJob);
        m_CustodyReady = this.HCLoadCustody();
        if (m_CustodyReady) { this.HCAcceptCustodyLoad(); }
        else if (!m_CustodyRetryRead) { HCAIBudget.Block(); }
        m_Running = true;
        s_Instance = this;
        this.HCPlanLine("on");
    }

    // Shared completion for initial load and bounded transient-read retries.
    protected void HCAcceptCustodyLoad()
    {
        if (!m_StartedOnce) { this.HCRestoreCustody(); }
        else
        {
            // A module off/on transition is not a process restart. Provider
            // bodies may still exist; retain their claims until Result.
            foreach (HCAIPartyCustodyRow sameProcess : m_Custody.Rows)
            {
                if (sameProcess.Outcome == "CLAIMED" || sameProcess.Outcome == "QUARANTINED") { HCAIBudget.Restore(sameProcess.LeaseId, sameProcess.ActorCap); }
            }
        }
        if (m_CustodyReady)
        {
            map<string, bool> durableClaims = new map<string, bool>;
            foreach (HCAIPartyCustodyRow pendingRow : m_Custody.Rows)
            {
                if (pendingRow.Outcome == "CLAIMED") { durableClaims.Set(pendingRow.LeaseId, true); }
            }
            foreach (HCWorldProposalLease undelivered : m_Undelivered)
            {
                if (durableClaims.Contains(undelivered.Proposal.Id))
                {
                    undelivered.CustodyRevision = m_CustodyCommitted;
                    undelivered.Created = 0;
                    m_Active.Insert(undelivered);
                }
                else { HCAIBudget.Release(undelivered.Proposal.Id); }
            }
            m_Undelivered.Clear();
        }
        // A failed load or migration is still the first start on the next toggle.
        if (m_CustodyReady)
        {
            m_StartedOnce = true;
            HCAIBudget.Release("custody:read_retry");
        }
    }

    // A failed startup read retries initialization at most three times, outside
    // routine OnTick/save dispatch. Recovery is the same one-time synchronous boot
    // transaction, not a periodic store reader. Native queue API inspected in
    // 2_GameLib/tools.c (ScriptCallQueue.CallLater/Remove), Game.c:1550.
    protected void HCRetryCustodyLoad()
    {
        if (!m_Running || m_CustodyReady || !m_CustodyRetryRead) { return; }
        m_CustodyReady = this.HCLoadCustody();
        if (m_CustodyReady) { this.HCAcceptCustodyLoad(); }
        else if (!m_CustodyRetryRead) { HCAIBudget.Block(); }
    }

    protected void HCPumpCustodyFallback()
    {
        if (HCPerfConfig.HCGet().EnableSharedSaves && HCSaveScheduler.HCRegistered(m_CustodyJob)) { return; }
        float now = GetGame().GetTickTime();
        if (now != m_CustodyStepTime)
        {
            m_CustodyStepTime = now;
            m_CustodyStepBudget.HCReset(HCWorldRuntimeConfig.HCGet().SaveStagesPerTick, HCPerfConfig.HCGet().SaveStageTargetMs);
        }
        if (m_CustodyStepBudget.HCContinue()) { HCSaveScheduler.HCPumpFallback(m_CustodyJob); }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0) || deltaTime > 3600) { return; }
        if (m_Activity.HCDue(deltaTime)) { m_Activity.HCLog("[HollowCountry] V2 materializer", " active=" + m_Active.Count().ToString() + " custody_ready=" + m_CustodyReady.ToString()); }
        this.HCPumpCustodyFallback();
        m_Clock += deltaTime;
        m_RingSeconds += deltaTime;
        m_LogSeconds += deltaTime;
        Expire();
        HCReached.Mark("materializer.expire");
        if (m_RingSeconds >= RING_SECONDS)
        {
            m_RingSeconds = 0;
            InterestRing();
        }
        if (m_LogSeconds >= LOG_SECONDS)
        {
            m_LogSeconds = 0;
            // Activity summary above includes window and lifetime outcomes.
            this.HCPlanLine("on");
        }
    }

    override void OnStop()
    {
        m_Stopping = true;
        m_StopFolded = 0;
        m_StopUnavailable = 0;
        // Mission shutdown owns provider cleanup. Unreported body outcomes are
        // not invented or replayed after restart; ledger facts remain durable.
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(this.HCRetryCustodyLoad);
        if (m_CustodyReady)
        {
            if (!HCSaveScheduler.HCFlush(m_CustodyJob, true)) { this.HCCustodySaveFailed(); }
            else
            {
                // Resolve only finished results here. Expire may create new
                // timeout results; those would need another flush before stop.
                for (int finishedIndex = m_Active.Count() - 1; finishedIndex >= 0; finishedIndex--)
                {
                    HCWorldProposalLease finished = m_Active[finishedIndex];
                    if (finished.Finished && m_CustodyCommitted >= finished.ResultRevision) { this.Resolve(finishedIndex, finished.Materialized, finished.Survivors); }
                }
            }
        }
        Print("[HC " + GetName() + "] custody_stop folded=" + m_StopFolded.ToString() + " unavailable=" + m_StopUnavailable.ToString());
        m_Stopping = false;
        HCSaveScheduler.HCUnregister(m_CustodyJob);
        m_Running = false;
        this.HCPlanLine("off");
        if (s_Instance == this) { s_Instance = null; }
        foreach (HCWorldProposalLease stopped : m_Active)
        {
            // Unclaimed leases have never been handed to a provider.
            if (!stopped.Claimed && stopped.CustodyRevision > 0)
            {
                // Keep the undelivered continuation as well as its durable row.
                // Next or timeout will finish it after an in-process restart.
                m_Undelivered.Insert(stopped);
            }
            else if (!stopped.Claimed) { HCAIBudget.Release(stopped.Proposal.Id); }
        }
        m_Active.Clear();
    }

    protected void HCPlanLine(string state)
    {
        if (state != "off" && !m_CustodyReady) { state = "refused"; }
        int leases = 0;
        if (m_Custody && m_Custody.Rows) { leases = m_Custody.Rows.Count(); }
        Print("[HC Plan] HC-10 actor_cap=" + HCAILimits.Get().MaxLiveAI.ToString() + " leases=" + leases.ToString() + " duplicate_refused=" + m_DuplicateRefused.ToString() + " state=" + state + " runtime=PENDING");
    }

    // Canonical V1/V2 images remain unchanged. NextLease is an existing durable
    // high-water mark; new checkpoints advance it even for result-only changes.
    // Old V2 checkpoints can tie, which is deliberately admissible (>=).
    protected HCAIPartyCustodyData HCDecodeCustody(string text)
    {
        HCAIPartyCustodyData loaded;
        string error;
        if (text == "" || text.Length() > HCWorldStore.MAX_BYTES || !JsonFileLoader<HCAIPartyCustodyData>.LoadData(text, loaded, error) || !loaded) { return null; }
        if (loaded.SchemaVersion == 1 && loaded.NextLease == 0) { loaded.NextLease = 1; }
        if (!this.HCValidCustody(loaded)) { return null; }
        string canonical;
        if (loaded.SchemaVersion == 1)
        {
            HCAIPartyCustodyLegacyData legacy;
            if (!JsonFileLoader<HCAIPartyCustodyLegacyData>.LoadData(text, legacy, error) || !legacy || legacy.SchemaVersion != 1) { return null; }
            if (!JsonFileLoader<HCAIPartyCustodyLegacyData>.MakeData(legacy, canonical, error) || canonical != text) { return null; }
        }
        else if (!JsonFileLoader<HCAIPartyCustodyData>.MakeData(loaded, canonical, error) || canonical != text) { return null; }
        foreach (HCAIPartyCustodyRow decodedRow : loaded.Rows)
        {
            // V1 admitted lease:<party>:<generation>, not a sequence number.
            // Those rows survive migration to V2; skip the legacy shape before
            // ToInt. Numeric sequence tokens remain canonical in both schemas.
            if (decodedRow.LeaseId.IndexOf("lease:") != 0) { continue; }
            if (decodedRow.LeaseId.Length() <= 6) { return null; }
            string suffix = decodedRow.LeaseId.Substring(6, decodedRow.LeaseId.Length() - 6);
            bool legacyShape = false;
            HCTextWindow leaseText = new HCTextWindow(suffix);
            for (int token = 0; token < leaseText.Length(); token++)
            {
                if (leaseText.At(token) == ":") { legacyShape = true; break; }
            }
            if (legacyShape) { continue; }
            int number = suffix.ToInt();
            if (number < 1 || number >= 2147483647 || suffix != number.ToString()) { return null; }
            // V1 had no NextLease field. Derive its watermark only after its
            // exact legacy image passed canonical validation above.
            if (loaded.SchemaVersion == 1 && number >= loaded.NextLease) { loaded.NextLease = number + 1; }
            if (number >= loaded.NextLease) { return null; }
        }
        return loaded;
    }

    // Read failures never authorize deletion without preservation. The materializer's
    // readiness/debt queries refuse admission during three delayed startup retries;
    // exhaustion permits raw preservation and selection of a valid copy.
    protected bool HCReadCustody(string path, out string text)
    {
        if (HCWorldStore.ReadChecked(path, text)) { return true; }
        m_CustodyLoadFault = "custody_read_failed";
        if (m_CustodyReadRetries < 3)
        {
            m_CustodyReadRetries++;
            // A temporary reservation blocks all providers without latching
            // the irreversible process-wide Block on a transient file error.
            HCAIBudget.Restore("custody:read_retry", HCAILimits.Get().MaxLiveAI);
            m_CustodyRetryRead = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(this.HCRetryCustodyLoad, 1000, false);
            Print("[HC " + GetName() + "] custody_read_failed retry=" + m_CustodyReadRetries.ToString());
        }
        else { Print("[HC " + GetName() + "] custody_read_failed reason=retry_exhausted"); }
        return false;
    }

    protected bool HCCustodyFault(string reason)
    {
        m_CustodyLoadFault = reason;
        Print("[HC " + GetName() + "] " + reason);
        // IO faults are retryable boot transactions, not an irreversible latch.
        if (m_CustodyReadRetries < 3)
        {
            m_CustodyReadRetries++;
            HCAIBudget.Restore("custody:read_retry", HCAILimits.Get().MaxLiveAI);
            m_CustodyRetryRead = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(this.HCRetryCustodyLoad, 1000, false);
        }
        return false;
    }

    protected string HCRejectedSlot(int slot)
    {
        return m_CustodyPath + ".rejected." + slot.ToString();
    }

    protected bool HCHasCustodyWitness()
    {
        string witness = m_CustodyPath + ".rejected.tmp";
        if (!FileExist(witness) || !HCWorldStore.RawEqual(witness, m_CustodyPath)) { return false; }
        if (FileExist(m_CustodyPath + ".rejected") && HCWorldStore.RawEqual(witness, m_CustodyPath + ".rejected")) { return true; }
        for (int slot = 0; slot < HC_REJECTED_SLOTS; slot++)
        {
            if (FileExist(this.HCRejectedSlot(slot)) && HCWorldStore.RawEqual(witness, this.HCRejectedSlot(slot))) { return true; }
        }
        return false;
    }

    // Preserve arbitrary raw bytes, including a string-read failure, through a
    // verified witness. Slots are compacted oldest first; interrupted copies
    // leave duplicate archives, never authorize deleting the source. All loops
    // are bounded one-time boot work. Round-4's single rejection is slot zero.
    protected bool HCPreserveCustodyFile(string source)
    {
        string legacy = m_CustodyPath + ".rejected";
        bool adopting = FileExist(legacy);
        if (adopting)
        {
            HCModuleReadiness.HCUse(GetName(), "custody_legacy_adoption");
            Print("[HC " + GetName() + "] custody_legacy_adoption");
            if (!FileExist(this.HCRejectedSlot(0)))
            {
                if (!CopyFile(legacy, this.HCRejectedSlot(0))) { return this.HCCustodyFault("custody_rejected_adopt_copy_failed"); }
                if (!HCWorldStore.RawEqual(legacy, this.HCRejectedSlot(0))) { return this.HCKeepUnverifiedCustody(source); }
                if (!DeleteFile(legacy)) { return this.HCCustodyFault("custody_rejected_adopt_delete_failed"); }
            }
            else if (HCWorldStore.RawEqual(legacy, this.HCRejectedSlot(0)))
            {
                if (!DeleteFile(legacy)) { return this.HCCustodyFault("custody_rejected_adopt_delete_failed"); }
            }
            // A crash may leave a different slot zero. Preserve the legacy
            // file through the same bounded archive before removing its name.
            else
            {
                if (!this.HCArchiveCustodyFile(legacy)) { return false; }
                if (m_CustodyRetainedSource == legacy) { return this.HCKeepUnverifiedCustody(source); }
                if (!DeleteFile(legacy)) { return this.HCCustodyFault("custody_rejected_adopt_delete_failed"); }
            }
        }
        if (adopting)
        {
            HCModuleReadiness.HCUse(GetName(), "custody_legacy_adopted");
            Print("[HC " + GetName() + "] custody_legacy_adopted");
        }
        return this.HCArchiveCustodyFile(source);
    }

    // If native raw qualification fails, do not mistake an unverifiable copy
    // for permission to remove its source. The valid backup becomes the active
    // checkpoint (its normal .tmp/.bak protocol is unchanged). Next boot makes
    // the same choice, retaining the original raw file under its original name.
    protected bool HCKeepUnverifiedCustody(string source, string faultReason = "")
    {
        string text;
        bool read = HCWorldStore.ReadChecked(source, text);
        string reason = "unverified_read";
        if (read && text.Length() > HCWorldStore.MAX_BYTES) { reason = "unverified_oversize"; }
        string copy = source + "." + reason;
        if (!FileExist(copy))
        {
            if (!CopyFile(source, copy) || !FileExist(copy)) { return this.HCCustodyFault("custody_unverified_copy_failed"); }
        }
        // Existing unverified copies are never overwritten; the source remains
        // the authoritative raw evidence, even if CopyFile was torn on crash.
        m_CustodyRetainedSource = source;
        if (faultReason != "") { reason = faultReason; }
        HCModuleReadiness.HCUse(GetName(), "custody_" + reason);
        Print("[HC " + GetName() + "] custody_" + reason + " source_retained=true");
        return true;
    }

    protected bool HCArchiveCustodyFile(string source)
    {
        string temporary = m_CustodyPath + ".rejected.tmp";
        // Across all delayed retries, scan at most 64 slots (8 full scans).
        if (m_CustodyArchiveScans >= HC_ARCHIVE_SCAN_LIMIT)
        {
            Print("[HC " + GetName() + "] custody_archive_scan_budget_exhausted");
            return this.HCKeepUnverifiedCustody(source, "archive_scan_budget_exhausted");
        }
        m_CustodyArchiveScans += HC_REJECTED_SLOTS;
        for (int match = 0; match < HC_REJECTED_SLOTS; match++)
        {
            if (FileExist(this.HCRejectedSlot(match)) && HCWorldStore.RawEqual(source, this.HCRejectedSlot(match))) { return true; }
        }
        // Do not destroy a witness being archived. A stale temporary of any
        // shape can be retired: its source stays intact until preservation ends.
        if (source != temporary)
        {
            if (FileExist(temporary) && !DeleteFile(temporary)) { return this.HCCustodyFault("custody_rejected_tmp_delete_failed"); }
            if (!CopyFile(source, temporary)) { return this.HCCustodyFault("custody_rejected_tmp_copy_failed"); }
            if (!HCWorldStore.RawEqual(source, temporary)) { return this.HCKeepUnverifiedCustody(source); }
        }
        int used;
        for (int slot = 0; slot < HC_REJECTED_SLOTS; slot++)
        {
            string path = this.HCRejectedSlot(slot);
            if (!FileExist(path)) { continue; }
            if (slot != used)
            {
                string compact = this.HCRejectedSlot(used);
                if (!CopyFile(path, compact)) { return this.HCCustodyFault("custody_rejected_compact_copy_failed"); }
                if (!HCWorldStore.RawEqual(path, compact)) { return this.HCKeepUnverifiedCustody(source); }
                if (!DeleteFile(path)) { return this.HCCustodyFault("custody_rejected_compact_delete_failed"); }
            }
            used++;
        }
        if (used == HC_REJECTED_SLOTS)
        {
            Print("[HC " + GetName() + "] custody_rejected_retired reason=archive_cap oldest=0");
            if (!DeleteFile(this.HCRejectedSlot(0))) { return this.HCCustodyFault("custody_rejected_retire_delete_failed"); }
            for (int shift = 1; shift < HC_REJECTED_SLOTS; shift++)
            {
                string oldPath = this.HCRejectedSlot(shift);
                string newPath = this.HCRejectedSlot(shift - 1);
                if (!CopyFile(oldPath, newPath)) { return this.HCCustodyFault("custody_rejected_rotate_copy_failed"); }
                if (!HCWorldStore.RawEqual(oldPath, newPath)) { return this.HCKeepUnverifiedCustody(source); }
                if (!DeleteFile(oldPath)) { return this.HCCustodyFault("custody_rejected_rotate_delete_failed"); }
            }
            used--;
        }
        string rejected = this.HCRejectedSlot(used);
        if (!CopyFile(temporary, rejected)) { return this.HCCustodyFault("custody_rejected_copy_failed"); }
        if (!HCWorldStore.RawEqual(temporary, rejected)) { return this.HCKeepUnverifiedCustody(source); }
        if (source != temporary && !DeleteFile(temporary)) { return this.HCCustodyFault("custody_rejected_tmp_delete_failed"); }
        string tag = "custody_primary_rejected";
        if (source == m_CustodyPath + ".tmp") { tag = "custody_tmp_archived"; }
        if (source == m_CustodyPath + ".rejected") { return true; } // Adoption is counted once by the caller.
        HCModuleReadiness.HCUse(GetName(), tag);
        Print("[HC " + GetName() + "] " + tag + " reason=raw_preserved slot=" + used.ToString());
        return true;
    }

    protected bool HCRecoverCustodyTmp()
    {
        string temporary = m_CustodyPath + ".tmp";
        string intent;
        if (!this.HCReadCustody(temporary, intent))
        {
            if (m_CustodyRetryRead) { return false; }
            // Exhausted string reads (including NUL conversion) are not a
            // permanent refusal when another fully valid checkpoint survives.
            string survivor;
            bool read = HCWorldStore.ReadChecked(m_CustodyPath, survivor);
            bool valid;
            if (read) { valid = this.HCDecodeCustody(survivor) != null; }
            if (!valid)
            {
                read = HCWorldStore.ReadChecked(m_CustodyPath + ".bak", survivor);
                if (read) { valid = this.HCDecodeCustody(survivor) != null; }
            }
            bool fresh = !FileExist(m_CustodyPath);
            if (FileExist(m_CustodyPath + ".bak")) { fresh = false; }
            if (!valid && !fresh) { return false; }
            if (!this.HCPreserveCustodyFile(temporary)) { return false; }
            if (m_CustodyRetainedSource == temporary)
            {
                m_CustodyKeepTmp = true;
                Print("[HC " + GetName() + "] custody_tmp_kept reason=read_failed_unverified");
                return true;
            }
            else if (!DeleteFile(temporary)) { return this.HCCustodyFault("custody_tmp_retire_delete_failed"); }
            HCModuleReadiness.HCUse(GetName(), "custody_tmp_retired");
            Print("[HC " + GetName() + "] custody_tmp_retired reason=read_failed_preserved");
            return true;
        }
        HCAIPartyCustodyData next = this.HCDecodeCustody(intent);
        string primaryText;
        if (FileExist(m_CustodyPath) && !this.HCReadCustody(m_CustodyPath, primaryText))
        {
            if (m_CustodyRetryRead) { return false; }
            if (!this.HCPreserveCustodyFile(m_CustodyPath)) { return false; }
            // Preserve arbitrary torn bytes before selecting a valid intent.
            primaryText = "";
        }
        HCAIPartyCustodyData primary = this.HCDecodeCustody(primaryText);
        // Keep committed checkpoints and process-local proposals nondecreasing.
        // Merely decoding an uncommitted intent must not poison fallback.
        if (primary && primary.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = primary.NextLease; }
        string backupImage;
        HCAIPartyCustodyData backupFloor;
        bool backupRead = HCWorldStore.ReadChecked(m_CustodyPath + ".bak", backupImage);
        if (backupRead) { backupFloor = this.HCDecodeCustody(backupImage); }
        if (backupFloor && backupFloor.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = backupFloor.NextLease; }
        string reason = "invalid";
        if (next && next.NextLease >= m_CustodyNextLeaseSeen && (!primary || next.NextLease >= primary.NextLease))
        {
            if (!primary && FileExist(m_CustodyPath))
            {
                string witness = m_CustodyPath + ".rejected.tmp";
                // A byte-equal archive/witness pair is written only by recovery
                // before promotion. A torn CopyFile need not leave a prefix.
                if (!this.HCHasCustodyWitness())
                {
                    if (!this.HCPreserveCustodyFile(m_CustodyPath)) { return false; }
                    if (m_CustodyRetainedSource == m_CustodyPath)
                    {
                        if (!this.HCSelectRetainedCustody()) { return false; }
                        if (FileExist(m_CustodyPath + ".tmp")) { return this.HCRecoverCustodyTmp(); }
                        return true;
                    }
                    if (FileExist(witness) && !DeleteFile(witness)) { return this.HCCustodyFault("custody_witness_delete_failed"); }
                    if (!CopyFile(m_CustodyPath, witness)) { return this.HCCustodyFault("custody_witness_copy_failed"); }
                    if (!HCWorldStore.RawEqual(m_CustodyPath, witness))
                    {
                        if (!this.HCKeepUnverifiedCustody(m_CustodyPath)) { return false; }
                        if (!this.HCSelectRetainedCustody()) { return false; }
                        if (FileExist(m_CustodyPath + ".tmp")) { return this.HCRecoverCustodyTmp(); }
                        return true;
                    }
                }
            }
            // Keep intent throughout backup repair/promotion/readback. A crash
            // repeats this selection, never dispatches a claim or replays cargo.
            if (primary && primaryText != intent)
            {
                string backup = m_CustodyPath + ".bak";
                if (FileExist(backup) && !DeleteFile(backup)) { return this.HCCustodyFault("custody_backup_delete_failed"); }
                if (!CopyFile(m_CustodyPath, backup)) { return this.HCCustodyFault("custody_primary_backup_copy_failed"); }
                string backupText;
                if (!this.HCReadCustody(backup, backupText)) { return false; }
                if (backupText != primaryText) { return this.HCCustodyFault("custody_primary_backup_verify_mismatch"); }
            }
            if (primaryText != intent)
            {
                if (FileExist(m_CustodyPath) && !DeleteFile(m_CustodyPath)) { return this.HCCustodyFault("custody_primary_delete_failed"); }
                if (!CopyFile(temporary, m_CustodyPath)) { return this.HCCustodyFault("custody_primary_copy_failed"); }
            }
            string promotedText;
            if (!this.HCReadCustody(m_CustodyPath, promotedText)) { return false; }
            if (promotedText != intent) { return this.HCCustodyFault("custody_primary_verify_mismatch"); }
            if (!DeleteFile(temporary)) { return this.HCCustodyFault("custody_tmp_delete_failed"); }
            if (FileExist(m_CustodyPath + ".rejected.tmp") && !DeleteFile(m_CustodyPath + ".rejected.tmp")) { return this.HCCustodyFault("custody_witness_cleanup_delete_failed"); }
            HCModuleReadiness.HCUse(GetName(), "custody_tmp_recovered");
            Print("[HC AI] custody_tmp action=recovered reason=valid_nondecreasing_revision runtime=PENDING");
            return true;
        }
        if (next) { reason = "older_revision"; }
        // Preserve invalid raw evidence before retirement. A failed compare
        // keeps the source in place and moves subsequent saves to the backup.
        if (!next)
        {
            if (!this.HCPreserveCustodyFile(temporary)) { return false; }
            if (m_CustodyRetainedSource == temporary)
            {
                m_CustodyKeepTmp = true;
                return true;
            }
        }
        // Retirement leaves the primary/backup untouched, including on crash.
        if (!DeleteFile(temporary)) { return this.HCCustodyFault("custody_tmp_retire_delete_failed"); }
        HCModuleReadiness.HCUse(GetName(), "custody_tmp_retired");
        Print("[HC AI] custody_tmp action=retired reason=" + reason + " runtime=PENDING");
        return true;
    }

    // Unverified raw sources remain in place. Their copy names are durable
    // selection markers, never equality witnesses. A backup then owns the active
    // checkpoint and its usual staged protocol. Reapply the selection on boot;
    // a newer valid original intent is forwarded before using the backup.
    protected bool HCSelectRetainedCustody()
    {
        HCAIPartyCustodyData carry;
        string carryText;
        for (int depth = 0; depth < HC_REJECTED_SLOTS; depth++)
        {
            string primaryReadMarker = m_CustodyPath + ".unverified_read";
            string primaryOversizeMarker = m_CustodyPath + ".unverified_oversize";
            bool retainedPrimary = FileExist(primaryReadMarker);
            if (FileExist(primaryOversizeMarker)) { retainedPrimary = true; }
            string tmpReadMarker = m_CustodyPath + ".tmp.unverified_read";
            string tmpOversizeMarker = m_CustodyPath + ".tmp.unverified_oversize";
            bool retainedTmp = FileExist(tmpReadMarker);
            if (FileExist(tmpOversizeMarker)) { retainedTmp = true; }
            if (!retainedPrimary && !retainedTmp) { return true; }
            if (m_StartedOnce) { return this.HCCustodyFault("custody_in_process_retained_primary"); }
            string backup = m_CustodyPath + ".bak";
            string selectedText = carryText;
            HCAIPartyCustodyData selected = carry;
            string text;
            bool read = HCWorldStore.ReadChecked(m_CustodyPath, text);
            HCAIPartyCustodyData current;
            if (read) { current = this.HCDecodeCustody(text); }
            if (current && current.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = current.NextLease; }
            if (current && (!selected || current.NextLease >= selected.NextLease)) { selected = current; selectedText = text; }
            string intent;
            HCAIPartyCustodyData proposed;
            read = HCWorldStore.ReadChecked(m_CustodyPath + ".tmp", intent);
            if (read) { proposed = this.HCDecodeCustody(intent); }
            if (proposed && (!selected || proposed.NextLease >= selected.NextLease)) { selected = proposed; selectedText = intent; }
            string backupText;
            HCAIPartyCustodyData prior;
            read = HCWorldStore.ReadChecked(backup, backupText);
            if (read) { prior = this.HCDecodeCustody(backupText); }
            if (prior && prior.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = prior.NextLease; }
            string pendingText;
            HCAIPartyCustodyData pending;
            read = HCWorldStore.ReadChecked(backup + ".tmp", pendingText);
            if (read) { pending = this.HCDecodeCustody(pendingText); }
            // Existing backup intent wins ties; it may include newer results.
            if (pending && (!selected || pending.NextLease >= selected.NextLease)) { selected = pending; selectedText = pendingText; }
            if (!selected && !prior)
            {
                if (FileExist(m_CustodyPath)) { return this.HCCustodyFault("custody_retained_no_valid_copy"); }
                Print("[HC " + GetName() + "] custody_retained_no_primary starting_empty=true");
            }
            if (selected && (!prior || selected.NextLease > prior.NextLease))
            {
                // First drain any damaged backup intent with its own raw source
                // preservation policy; never overwrite its only raw bytes.
                if (FileExist(backup + ".tmp") && !pending)
                {
                    string originalPath = m_CustodyPath;
                    m_CustodyPath = backup;
                    m_CustodyKeepTmp = false;
                    bool recovered = this.HCRecoverCustodyTmp();
                    if (!recovered) { m_CustodyPath = originalPath; return false; }
                    if (m_CustodyKeepTmp)
                    {
                        if (!this.HCCleanupCustodyWitness(originalPath)) { return false; }
                        carry = selected;
                        carryText = selectedText;
                        continue;
                    }
                    m_CustodyPath = originalPath;
                }
                FileHandle handle = OpenFile(backup + ".tmp", FileMode.WRITE);
                if (!handle) { return this.HCCustodyFault("custody_retained_open_write_failed"); }
                int offset = 0;
                while (offset < selectedText.Length())
                {
                    int count = selectedText.Length() - offset;
                    if (count > 4096) { count = 4096; }
                    FPrint(handle, selectedText.Substring(offset, count));
                    offset = offset + count;
                }
                CloseFile(handle);
                string verified;
                if (!HCWorldStore.ReadChecked(backup + ".tmp", verified) || verified != selectedText) { return this.HCCustodyFault("custody_retained_verify_failed"); }
            }
            if (!this.HCCleanupCustodyWitness(m_CustodyPath)) { return false; }
            m_CustodyPath = backup;
            m_CustodyKeepTmp = false;
        }
        return true;
    }

    protected bool HCCleanupCustodyWitness(string path)
    {
        string witness = path + ".rejected.tmp";
        if (FileExist(witness) && !DeleteFile(witness)) { return this.HCCustodyFault("custody_witness_cleanup_delete_failed"); }
        return true;
    }

    protected bool HCLoadCustody()
    {
        bool loaded = this.HCLoadCustodyImage();
        string basePath = "$profile:HollowCountry/ai-custody.json";
        int depth = (m_CustodyPath.Length() - basePath.Length()) / 4;
        Print("[HC " + GetName() + "] custody_load path=" + m_CustodyPath + " relocation_depth=" + depth.ToString() + " loaded=" + loaded.ToString());
        return loaded;
    }

    protected bool HCLoadCustodyImage()
    {
        // Retain the process watermark across failed loads and module toggles.
        m_CustodyRetryRead = false;
        m_CustodyLoadFault = "custody_invalid_no_backup";
        m_Custody = new HCAIPartyCustodyData();
        m_CustodyText = "";
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) { return this.HCCustodyFault("custody_directory_create_failed"); }
        m_CustodyKeepTmp = false;
        if (!this.HCSelectRetainedCustody()) { return false; }
        if (FileExist(m_CustodyPath + ".tmp") && !this.HCRecoverCustodyTmp()) { return false; }
        string text;
        HCAIPartyCustodyData loaded;
        bool primaryExists = FileExist(m_CustodyPath);
        if (primaryExists)
        {
            if (!this.HCReadCustody(m_CustodyPath, text))
            {
                if (m_CustodyRetryRead || m_StartedOnce) { return false; }
                if (!this.HCPreserveCustodyFile(m_CustodyPath)) { return false; }
            }
            loaded = this.HCDecodeCustody(text);
            if (loaded && loaded.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = loaded.NextLease; }
        }
        if (!loaded)
        {
            // In-process bodies may still be alive: never roll back to backup.
            if (m_StartedOnce) { return this.HCCustodyFault("custody_in_process_invalid_primary"); }
            string backup = m_CustodyPath + ".bak";
            if (FileExist(backup))
            {
                string backupText;
                if (!this.HCReadCustody(backup, backupText)) { return false; }
                HCAIPartyCustodyData prior = this.HCDecodeCustody(backupText);
                if (!prior) { return this.HCCustodyFault("custody_backup_invalid"); }
                // Rollback may lose a checkpoint, but never reissue any lease
                // proposed in this process, even after its last save request.
                if (prior.NextLease < m_CustodyNextLeaseSeen)
                {
                    Print("[HC " + GetName() + "] custody_backup_older_than_watermark action=raise_next_lease");
                    prior.NextLease = m_CustodyNextLeaseSeen;
                    prior.SchemaVersion = 2;
                    string error;
                    if (!JsonFileLoader<HCAIPartyCustodyData>.MakeData(prior, backupText, error)) { return this.HCCustodyFault("custody_backup_encode_failed"); }
                }
                if (primaryExists && !this.HCPreserveCustodyFile(m_CustodyPath)) { return false; }
                if (m_CustodyRetainedSource == m_CustodyPath || m_CustodyKeepTmp)
                {
                    // Keep the unverifiable source untouched. The already valid
                    // backup owns the same schema and staged-save protocol.
                    if (!this.HCSelectRetainedCustody()) { return false; }
                    if (FileExist(m_CustodyPath + ".tmp"))
                    {
                        if (!this.HCRecoverCustodyTmp()) { return false; }
                        if (!this.HCReadCustody(m_CustodyPath, backupText)) { return false; }
                        prior = this.HCDecodeCustody(backupText);
                        if (!prior) { return this.HCCustodyFault("custody_post_restore_verify_failed"); }
                    }
                    // Watermark raising is a new pending checkpoint, never
                    // pretend its encoding is already the disk prior image.
                    if (!this.HCReadCustody(m_CustodyPath, text)) { return false; }
                    loaded = this.HCDecodeCustody(text);
                    if (!loaded) { return this.HCCustodyFault("custody_post_restore_verify_failed"); }
                    if (loaded.NextLease < m_CustodyNextLeaseSeen)
                    {
                        loaded.NextLease = m_CustodyNextLeaseSeen;
                        loaded.SchemaVersion = 2;
                    }
                }
                else
                {
                    // Backup never writes directly over primary. A torn copy here
                    // is retired on next load; a verified intent uses normal recovery.
                    string temporary = m_CustodyPath + ".tmp";
                    string originalBackup;
                    if (!this.HCReadCustody(backup, originalBackup)) { return false; }
                    if (originalBackup == backupText)
                    {
                        if (!CopyFile(backup, temporary)) { return this.HCCustodyFault("custody_backup_copy_failed"); }
                    }
                    else
                    {
                        FileHandle raised = OpenFile(temporary, FileMode.WRITE);
                        if (!raised) { return this.HCCustodyFault("custody_backup_open_write_failed"); }
                        // Native FPrint string transfer cap: boot-only bounded chunks.
                        int offset = 0;
                        while (offset < backupText.Length())
                        {
                            int length = backupText.Length() - offset;
                            if (length > 4096) { length = 4096; }
                            FPrint(raised, backupText.Substring(offset, length));
                            offset = offset + length;
                        }
                        CloseFile(raised);
                    }
                    string temporaryText;
                    if (!this.HCReadCustody(temporary, temporaryText)) { return false; }
                    if (temporaryText != backupText || !this.HCDecodeCustody(temporaryText)) { return this.HCCustodyFault("custody_backup_verify_mismatch"); }
                    if (!this.HCRecoverCustodyTmp()) { return false; }
                    if (!this.HCReadCustody(m_CustodyPath, text)) { return false; }
                    loaded = this.HCDecodeCustody(text);
                    if (!loaded) { return this.HCCustodyFault("custody_post_restore_verify_failed"); }
                }
            }
            else
            {
                if (primaryExists || m_Custody.NextLease < m_CustodyNextLeaseSeen)
                {
                    Print("[HC " + GetName() + "] custody_invalid_no_backup");
                    return false;
                }
                if (m_CustodyKeepTmp)
                {
                    if (!this.HCCleanupCustodyWitness(m_CustodyPath)) { return false; }
                    Print("[HC " + GetName() + "] custody_retained_no_primary starting_empty=true");
                    m_CustodyPath += ".bak";
                }
                loaded = m_Custody;
            }
        }
        if (loaded && m_CustodyKeepTmp && m_CustodyRetainedSource == m_CustodyPath + ".tmp")
        {
            if (!this.HCSelectRetainedCustody()) { return false; }
            if (FileExist(m_CustodyPath + ".tmp") && !this.HCRecoverCustodyTmp()) { return false; }
            if (!this.HCReadCustody(m_CustodyPath, text)) { return false; }
            loaded = this.HCDecodeCustody(text);
            if (!loaded) { return this.HCCustodyFault("custody_retained_backup_verify_failed"); }
        }
        if (loaded.NextLease < m_CustodyNextLeaseSeen) { return this.HCCustodyFault("custody_primary_older_than_watermark"); }
        // A valid primary no longer needs a stale preservation intent.
        if (FileExist(m_CustodyPath + ".rejected.tmp") && !DeleteFile(m_CustodyPath + ".rejected.tmp")) { return this.HCCustodyFault("custody_witness_cleanup_delete_failed"); }
        m_Custody = loaded;
        m_CustodyText = text;
        m_CustodyRevision = loaded.NextLease;
        m_CustodyCommitted = m_CustodyRevision;
        if (m_CustodyCommitted > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = m_CustodyCommitted; }
        m_CustodyLoadFault = "";
        if (m_CustodyReadRetries > 0)
        {
            Print("[HC " + GetName() + "] custody_read_recovered retry=" + m_CustodyReadRetries.ToString());
            m_CustodyReadRetries = 0;
        }
        return true;
    }

    // Expansion transient groups use Persist=false. There is no surviving body
    // after a process restart, and no trustworthy casualty observation either.
    // Cargo never left its owner store here: release custody without spawning,
    // refunding, copying inventory or applying a guessed world outcome.
    protected void HCRestoreCustody()
    {
        int recovered = 0;
        foreach (HCAIPartyCustodyRow restored : m_Custody.Rows)
        {
            if (restored.Outcome == "CLAIMED" || restored.Outcome == "QUARANTINED")
            {
                restored.Outcome = "FINISHED_UNKNOWN";
                restored.Materialized = false;
                restored.Survivors = 0;
                HCAIBudget.Release(restored.LeaseId);
                recovered++;
                Print("[HC AI] custody restore lease=" + restored.LeaseId + " outcome=FINISHED_UNKNOWN runtime=PENDING");
            }
            else { HCAIBudget.Release(restored.LeaseId); }
        }
        if (recovered > 0 || m_Custody.SchemaVersion == 1)
        {
            m_Custody.SchemaVersion = 2;
            this.HCSaveCustody();
        }
        Print("[HC AI] custody restore finished_unknown=" + recovered.ToString() + " runtime=PENDING");
    }

    protected bool HCValidCustody(HCAIPartyCustodyData data)
    {
        if (!data || (data.SchemaVersion != 1 && data.SchemaVersion != 2) || data.NextLease < 1 || !data.Rows || data.Rows.Count() > HCAIPartyCustody.MAX_ROWS) { return false; }
        map<string, bool> partyIds = new map<string, bool>;
        map<string, bool> cargoIds = new map<string, bool>;
        map<string, bool> leaseIds = new map<string, bool>;
        foreach (HCAIPartyCustodyRow row : data.Rows)
        {
            if (!row || row.ActorCap < 1 || row.ActorCap > HCAILimits.SIZE_CEILING || !HCWorldLimits.Token(row.LeaseId)) { return false; }
            if (!HCAIPartyIdentity.HCCreate(row.PartyId, row.CampId, row.HomeId, row.RouteId, row.CargoId, row.Generation)) { return false; }
            if (row.Outcome != "CLAIMED" && row.Outcome != "FINISHED" && row.Outcome != "FINISHED_UNKNOWN" && row.Outcome != "QUARANTINED") { return false; }
            if (row.Survivors < 0 || row.Survivors > row.ActorCap || (!row.Materialized && row.Survivors != 0)) { return false; }
            if ((row.Outcome == "CLAIMED" || row.Outcome == "FINISHED_UNKNOWN") && (row.Materialized || row.Survivors != 0)) { return false; }
            if (partyIds.Contains(row.PartyId) || cargoIds.Contains(row.CargoId) || leaseIds.Contains(row.LeaseId)) { return false; }
            partyIds.Set(row.PartyId, true);
            cargoIds.Set(row.CargoId, true);
            leaseIds.Set(row.LeaseId, true);
        }
        return true;
    }

    // Queue a durable continuation. New claims remain private until their
    // exact revision commits; callbacks may coalesce into the next checkpoint.
    // No disk calls are made by Next/Result/Expire.
    protected bool HCSaveCustody()
    {
        if (!m_CustodyReady || !this.HCValidCustody(m_Custody) || m_Custody.NextLease >= 2147483647) { return this.HCCustodySaveFailed(); }
        m_Custody.NextLease++;
        if (m_Custody.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = m_Custody.NextLease; }
        m_CustodyRevision = m_Custody.NextLease;
        m_CustodyJob.HCDirty = true;
        m_CustodyJob.HCUrgent = true;
        return true;
    }

    protected bool HCCustodySaveFailed()
    {
        m_CustodyReady = false;
        HCAIBudget.Block();
        if (!m_CustodyFailurePrinted)
        {
            m_CustodyFailurePrinted = true;
            Print("[HC " + GetName() + "] CUSTODY SAVE FAILED path=" + m_CustodyPath + "; ALL NEW AI BLOCKED; inspect active path and intent before restart runtime=PENDING");
        }
        return false;
    }

    bool HCCustodyCheckpointPending() { return m_CustodyCommitted != m_CustodyRevision; }

    // Routine scheduling owns its grant; only HCPumpCustodyFallback needs
    // the local guard. Flushes must never count no-op STEP_MORE as disk stages.
    int HCStepCustody()
    {
        if (!m_CustodyReady) { return m_CustodyImage.HCAbort(); }
        int result = this.HCWriteCustody();
        if (result == HCSaveJob.STEP_FAILED)
        {
            this.HCCustodySaveFailed();
            return m_CustodyImage.HCAbort();
        }
        return result;
    }

    protected int HCWriteCustody()
    {
        if (m_CustodyStage == 0)
        {
            HCSaveJob.HCOperation = "custody_encode";
            string error;
            if (!this.HCValidCustody(m_Custody) || !JsonFileLoader<HCAIPartyCustodyData>.MakeData(m_Custody, m_CustodySnapshot, error)) { return HCSaveJob.STEP_FAILED; }
            m_CustodySnapshotRevision = m_CustodyRevision;
            m_CustodyStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (m_CustodyStage == 1)
        {
            // Fresh-store absence must be checked explicitly: the shared prior
            // check with an empty expected image permits an existing primary.
            m_CustodyStage = 2;
            if (m_CustodyText == "")
            {
                HCSaveJob.HCOperation = "custody_check_fresh";
                if (FileExist(m_CustodyPath)) { return HCSaveJob.STEP_FAILED; }
                return HCSaveJob.STEP_MORE;
            }
        }
        if (m_CustodyStage == 2)
        {
            // Begin checks for an existing intent; yield before the first file
            // stage. Expected prior preserves external-edit refusal.
            HCSaveJob.HCOperation = "custody_begin";
            if (!m_CustodyImage.Begin(m_CustodyPath, m_CustodySnapshot, HCWorldStore.MAX_BYTES, true, true, m_CustodyText)) { return HCSaveJob.STEP_FAILED; }
            m_CustodyStage = 3;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_CustodyImage.HCStepImage();
        if (result != HCSaveJob.STEP_DONE) { return result; }
        m_CustodyText = m_CustodySnapshot;
        m_CustodyCommitted = m_CustodySnapshotRevision;
        if (m_CustodyCommitted > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = m_CustodyCommitted; }
        m_CustodySnapshot = "";
        m_CustodyStage = 0;
        return HCSaveJob.STEP_DONE;
    }

    protected bool HCCustodyAllows(HCAIPartyIdentity identity)
    {
        if (!m_CustodyReady || !m_Custody || !m_Custody.Rows || !identity) { return false; }
        bool evictable = false;
        foreach (HCAIPartyCustodyRow reservedRow : m_Custody.Rows)
        {
            if (reservedRow.Outcome == "FINISHED" || reservedRow.Outcome == "FINISHED_UNKNOWN") { evictable = true; continue; }
            if (reservedRow.PartyId == identity.HCPartyId() || reservedRow.CargoId == identity.HCCargoId())
            {
                if (m_DuplicateRefused < 2147483647) { m_DuplicateRefused++; }
                return false;
            }
        }
        return evictable || m_Custody.Rows.Count() < HCAIPartyCustody.MAX_ROWS;
    }

    // Only unresolved in-process custody and quarantines charge debt. Completed
    // history is bounded and evictable; active leases are already charged below.
    protected int HCCustodyDebt(bool actorUnits)
    {
        int debt = 0;
        if (!m_Custody || !m_Custody.Rows) { return 0; }
        map<string, bool> heldLeases = new map<string, bool>;
        foreach (HCWorldProposalLease activeLease : m_Active)
        {
            if (activeLease && activeLease.Proposal) { heldLeases.Set(activeLease.Proposal.Id, true); }
        }
        foreach (HCAIPartyCustodyRow debtRow : m_Custody.Rows)
        {
            if (debtRow.Outcome == "FINISHED" || debtRow.Outcome == "FINISHED_UNKNOWN") { continue; }
            if (heldLeases.Contains(debtRow.LeaseId)) { continue; }
            if (actorUnits) { debt += debtRow.ActorCap; }
            else { debt++; }
        }
        return debt;
    }

    protected bool HCClaimFits()
    {
        int actors = this.HCCustodyDebt(true);
        foreach (HCWorldProposalLease capacityLease : m_Active) { actors += capacityLease.Proposal.ActorCap; }
        return actors <= HCAILimits.Get().MaxLiveAI && m_Active.Count() + this.HCCustodyDebt(false) <= HCAILimits.Get().MaxMaterialized;
    }

    // Compatibility queries for custody reports. HCAIBudget owns admission for
    // every provider; startup restores this debt there before new proposals.
    // Missing/unreadable custody blocks new bodies, never grants room.
    static int HCUnresolvedActors()
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_CustodyReady) { return HCAILimits.Get().MaxLiveAI; }
        return s_Instance.HCCustodyDebt(true);
    }

    static int HCUnresolvedLeases()
    {
        if (!s_Instance || !s_Instance.m_Running || !s_Instance.m_CustodyReady) { return HCAILimits.Get().MaxMaterialized; }
        return s_Instance.HCCustodyDebt(false);
    }

    protected bool HCClaim(HCWorldProposalLease candidate)
    {
        if (!candidate || !candidate.Proposal || candidate.Claimed || candidate.Finished || !m_CustodyReady) { return false; }
        if (candidate.CustodyRevision > 0)
        {
            if (m_CustodyCommitted < candidate.CustodyRevision) { return false; }
            candidate.Claimed = true;
            m_Activity.HCHit("claims");
            return true;
        }
        if (this.HCCustodyCheckpointPending() || !this.HCCustodyAllows(candidate.Proposal.Identity)) { return false; }
        if (!this.HCClaimFits()) { return false; }
        HCAIPartyCustodyRow row = HCAIPartyCustody.HCReservation(candidate.Proposal.Identity, candidate.Proposal.Id, candidate.Proposal.ActorCap);
        if (!row) { return false; }
        int priorIndex = m_Custody.Rows.Count() - 1;
        while (priorIndex >= 0)
        {
            HCAIPartyCustodyRow prior = m_Custody.Rows[priorIndex];
            if ((prior.Outcome == "FINISHED" || prior.Outcome == "FINISHED_UNKNOWN") && (prior.PartyId == row.PartyId || prior.CargoId == row.CargoId)) { m_Custody.Rows.RemoveOrdered(priorIndex); }
            priorIndex -= 1;
        }
        int evictIndex = 0;
        while (m_Custody.Rows.Count() >= HCAIPartyCustody.MAX_ROWS && evictIndex < m_Custody.Rows.Count())
        {
            HCAIPartyCustodyRow old = m_Custody.Rows[evictIndex];
            if (old.Outcome == "FINISHED" || old.Outcome == "FINISHED_UNKNOWN") { m_Custody.Rows.RemoveOrdered(evictIndex); }
            else { evictIndex++; }
        }
        if (m_Custody.Rows.Count() >= HCAIPartyCustody.MAX_ROWS) { return false; }
        m_Custody.Rows.Insert(row);
        if (!this.HCSaveCustody()) { return false; }
        candidate.CustodyRevision = m_CustodyRevision;
        return false; // provider retries Next after the durable checkpoint
    }

    // Wave 2 director seam: immutable identity for the exact current lease.
    // Never derive an identity from the place position or provider body count.
    static HCAIPartyIdentity HCIdentity(string leaseId)
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        foreach (HCWorldProposalLease identityLease : s_Instance.m_Active)
        {
            if (identityLease.Proposal.Id == leaseId && identityLease.Claimed) { return identityLease.Proposal.Identity; }
        }
        return null;
    }

    // w29-debugmap #194: read-only debug seam. Only a running module is visible.
    // These getters never call Next/Expire/HCClaim/Resolve, never claim or finish a
    // lease, and return detached rows. Runtime acceptance pending.
    static HCWorldMaterializer HCDebugGet()
    {
        if (!s_Instance || !s_Instance.m_Running) { return null; }
        return s_Instance;
    }

    int HCDebugProposalCount() { return m_Active.Count(); }

    HCDebugProposalRow HCDebugProposal(int wanted)
    {
        if (wanted < 0 || wanted >= m_Active.Count()) { return null; }
        HCWorldProposalLease lease = m_Active[wanted];
        if (!lease || !lease.Proposal) { return null; }
        HCDebugProposalRow row = new HCDebugProposalRow;
        row.Id = lease.Proposal.Id;
        row.PlaceId = lease.Proposal.PlaceId;
        row.Kind = lease.Proposal.Kind;
        row.Position = lease.Proposal.Position;
        row.ActorCap = lease.Proposal.ActorCap;
        if (lease.Claimed) { row.State = "claimed"; }
        if (lease.Finished) { row.State = "finished"; }
        if (lease.Finished && lease.Materialized) { row.State = "materialized"; }
        row.AgeSeconds = Math.Floor(m_Clock - lease.Created);
        return row;
    }

    static bool CanPropose(int active, int actors, int actorCap)
    {
        return active >= 0 && active < HCAILimits.Get().MaxMaterialized && actors >= 0 && actorCap >= 1 && actorCap <= HCAILimits.SIZE_CEILING && actors <= HCAILimits.Get().MaxLiveAI - actorCap;
    }

    static bool NoProvider(bool claimed, float age)
    {
        return !claimed && age >= HCWorldMaterializer.PROVIDER_TIMEOUT;
    }

    // Only confirmed materialized casualties debit finite faction strength.
    // Refusals/timeouts preserve strength and leave a bounded place trace.
    static bool FoldBack(HCWorldModule world, HCWorldProposal proposal, bool materialized, int survivors)
    {
        if (!world || !proposal || survivors < 0 || survivors > proposal.ActorCap) { return false; }
        if (!materialized)
        {
            if (survivors != 0) { return false; }
            if (proposal.Kind == "HOLDOUT") { return world.AddFact("holdout_traces", proposal.PlaceId, 0); }
            return world.AddFact("party_passed", proposal.PlaceId, 0);
        }
        return world.AddFact(proposal.FactionId + "_survivors_" + survivors.ToString() + "_of_" + proposal.ActorCap.ToString(), proposal.PlaceId, 1);
    }

    protected void Resolve(int leaseIndex, bool materialized, int survivors)
    {
        HCWorldProposalLease lease = m_Active[leaseIndex];
        HCWorldModule world = HCWorldModule.Get();
        // The provider has confirmed body absence. Even if a world write fails,
        // release the body budget exactly once; never retry a partial debit.
        if (lease.OutcomeApplied) { return; }
        lease.OutcomeApplied = true;
        HCAIBudget.Release(lease.Proposal.Id);
        if (lease.RowIndex >= 0 && lease.RowIndex < m_Cooldowns.Count()) { m_Cooldowns[lease.RowIndex] = m_Clock + ROW_COOLDOWN; }
        m_Active.RemoveOrdered(leaseIndex);
        if (m_Stopping) { m_StopUnavailable++; }
        if (!world || !world.GetFaction(lease.Proposal.FactionId)) { Print("[HC AI] custody fold-back unavailable world/faction runtime=PENDING"); return; }
        if (!HCWorldMaterializer.FoldBack(world, lease.Proposal, materialized, survivors)) { Print("[HC AI] custody fold-back fact failed runtime=PENDING"); return; }
        if (materialized)
        {
            if (!world.AdjustStrength(lease.Proposal.FactionId, survivors - lease.Proposal.ActorCap)) { Print("[HC AI] custody fold-back strength failed runtime=PENDING"); return; }
            m_Materialized++;
            m_Activity.HCHit("materialized");
            if (lease.Fixture) { HCModuleReadiness.HCUseFixture("Materializer", "actors_materialized"); }
            else { HCModuleReadiness.HCUse("Materializer", "actors_materialized"); }
            string outcome = "[HC AI] materializer outcome=folded-back";
            if (lease.Fixture) { outcome += " fixture=1"; }
            Print("" + outcome);
        }
        else { m_Traces++; m_Activity.HCHit("traces"); }
        if (m_Stopping) { m_StopUnavailable--; m_StopFolded++; }
    }

    protected void Expire()
    {
        int leaseIndex = m_Active.Count() - 1;
        while (leaseIndex >= 0)
        {
            if (m_Active[leaseIndex].Finished)
            {
                // Result side effects retain the old durability barrier too:
                // only fold back world state/release actors after this result
                // is committed, even when newer callbacks are still queued.
                if (m_CustodyReady && m_CustodyCommitted >= m_Active[leaseIndex].ResultRevision)
                {
                    this.Resolve(leaseIndex, m_Active[leaseIndex].Materialized, m_Active[leaseIndex].Survivors);
                }
            }
            else if (m_Active[leaseIndex].CustodyRevision > 0 && !m_Active[leaseIndex].Claimed)
            {
                // A pending claim cannot time out before its image commits.
                // After commit, cancel through the normal result path rather
                // than leaving an orphan CLAIMED row when no provider polls.
                HCWorldProposalLease pending = m_Active[leaseIndex];
                if (m_CustodyReady && m_CustodyCommitted >= pending.CustodyRevision && HCWorldMaterializer.NoProvider(false, m_Clock - pending.Created))
                {
                    pending.Claimed = true;
                    this.HCRecordResult(pending.Proposal.Id, false, 0, false);
                }
            }
            else
            {
                if (HCWorldMaterializer.NoProvider(m_Active[leaseIndex].Claimed, m_Clock - m_Active[leaseIndex].Created)) { m_Activity.HCRefuse("provider_timeout"); this.Resolve(leaseIndex, false, 0); }
            }
            leaseIndex -= 1;
        }
    }

    // Existing naturally offered, short (<=2 actors), unclaimed lease only.
    // No new Offer/Result: Next still performs the normal durable claim.
    bool HCFixtureProposal(vector pos, bool apply, out string reason)
    {
        reason = "materializer-custody-or-owner-unavailable";
        if (!m_Running || !m_CustodyReady) { return false; }
        int selected = -1;
        float best = 0;
        m_WorkBudget.HCReset(m_Active.Count());
        for (int i = 0; i < m_Active.Count(); i++)
        {
            if (!m_WorkBudget.HCContinue()) { reason = "materializer-selection-budget"; return false; }
            HCWorldProposalLease lease = m_Active[i];
            if (!lease || !lease.Proposal || lease.Claimed || lease.Finished || lease.OutcomeApplied || lease.Fixture) { continue; }
            if (lease.Proposal.ActorCap < 1 || lease.Proposal.ActorCap > 2 || HCWorldMaterializer.NoProvider(false, m_Clock - lease.Created)) { continue; }
            if (!HCCustodyAllows(lease.Proposal.Identity)) { continue; }
            float distance = vector.DistanceSq(pos, lease.Proposal.Position);
            if (selected < 0 || distance < best) { best = distance; selected = i; }
        }
        reason = "no-short-unclaimed-offered-proposal";
        if (selected < 0) { return false; }
        if (apply)
        {
            HCWorldProposalLease chosen = m_Active[selected];
            m_Active[selected] = m_Active[0];
            m_Active[0] = chosen;
            chosen.Fixture = true;
            chosen.Proposal.Fixture = true;
        }
        reason = "offered-proposal-prioritized-normal-next-claim";
        return true;
    }

    // Hands a detached place-only DTO to at most one provider. Claiming keeps
    // the slot/body reservation until Result; polling alone cannot release it.
    static bool Next(out HCWorldProposal p)
    {
        p = null;
        if (!s_Instance || !s_Instance.m_Running || !HCWorldModule.Get()) { return false; }
        s_Instance.Expire();
        foreach (HCWorldProposalLease candidate : s_Instance.m_Active)
        {
            if (candidate.Claimed || candidate.Finished) { continue; }
            HCWorldProposal copy = new HCWorldProposal;
            copy.Id = candidate.Proposal.Id;
            copy.FactionId = candidate.Proposal.FactionId;
            copy.PlaceId = candidate.Proposal.PlaceId;
            copy.Position = candidate.Proposal.Position;
            copy.ActorCap = candidate.Proposal.ActorCap;
            copy.Kind = candidate.Proposal.Kind;
            copy.Identity = candidate.Proposal.Identity;
            copy.Fixture = candidate.Fixture;
            if (!s_Instance.HCClaim(candidate)) { continue; }
            p = copy;
            return true;
        }
        return false;
    }

    // Provider contract: call only after all owned actors have died/despawned,
    // with the number that survived. Refusal calls Result(id, false, 0).
    static void Result(string id, bool materialized, int survivors)
    {
        if (!s_Instance || !s_Instance.m_Running) { return; }
        s_Instance.HCRecordResult(id, materialized, survivors);
    }

    protected void HCRecordResult(string id, bool materialized, int survivors, bool resolveNow = true)
    {
        if (!m_CustodyReady || !m_Custody) { return; }
        HCAIPartyCustodyRow resultRow;
        foreach (HCAIPartyCustodyRow journalRow : m_Custody.Rows)
        {
            if (journalRow.LeaseId == id) { resultRow = journalRow; break; }
        }
        if (!resultRow) { HCAIBudget.Release(id); return; }
        if (resultRow.Outcome == "FINISHED_UNKNOWN") { HCAIBudget.Release(id); return; }
        if (resultRow.Outcome == "QUARANTINED") { return; }
        int disposition = HCAIPartyCustody.HCFinish(resultRow, materialized, survivors);
        if (disposition == 2) { HCAIBudget.Release(id); return; }
        if (disposition == 0) { HCAIBudget.Restore(id, resultRow.ActorCap); }
        if (disposition == 1 && !materialized)
        {
            // A clean refusal never owned a body or cargo; release its claim.
            m_Custody.Rows.RemoveOrdered(m_Custody.Rows.Find(resultRow));
        }
        if (!this.HCSaveCustody()) { return; }
        if (disposition == 0)
        {
            // Contradictory callbacks keep any active reservation quarantined.
            foreach (HCWorldProposalLease uncertain : m_Active)
            {
                if (uncertain.Proposal.Id == id) { uncertain.OutcomeApplied = true; }
            }
            return;
        }
        foreach (HCWorldProposalLease completed : m_Active)
        {
            if (completed.Proposal.Id != id || !completed.Claimed || completed.Finished) { continue; }
            completed.ResultRevision = m_CustodyRevision;
            completed.Finished = true;
            completed.Materialized = materialized;
            completed.Survivors = survivors;
            if (resolveNow) { this.Expire(); }
            return;
        }
        HCAIBudget.Release(id);
    }

    static void HCTypedResult(HCAIPartyResult result)
    {
        if (!s_Instance || !s_Instance.m_Running || !result) { return; }
        s_Instance.HCRecordTypedResult(result);
    }

    protected void HCRecordTypedResult(HCAIPartyResult result)
    {
        if (!result || !m_CustodyReady || !m_Custody) { return; }
        HCAIPartyIdentity observed = result.HCIdentity();
        if (!HCAIPartyIdentity.HCValid(observed)) { return; }
        foreach (HCAIPartyCustodyRow typedRow : m_Custody.Rows)
        {
            if (typedRow.LeaseId != result.HCLeaseId()) { continue; }
            if (typedRow.PartyId != observed.HCPartyId() || typedRow.CampId != observed.HCCampId() || typedRow.HomeId != observed.HCHomeId() || typedRow.RouteId != observed.HCRouteId() || typedRow.CargoId != observed.HCCargoId() || typedRow.Generation != observed.HCGeneration())
            {
                // A mismatched identity is not a second population/result.
                // Reuse invalid-result quarantine without applying casualties.
                this.HCRecordResult(result.HCLeaseId(), true, -1);
                return;
            }
            this.HCRecordResult(result.HCLeaseId(), result.HCMaterialized(), result.HCSurvivors());
            return;
        }
        // Finished history may already have been evicted. Unique lease IDs
        // make this release harmless to a newer offer of the same party.
        HCAIBudget.Release(result.HCLeaseId());
    }

    // Squared horizontal distance: conservative, allocation-free, no sqrt
    // inside the bounded observer loop. Provider sight/member gates still run.
    static bool HCSpawnDistanceAllowed(float distanceSquared)
    {
        float minimum = HCPerceptionRing.HCSpawnMin();
        return distanceSquared >= minimum * minimum;
    }

    protected void InterestRing()
    {
        m_Activity.HCHit("rings");
        HCWorldModule world = HCWorldModule.Get();
        if (!world || !GetGame() || !m_CustodyReady) { m_Activity.HCRefuse("prerequisite"); return; }
        int unresolvedLeases = this.HCCustodyDebt(false);
        if (m_Active.Count() + unresolvedLeases >= HCAILimits.Get().MaxMaterialized) { m_Activity.HCRefuse("cap"); return; }
        array<Man> players = HCPerfPlayers.HCGet();
        int playerCount = players.Count();
        if (playerCount < 1) { m_Activity.HCRefuse("no_players"); return; }
        int playerWork = playerCount;
        if (playerWork > MAX_PLAYERS) { playerWork = MAX_PLAYERS; }
        array<vector> interests = new array<vector>;
        for (int playerOffset = 0; playerOffset < playerWork; playerOffset++)
        {
            if (m_PlayerCursor >= playerCount) { m_PlayerCursor = 0; }
            Man observer = players[m_PlayerCursor];
            m_PlayerCursor++;
            if (!observer || !observer.GetIdentity() || !observer.IsAlive()) { continue; }
            vector interest = observer.GetPosition();
            if (HCWorldLimits.Position(interest)) { interests.Insert(interest); }
        }
        float interestMaximum = HCPerceptionRing.HCSpawnMax();
        float interestMaximumSquared = interestMaximum * interestMaximum;
        // Player positions never leave this function or enter proposal DTOs.
        // Native EnScript.c:877/902/917: per-ring hash indexes.
        map<string, bool> activeRows = new map<string, bool>;
        map<string, int> activeFactions = new map<string, int>;
        int reservedActors = this.HCCustodyDebt(true);
        foreach (HCWorldProposalLease reserved : m_Active)
        {
            reservedActors += reserved.Proposal.ActorCap;
            activeRows.Set(reserved.RowId, true);
            int priorActors;
            if (!activeFactions.Find(reserved.Proposal.FactionId, priorActors)) { priorActors = 0; }
            activeFactions.Set(reserved.Proposal.FactionId, priorActors + reserved.Proposal.ActorCap);
        }
        int totalRows = HCAILimits.Get().MaxHoldouts + HCAILimits.Get().MaxParties;
        m_WorkBudget.HCReset(4);
        m_UnitBudget.HCReset(4);
        for (int rowWork = 0; rowWork < ROWS_PER_RING; rowWork++)
        {
            if (m_Active.Count() + unresolvedLeases >= HCAILimits.Get().MaxMaterialized) { m_Activity.HCRefuse("cap"); return; }
            if (!m_WorkBudget.HCContinue()) { m_Activity.HCRefuse("budget"); m_WorkBudget.HCDeferred(GetName(), ROWS_PER_RING - rowWork); return; }
            if (!m_UnitBudget.HCTake(1)) { m_Activity.HCRefuse("budget"); m_WorkBudget.HCDeferred(GetName(), ROWS_PER_RING - rowWork); return; }
            if (m_RowCursor >= totalRows) { m_RowCursor = 0; }
            int rowIndex = m_RowCursor;
            m_RowCursor++;
            m_Activity.HCHit("rows");
            if (m_Cooldowns[rowIndex] > m_Clock) { m_Activity.HCHit("cooldown"); continue; }
            HCWorldProposal row = world.MaterializerRow(rowIndex);
            if (!row) { m_Activity.HCRefuse("row_unavailable"); continue; }
            if (!this.HCCustodyAllows(row.Identity)) { m_Activity.HCRefuse("custody"); continue; }
            bool nearby = false;
            bool insideRing = false;
            foreach (vector point : interests)
            {
                float dx = point[0] - row.Position[0];
                float dz = point[2] - row.Position[2];
                float playerDistanceSquared = dx * dx + dz * dz;
                if (!HCWorldMaterializer.HCSpawnDistanceAllowed(playerDistanceSquared)) { insideRing = true; break; }
                if (playerDistanceSquared <= interestMaximumSquared) { nearby = true; }
            }
            if (!nearby || insideRing) { m_Activity.HCRefuse("ring"); continue; }
            int factionActors;
            if (!activeFactions.Find(row.FactionId, factionActors)) { factionActors = 0; }
            bool duplicate = activeRows.Contains(row.Id);
            HCWorldFaction faction = world.GetFaction(row.FactionId);
            if (!faction || duplicate || row.ActorCap + factionActors > faction.Strength) { m_Activity.HCRefuse("faction"); continue; }
            if (!CanPropose(m_Active.Count() + unresolvedLeases, reservedActors, row.ActorCap)) { m_Activity.HCRefuse("population"); continue; }
            HCWorldProposalLease lease = new HCWorldProposalLease;
            lease.RowId = row.Id;
            lease.RowIndex = rowIndex;
            // Persisted sequence makes callbacks unique across retries/restarts,
            // independent of the (up to 96-character) stable party identity.
            if (m_Custody.NextLease >= 2147483647) { m_Activity.HCRefuse("sequence"); return; }
            row.Id = "lease:" + m_Custody.NextLease.ToString();
            m_Custody.NextLease++;
            if (m_Custody.NextLease > m_CustodyNextLeaseSeen) { m_CustodyNextLeaseSeen = m_Custody.NextLease; }
            if (!HCAIBudget.TryReserve(row.Id, row.ActorCap)) { m_Activity.HCRefuse("reserve"); continue; }
            lease.Proposal = row;
            lease.Created = m_Clock;
            m_Active.Insert(lease);
            activeRows.Set(lease.RowId, true);
            activeFactions.Set(row.FactionId, factionActors + row.ActorCap);
            reservedActors += row.ActorCap;
            m_Cooldowns[rowIndex] = m_Clock + ROW_COOLDOWN;
            m_Proposals++;
            m_Activity.HCHit("proposals");
        }
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCWorldMaterializer);
    }
}
