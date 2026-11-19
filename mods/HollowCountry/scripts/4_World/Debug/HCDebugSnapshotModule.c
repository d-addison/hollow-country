// W5 #122. Per core tick: at most ONE Describe (<=64 emitted points, <=8
// routes of <=64 vertices); cursor over <=24 contributors. Every 20 s begin
// a new cycle; completed captures encode/promote over eight separate ticks
// (<=1024 points/128 routes, <=1MiB JSON).
// Off: no arrays, contributors, file I/O or Describe calls allocated by module.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:914 GetTickTime, :931
// GetWorld, :934 GetWorldName, :1120 IsServer; Global/World.c:28 GetDate.
// 1_Core/proto/EnSystem.c:397,525 FileExist/MakeDirectory;
// EnScript.c:380,407 Count/Insert; EnString.c:171,199 ToLower/Length;
// EnConvert.c:30 int.ToString; EnDebug.c:96 Print; gameplay.c:636 GetGame.
// Reuses HCGroupClock.CalendarUtc, HCV2ThreatStore.CanOpen and HCGroupIO:
// native JSON 3_Game/tools/JsonFileLoader.c:85 MakeData; native file sequence
// EnSystem.c:417,425,443,462,528,531 Open/Read/Close/FPrint/Delete/CopyFile.
// No installed rename API: verified temp/backup/copy is NOT atomic rename.
class HCDebugSnapshotModule : HCModule
{
    static const string PATH = "$profile:HollowCountry/debug/snapshot.json";
    static const int MAX_BYTES = 1048576;
    protected bool m_Running;
    protected string m_Refusal;
    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;
    protected bool m_AdmissionPrinted;
    protected bool m_Logged;
    protected float m_Elapsed;
    protected float m_LastLog;
    protected ref HCDebugSnapshot m_Snapshot;
    protected ref HCPerfSnapshotSave m_Save;
    protected ref array<ref HCDebugContributor> m_Builtins;

    override string GetName() { return "DebugSnapshot"; }

    // Wave 16: ready = contributors registered and the snapshot tick running; a world/date/store fault reports why.
    override HCOperationalStatus HCGetOperationalStatus()
    {
        HCModuleReadiness.HCDerive(m_Operational, m_Running, m_Refusal, "", "snapshot_contributors_registered");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableDebugSnapshot; }

    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || m_Running) { return; }
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_Refusal = "";
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("DebugSnapshot", true, "W5-122", false));
            m_AdmissionPrinted = true;
        }
        string worldName = GetGame().GetWorldName();
        worldName.ToLower();
        if (worldName != "chernarusplus") { HCRefuse(); return; }
        if (!HCV2ThreatStore<HCDebugDocument>.CanOpen(PATH)) { HCRefuse(); return; }
        string root = "$profile:HollowCountry/debug";
        if (!FileExist(root) && !MakeDirectory(root)) { HCRefuse(); return; }
        m_Builtins = new array<ref HCDebugContributor>;
        HCDebugPlayersContributor players = new HCDebugPlayersContributor;
        HCKeep(players);
        HCKeep(new HCDebugCampSitesContributor);
        HCKeep(new HCDebugDeadDropsContributor);
        HCKeep(new HCDebugSheltersContributor);
        HCKeep(new HCDebugEventsContributor);
        HCKeep(new HCDebugLeadsContributor(players));
        HCKeep(new HCDebugMaterializerCandidatesContributor);
        HCKeep(new HCDebugLeadLedgerContributor);
        HCKeep(new HCDebugScenesContributor);
        HCKeep(new HCDebugPickersContributor);
        HCKeep(new HCDebugGroupPinsContributor);
        HCKeep(new HCDebugProposalsContributor);
        m_Elapsed = 0;
        m_Running = true;
    }

    protected void HCKeep(HCDebugContributor contributor)
    {
        m_Builtins.Insert(contributor);
        HCDebugSnapshot.HCRegister(contributor);
    }

    protected void HCRefuse()
    {
        Print("[HollowCountry] debug snapshot disabled: world/date/store fault; preserve snapshot.json, .tmp and .bak");
        OnStop();
        m_Refusal = "world_date_or_store_fault";
    }

    protected int HCWorldTime()
    {
        int year;
        int month;
        int day;
        int hour;
        int minute;
        GetGame().GetWorld().GetDate(year, month, day, hour, minute);
        return HCGroupClock.CalendarUtc(year, month, day, hour, minute, 0);
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Running || !(deltaTime > 0)) { return; }
        m_Elapsed += deltaTime;
        // A completed capture, four encodes and each verified file phase get
        // separate ticks. HCStep failure preserves .tmp/.bak and refuses once.
        if (m_Save)
        {
            int result = m_Save.HCStep();
            if (result == HCSaveJob.STEP_FAILED) { m_Save = null; HCRefuse(); return; }
            if (result == HCSaveJob.STEP_DONE)
            {
                HCReportSaved(m_Save.HCBytes());
                m_Save = null;
                m_Snapshot = null;
            }
            return;
        }
        if (!m_Snapshot)
        {
            if (m_Elapsed < 20) { return; }
            m_Elapsed = 0;
            int worldTime = HCWorldTime();
            if (worldTime < 0) { HCRefuse(); return; }
            m_Snapshot = new HCDebugSnapshot(worldTime);
        }
        if (!m_Snapshot.HCCaptureNext()) { return; }
        m_Save = new HCPerfSnapshotSave;
        m_Save.HCBind(PATH, m_Snapshot.HCDocument(), MAX_BYTES);
    }

    protected void HCReportSaved(int bytes)
    {
        float now = GetGame().GetTickTime();
        if (!m_Logged || now - m_LastLog >= 600)
        {
            Print("[HollowCountry] debug snapshot points=" + m_Snapshot.HCPointCount().ToString() + " routes=" + m_Snapshot.HCRouteCount().ToString() + " bytes=" + bytes.ToString());
            m_LastLog = now;
            m_Logged = true;
        }
    }

    override void OnStop()
    {
        m_Running = false;
        // Once intent exists, complete it before discarding the document. Before
        // intent, dropping this read-only diagnostic capture cannot lose world state.
        if (m_Save && !HCSaveScheduler.HCFlush(m_Save))
        {
            m_Refusal = "snapshot_shutdown_store_fault";
            Print("[HC PerfControl] DebugSnapshot shutdown save failed; preserve intent runtime=PENDING");
        }
        m_Save = null;
        m_Snapshot = null;
        if (m_Builtins)
        {
            for (int index = 0; index < m_Builtins.Count(); index++)
            {
                HCDebugSnapshot.HCUnregister(m_Builtins[index]);
            }
        }
        m_Builtins = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCDebugSnapshotModule);
    }
}
