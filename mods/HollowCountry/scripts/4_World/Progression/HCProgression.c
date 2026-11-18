// W5 #130 forage familiarity. Tick bound: decay <=4 of <=128 records with a
// cursor, no player scan; one <=65536-byte save at most every 300 seconds.
// Pickup callbacks look up <=128 records; one gain/player/60s, score <=100.
// Off: no store, arrays, callbacks or ticks. No entity persistence additions.
// Installed scripts-1.30.164289 evidence:
// 1_Core/proto/EnScript.c:380,385,389,399,407 arrays; EnString.c:199,240,448;
// EnDebug.c:96 Print; EnConvert.c:30 int.ToString;
// Shared HCSurvivalRuntime uses Man.c:21 GetIdentity/gameplay.c:368 GetId.
// HCGroupClock.Utc uses EnSystem.c:76,100 UTC; HCV2ThreatStore/HCGroupIO use
// EnSystem.c:397,417,425,443,462,525,528,531 and JsonFileLoader.c:69,85.
// Reuse the existing bounded temp/backup/copy/readback transaction. A leftover
// intent fails closed, preserving all files for operator recovery. There is no
// native rename/fsync API: filesystem-atomic save remains a skipped requirement,
// never represented as proven by this recoverable store or by offline tests.
class HCProgressionRow
{
    string Key;
    int Forage;
    int DecayUtc;
    int GainUtc;
}

class HCProgressionState
{
    int Version = 1;
    ref array<ref HCProgressionRow> Players = new array<ref HCProgressionRow>;
}

class HCProgressionModule : HCModule
{
    static const string PATH = "$profile:HollowCountry/progression.json";
    protected static HCProgressionModule s_HCInstance;
    protected ref HCProgressionState m_State;
    protected bool m_Healthy;
    protected bool m_Dirty;
    protected int m_Cursor;
    protected int m_SaveUtc;

    override string GetName() { return "Progression"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableProgression; }

    protected void HCFail()
    {
        m_Healthy = false;
        if (s_HCInstance == this) { s_HCInstance = null; }
        Print("[HC Progression] disabled: clock/schema/store fault; preserve progression.json .tmp .bak; atomic rename unavailable");
    }

    protected bool HCValidKey(string key)
    {
        if (key.Length() < 33 || key.Length() > 129) { return false; }
        if (key.Get(0) != "p") { return false; }
        int payload = key.Length() - 1;
        if ((payload / 2) * 2 != payload) { return false; }
        string digits = "0123456789abcdef";
        for (int digitIndex = 1; digitIndex < key.Length(); digitIndex++)
        {
            if (digits.IndexOf(key.Get(digitIndex)) < 0) { return false; }
        }
        return true;
    }

    protected bool HCValidState(int now)
    {
        if (!m_State || m_State.Version != 1) { return false; }
        if (!m_State.Players || m_State.Players.Count() > 128) { return false; }
        for (int rowIndex = 0; rowIndex < m_State.Players.Count(); rowIndex++)
        {
            HCProgressionRow row = m_State.Players[rowIndex];
            if (!row || !HCValidKey(row.Key)) { return false; }
            if (row.Forage < 0 || row.Forage > 100) { return false; }
            if (row.DecayUtc < 1 || row.DecayUtc > now) { return false; }
            if (row.GainUtc < 0 || row.GainUtc > now) { return false; }
            for (int earlierIndex = 0; earlierIndex < rowIndex; earlierIndex++)
            {
                if (m_State.Players[earlierIndex].Key == row.Key) { return false; }
            }
        }
        return true;
    }

    override void OnStart(HCSettings settings)
    {
        Print(HCV2Admission.Line("Progression", settings.EnableProgression, "W5-130", false));
        if (!settings.EnableProgression || !HCSurvivalRuntime.HCIsServer()) { return; }
        int now = HCGroupClock.Utc();
        if (now < 1 || now > 2146000000) { HCFail(); return; }
        if (!HCV2ThreatStore<HCProgressionState>.CanOpen(PATH)) { HCFail(); return; }
        if (FileExist(PATH))
        {
            if (!HCV2ThreatStore<HCProgressionState>.Load(PATH, 65536, m_State)) { HCFail(); return; }
        }
        else
        {
            m_State = new HCProgressionState;
            if (!HCV2ThreatStore<HCProgressionState>.Save(PATH, m_State, 65536)) { HCFail(); return; }
        }
        if (!HCValidState(now)) { HCFail(); return; }
        m_SaveUtc = now;
        m_Healthy = true;
        s_HCInstance = this;
        Print("[HC Progression] ready cap=128 score=100 decay=1/day refill-bonus<=10%; runtime acceptance pending");
    }

    protected void HCDecay(HCProgressionRow row, int now)
    {
        int days = (now - row.DecayUtc) / 86400;
        if (days < 1) { return; }
        row.Forage = HCSurvivalPolicy.DecayedFamiliarity(row.Forage, days);
        row.DecayUtc = row.DecayUtc + days * 86400;
        m_Dirty = true;
    }

    // No client input: only a server-observed pickup of an exact forage item
    // may call this. No rewards for picking up arbitrary CE food or re-dropping.
    static int HCRecordForage(PlayerBase player)
    {
        if (!s_HCInstance) { return 0; }
        return s_HCInstance.HCAwardForage(player);
    }

    protected int HCAwardForage(PlayerBase player)
    {
        if (!m_Healthy || !HCSurvivalRuntime.HCIsServer()) { return 0; }
        if (!player || !player.IsAlive()) { return 0; }
        string key = HCSurvivalRuntime.HCIdentityKey(player);
        if (key == "") { return 0; }
        int now = HCGroupClock.Utc();
        if (now < m_SaveUtc || now > 2146000000) { HCFail(); return 0; }
        HCProgressionRow found;
        foreach (HCProgressionRow candidate : m_State.Players)
        {
            if (candidate.Key == key) { found = candidate; break; }
        }
        if (!found)
        {
            if (!HCWorldLimits.Admit(m_State.Players.Count(), 128, "ProgressionPlayers")) { return 0; }
            found = new HCProgressionRow;
            found.Key = key;
            found.DecayUtc = now;
            m_State.Players.Insert(found);
            m_Dirty = true;
        }
        if (found.DecayUtc > now || found.GainUtc > now) { HCFail(); return 0; }
        HCDecay(found, now);
        if (now - found.GainUtc >= 60)
        {
            if (found.Forage < 100) { found.Forage = found.Forage + 1; }
            found.GainUtc = now;
            m_Dirty = true;
            // Bounded diagnostic, no identities in logs.
            if (found.Forage == 1 || (found.Forage / 10) * 10 == found.Forage)
            {
                Print("[HC Progression] forage familiarity=" + found.Forage.ToString());
            }
        }
        return found.Forage;
    }

    protected void HCFlush(int now)
    {
        if (!m_Dirty) { return; }
        if (!HCV2ThreatStore<HCProgressionState>.Save(PATH, m_State, 65536)) { HCFail(); return; }
        m_Dirty = false;
        m_SaveUtc = now;
        Print("[HC Progression] saved players=" + m_State.Players.Count().ToString());
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Healthy) { return; }
        int now = HCGroupClock.Utc();
        if (now < m_SaveUtc || now > 2146000000) { HCFail(); return; }
        int count = m_State.Players.Count();
        int work = 4;
        if (count < work) { work = count; }
        for (int tickIndex = 0; tickIndex < work; tickIndex++)
        {
            if (m_Cursor >= count) { m_Cursor = 0; }
            HCProgressionRow row = m_State.Players[m_Cursor];
            m_Cursor = m_Cursor + 1;
            if (row.DecayUtc > now || row.GainUtc > now) { HCFail(); return; }
            HCDecay(row, now);
        }
        if (now - m_SaveUtc >= 300) { HCFlush(now); }
    }

    override void OnStop()
    {
        if (m_Healthy) { HCFlush(HCGroupClock.Utc()); }
        m_Healthy = false;
        if (s_HCInstance == this) { s_HCInstance = null; }
        m_State = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCProgressionModule);
    }
}
