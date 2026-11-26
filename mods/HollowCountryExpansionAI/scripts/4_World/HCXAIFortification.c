// HC-17/#304. One bounded fortification candidate per existing adapter tick.
// Reservations are durable BEFORE world creation. Native CE owns the resulting
// world objects; reservations are never recycled after raids, decay or crashes.
// An interrupted creation can leave a spent slot; it is reported, never replayed
// on restart (world persistence and JSON cannot form an atomic transaction).
class HCXAIFortificationState
{
    int Version = 1;
    string WorldName;
    ref array<string> Reserved = new array<string>;
}
class HCXAIFortificationSite
{
    string Id;
    vector Anchor;
    int PartIndex;
    int Attempt;
}
class HCXAIFortification
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    static const int SITE_CAP = 32;
    static const int SITE_PARTS = 3;
    static const int GLOBAL_CAP = 96;
    static const string STORE = "$profile:HollowCountry/ai-fortifications.json";
    protected static ref HCXAIFortification s_Active;
    protected ref HCXAIFortificationState m_State;
    protected ref array<ref HCXAIFortificationSite> m_Queue = new array<ref HCXAIFortificationSite>;
    protected ref array<string> m_Seen = new array<string>;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected bool m_Fault;
    protected ref HCXAIFortificationSaveJob m_SaveJob;
    protected ref HCV2ThreatStore<HCXAIFortificationState> m_Writer = new HCV2ThreatStore<HCXAIFortificationState>;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected int m_CommittedRevision;
    protected ref HCXAIFortificationSite m_PendingSite;
    protected vector m_PendingAt;
    protected float m_PendingBearing;
    protected string m_PendingKind;
    protected vector m_PendingCenter;
    protected vector m_PendingSize;
    protected int m_Placed;
    protected int m_NoRoom;
    protected int m_Deferred;
    protected int m_CapRefused;
    protected int m_SpawnFailed;
    protected int m_ClaimRefused;
    protected float m_LogAfter;

    static void Open()
    {
        s_Active = new HCXAIFortification;
        s_Active.Load();
    }
    static void Close()
    {
        if (s_Active) { s_Active.Stop(); }
        s_Active = null;
    }
    void Stop()
    {
        if (m_SaveJob)
        {
            if (!m_Fault && !HCSaveScheduler.HCFlush(m_SaveJob)) { m_Fault = true; }
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.Owner = null;
            m_SaveJob = null;
        }
        // Shutdown commits reservations but never creates a world object.
        m_PendingSite = null;
    }
    bool HCPendingCheckpoint() { return m_Revision != m_CommittedRevision; }
    int HCStepReservation()
    {
        if (m_Fault) { return HCSaveJob.STEP_FAILED; }
        if (!m_Writer.SaveInFlight()) { m_SnapshotRevision = m_Revision; }
        int result = m_Writer.SaveStep(STORE, m_State, 32768);
        if (result == HCSaveJob.STEP_FAILED) { m_Fault = true; Summary(); }
        if (result == HCSaveJob.STEP_DONE) { m_CommittedRevision = m_SnapshotRevision; }
        return result;
    }
    static void Enqueue(HCXAISitePatrol patrol, vector anchor)
    {
        if (!s_Active || !patrol || patrol.m_HCTransient || patrol.m_HCFinished) { return; }
        s_Active.Admit(patrol.m_HCSiteId, anchor);
    }
    void Load()
    {
        m_State = new HCXAIFortificationState;
        m_State.WorldName = GetGame().GetWorldName();
        if (!HCV2ThreatStore<HCXAIFortificationState>.CanOpen(STORE)) { m_Fault = true; }
        else if (FileExist(STORE))
        {
            if (!HCV2ThreatStore<HCXAIFortificationState>.Load(STORE, 32768, m_State)) { m_Fault = true; }
        }
        if (!m_State || m_State.Version != 1 || m_State.WorldName != GetGame().GetWorldName() || !m_State.Reserved || m_State.Reserved.Count() > GLOBAL_CAP) { m_Fault = true; }
        if (!m_Fault)
        {
            map<string, bool> unique = new map<string, bool>;
            foreach (string key : m_State.Reserved)
            {
                if (key.Length() < 3 || key.Length() > 100 || unique.Contains(key)) { m_Fault = true; break; }
                unique.Set(key, true);
            }
        }
        if (!m_Fault)
        {
            m_SaveJob = new HCXAIFortificationSaveJob;
            m_SaveJob.Owner = this;
            HCSaveScheduler.HCRegister(m_SaveJob);
        }
        Summary();
    }
    void Admit(string id, vector at)
    {
        if (m_Fault || id == "" || id.Length() > 80 || m_Seen.Find(id) >= 0) { return; }
        if (m_Seen.Count() >= SITE_CAP) { m_CapRefused++; return; }
        m_Seen.Insert(id);
        HCXAIFortificationSite site = new HCXAIFortificationSite;
        site.Id = id;
        site.Anchor = at;
        m_Queue.Insert(site);
    }
    bool Faulted() { return m_Fault; }
    static HCXAIFortification Active() { return s_Active; }
    static void Tick() { if (s_Active) { s_Active.Step(); } }
    void Summary()
    {
        int reserved;
        if (m_State && m_State.Reserved) { reserved = m_State.Reserved.Count(); }
        // Built in short pieces: one long concatenation is "Formula too complex".
        string statusLine = "[HC Plan] HC-17 construction=on kits=fence,watchtower,flag,shelter ai_fortified=" + m_Placed.ToString();
        statusLine += " ai_reserved=" + reserved.ToString() + " ai_sites=" + m_Seen.Count().ToString();
        statusLine += " ai_queue=" + m_Queue.Count().ToString() + " ai_no_room=" + m_NoRoom.ToString();
        statusLine += " ai_deferred=" + m_Deferred.ToString() + " ai_spawn_failed=" + m_SpawnFailed.ToString();
        statusLine += " ai_claim_refused=" + m_ClaimRefused.ToString() + " ai_cap_refused=" + m_CapRefused.ToString();
        statusLine += " ai_store_fault=" + m_Fault.ToString();
        statusLine += " ai_cap=96 per_site=3 count_scope=session restart=spent_slots_not_replayed runtime=PENDING";
        // First receipt, changed content, or one unchanged heartbeat per 30 minutes.
        float statusNow = GetGame().GetTickTime();
        if (statusLine != m_StatusLogLine || statusNow < m_StatusLogAt || statusNow - m_StatusLogAt >= 1800)
        {
            Print("" + statusLine);
            m_StatusLogLine = statusLine;
            m_StatusLogAt = statusNow;
        }
        m_LogAfter = GetGame().GetTickTime() + 60;
    }
    void Step()
    {
        if (GetGame().GetTickTime() >= m_LogAfter) { Summary(); }
        HCSaveScheduler.HCPumpFallback(m_SaveJob);
        if (m_Fault) { return; }
        if (m_PendingSite)
        {
            if (HCPendingCheckpoint()) { return; }
            m_Work.HCReset(1, HCPerfConfig.HCGet().SliceMs);
            if (!m_Work.HCContinue()) { return; }
            HCFinishPlacement();
            return;
        }
        // A cancelled reservation must commit before another candidate can spawn.
        if (HCPendingCheckpoint()) { return; }
        if (m_Queue.Count() == 0) { return; }
        m_Work.HCReset(1, HCPerfConfig.HCGet().SliceMs);
        if (!m_Work.HCContinue()) { return; }
        ref HCXAIFortificationSite site = m_Queue[0];
        m_Queue.RemoveOrdered(0);
        if (site.PartIndex >= SITE_PARTS) { return; }
        HCXZoneGuards guards = HCXZoneGuards.Active();
        if (guards && guards.BySite(site.Id) && !guards.Held(site.Id))
        {
            // Ownership can change again. Keep the cursor and durable slots;
            // round-robin requeue lets other sites continue in the meantime.
            m_Deferred++;
            m_Queue.Insert(site);
            return;
        }
        string key = site.Id + ":" + site.PartIndex.ToString();
        if (m_State.Reserved.Find(key) >= 0)
        {
            site.PartIndex++;
            site.Attempt = 0;
            m_Queue.Insert(site);
            return;
        }
        if (m_State.Reserved.Count() >= GLOBAL_CAP) { m_CapRefused++; return; }
        // Spread 3 isolated pieces around the perimeter; never seal an entrance.
        // Eight deterministic exterior alternatives per slot, no random retries.
        float bearing = Math.AbsInt(site.Id.Hash() % 360) + site.PartIndex * 120 + site.Attempt * 15;
        float radians = bearing * Math.DEG2RAD;
        vector at = site.Anchor + Vector(Math.Sin(radians) * 18, 0, Math.Cos(radians) * 18);
        at[1] = GetGame().SurfaceY(at[0], at[2]);
        array<Man> stepObservers = HCPerfPlayers.HCGet();
        foreach (Man observer : stepObservers)
        {
            if (observer && vector.DistanceSq(observer.GetPosition(), at) < 40000)
            {
                m_Deferred++;
                m_Queue.Insert(site);
                return;
            }
        }
        string kind = "Fence";
        vector size = "7 4 7";
        vector center = at + Vector(0, 2.1, 0);
        if (site.PartIndex == 2) { kind = "Watchtower"; size = "9 12 9"; center = at + Vector(0, 6.1, 0); }
        array<Object> exclude = new array<Object>;
        bool clear = HCBuildingClaim.HCAIFortificationAllowed(at);
        if (!clear) { m_ClaimRefused++; }
        if (GetGame().IsBoxCollidingGeometry(center, Vector(bearing, 0, 0), size, ObjIntersect.View, ObjIntersect.Geom, exclude)) { clear = false; }
        // Keep foundations on reasonably level ground; no buried/tipped scenes.
        if (Math.AbsFloat(GetGame().SurfaceY(at[0] + 3, at[2]) - at[1]) > 0.4 || Math.AbsFloat(GetGame().SurfaceY(at[0] - 3, at[2]) - at[1]) > 0.4 || Math.AbsFloat(GetGame().SurfaceY(at[0], at[2] + 3) - at[1]) > 0.4 || Math.AbsFloat(GetGame().SurfaceY(at[0], at[2] - 3) - at[1]) > 0.4) { clear = false; }
        if (!clear)
        {
            site.Attempt++;
            if (site.Attempt >= 8) { m_NoRoom++; site.PartIndex++; site.Attempt = 0; }
            m_Queue.Insert(site);
            return;
        }
        m_State.Reserved.Insert(key);
        // No second reservation until this image commits. A crash before
        // intent loses no object; after commit a lost continuation spends the
        // slot without replay, matching the existing conservative crash policy.
        m_PendingSite = site;
        m_PendingAt = at;
        m_PendingBearing = bearing;
        m_PendingKind = kind;
        m_PendingCenter = center;
        m_PendingSize = size;
        m_Revision++;
        m_SaveJob.HCDirty = true;
        m_SaveJob.HCUrgent = true;
        m_SaveJob.HCDue = GetGame().GetTickTime();
    }

    protected void HCFinishPlacement()
    {
        HCXAIFortificationSite site = m_PendingSite;
        m_PendingSite = null;
        // Recheck admission after the IO wait. No object exists on refusal, so
        // remove the reservation durably before retrying another alternative.
        bool clear = HCBuildingClaim.HCAIFortificationAllowed(m_PendingAt);
        HCXZoneGuards guards = HCXZoneGuards.Active();
        if (guards && guards.BySite(site.Id) && !guards.Held(site.Id)) { clear = false; }
        array<Man> finishObservers = HCPerfPlayers.HCGet();
        foreach (Man observer : finishObservers)
        {
            if (observer && vector.DistanceSq(observer.GetPosition(), m_PendingAt) < 40000) { clear = false; }
        }
        array<Object> exclude = new array<Object>;
        if (GetGame().IsBoxCollidingGeometry(m_PendingCenter, Vector(m_PendingBearing, 0, 0), m_PendingSize, ObjIntersect.View, ObjIntersect.Geom, exclude)) { clear = false; }
        if (clear)
        {
            BaseBuildingBase fort = HCCampFortification.Place(m_PendingKind, m_PendingAt, Vector(m_PendingBearing, 0, 0));
            if (fort) { m_Placed++; HCReached.Mark("camps.ai_fortification_spawn"); }
            else { m_SpawnFailed++; }
        }
        else
        {
            m_Deferred++;
            m_State.Reserved.RemoveItem(site.Id + ":" + site.PartIndex.ToString());
            m_Revision++;
            m_SaveJob.HCDirty = true;
            m_SaveJob.HCUrgent = true;
            m_SaveJob.HCDue = GetGame().GetTickTime();
            site.Attempt++;
            if (site.Attempt >= 8) { m_NoRoom++; site.PartIndex++; site.Attempt = 0; }
            m_Queue.Insert(site);
            return;
        }
        site.PartIndex++;
        site.Attempt = 0;
        m_Queue.Insert(site);
    }
}

// Existing camp/held-site success seam, including ZoneGuards' zg-* sites.
// No changes in the other workers' director or zone files are required.
modded class HCXAISiteDirector
{
    override void Spawned(HCXAISitePatrol patrol)
    {
        super.Spawned(patrol);
        // Ring admission can relocate m_Position. Resolve the authored site
        // instead, including the authored guard waypoints for zg-* sites.
        if (patrol && !patrol.m_HCTransient && !patrol.m_HCFinished)
        {
            foreach (HCXAISiteState state : m_States)
            {
                if (state.Patrol != patrol || !state.Site) { continue; }
                HCXAIFortification.Enqueue(patrol, this.HCSiteAnchor(state.Site));
                break;
            }
        }
    }
}
modded class HCXAIAdapter
{
    protected ref HCOperationalStatus m_HCFortificationStatus = new HCOperationalStatus;
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer()) { HCXAIFortification.Open(); }
    }
    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (GetGame() && GetGame().IsServer()) { HCXAIFortification.Tick(); }
    }
    override void OnStop()
    {
        HCXAIFortification.Close();
        super.OnStop();
    }
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCOperationalStatus inheritedStatus = super.HCGetOperationalStatus();
        HCXAIFortification service = HCXAIFortification.Active();
        if (service && service.Faulted())
        {
            m_HCFortificationStatus.HCPublish("degraded", "ai_fortification_store_fault");
            return m_HCFortificationStatus;
        }
        return inheritedStatus;
    }
}

class HCXAIFortificationSaveJob : HCSaveJob
{
    HCXAIFortification Owner;
    override string HCName() { return "AIFortification"; }
    override bool HCPendingCheckpoint() { return Owner && Owner.HCPendingCheckpoint(); }
    override int HCStep()
    {
        if (!Owner) { return STEP_FAILED; }
        return Owner.HCStepReservation();
    }
}
