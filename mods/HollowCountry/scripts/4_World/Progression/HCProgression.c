// HC-13: account lookup plus native character-generation key; death is a
// synchronous reset barrier, reconnect keeps only the same living generation.
// Native scripts-1.30.164289: 3_Game/Entities/EntityAI.c:3374 GetPersistentID
// (four out ints; all-zero refuses rather than inventing a life identity).
// 4_World/Entities/ManBase/PlayerBase.c:1214,1252 EEKilled/super; native
// :7353/:7408 store hooks inspected but NOT extended (no legacy stream guessing).
// Persistence-ID allocation/stability across reconnect/restart remains PENDING.
// Shared budget/scheduler evidence: Core/HCUnitBudget.c, World/HCWorkBudget.c.
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
    string Key; // account UID encoding, never a character-generation key
    string CharacterKey;
    bool Dead;
    int Forage;
    int DecayUtc;
    int GainUtc;
}

class HCProgressionState
{
    int Version = 2;
    ref array<ref HCProgressionRow> Players = new array<ref HCProgressionRow>;
}

class HCProgressionSaveJob : HCSaveJob
{
    HCProgressionModule Owner;
    override string HCName() { return "Progression"; }
    override int HCStep()
    {
        if (!Owner) { return HCSaveJob.STEP_FAILED; }
        return Owner.HCStepCheckpoint();
    }
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
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected int m_SaveStage;
    protected ref HCProgressionState m_Snapshot;
    protected ref HCProgressionSaveJob m_SaveJob;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_IdentityRefused;

    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    protected void HCChanged()
    {
        m_Dirty = true;
        m_Revision = m_Revision + 1;
    }

    protected void HCReceipt(string state, string reason)
    {
        int records = 0;
        if (m_State && m_State.Players) { records = m_State.Players.Count(); }
        Print("[HC Plan] HC-13 familiarity_scope=character-life state=" + state + " reason=" + reason + " records=" + records.ToString() + " cap=128 runtime=PENDING");
    }

    protected void HCIdentityRefusal()
    {
        if (m_IdentityRefused) { return; }
        m_IdentityRefused = true;
        m_Status.HCPublish("degraded", "character_id_unavailable");
        HCReceipt("refused", "character_id_unavailable");
    }

    protected void HCResetLife(HCProgressionRow row, string characterKey, bool dead, int now)
    {
        row.CharacterKey = characterKey;
        row.Dead = dead;
        row.Forage = 0;
        row.GainUtc = 0;
        row.DecayUtc = now;
        HCChanged();
    }

    protected bool HCMigrate(int now)
    {
        if (!m_State) { return false; }
        if (m_State.Version == 2) { return true; }
        if (m_State.Version != 1) { return false; }
        // Caller validates the complete legacy image before migration. No
        // account-wide reward is evidence of the current character's life.
        foreach (HCProgressionRow row : m_State.Players)
        {
            HCResetLife(row, "", false, now);
        }
        m_State.Version = 2;
        HCChanged();
        return true;
    }

    override string GetName() { return "Progression"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableProgression; }

    protected void HCFail()
    {
        m_Healthy = false;
        m_Status.HCPublish("refused", "clock_schema_store_fault");
        HCReceipt("refused", "clock_schema_store_fault");
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
        if (!m_State || (m_State.Version != 1 && m_State.Version != 2)) { return false; }
        if (!m_State.Players || m_State.Players.Count() > 128) { return false; }
        for (int rowIndex = 0; rowIndex < m_State.Players.Count(); rowIndex++)
        {
            HCProgressionRow row = m_State.Players[rowIndex];
            if (!row || !HCValidKey(row.Key)) { return false; }
            if (m_State.Version == 2)
            {
                if (row.CharacterKey != "" && (row.CharacterKey.Length() < 8 || row.CharacterKey.Length() > 49 || row.CharacterKey.Get(0) != "c")) { return false; }
                if ((row.Dead || row.CharacterKey == "") && row.Forage != 0) { return false; }
            }
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
        if (!settings.EnableProgression || !HCSurvivalRuntime.HCIsServer())
        {
            m_Status.HCPublish("off", "preference_or_authority");
            HCReceipt("off", "preference_or_authority");
            return;
        }
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
        if (!HCMigrate(now)) { HCFail(); return; }
        // Migration cannot publish old account rewards before its reset is durable.
        if (m_Dirty)
        {
            if (!HCV2ThreatStore<HCProgressionState>.Save(PATH, m_State, 65536)) { HCFail(); return; }
            m_Dirty = false;
        }
        m_SaveUtc = now;
        m_SaveJob = new HCProgressionSaveJob;
        m_SaveJob.Owner = this;
        HCSaveScheduler.HCRegister(m_SaveJob);
        m_Healthy = true;
        s_HCInstance = this;
        m_Status.HCPublish("ready", "character_life_store_loaded");
        HCReceipt("ready", "character_life_store_loaded");
    }

    protected void HCDecay(HCProgressionRow row, int now)
    {
        int days = (now - row.DecayUtc) / 86400;
        if (days < 1) { return; }
        row.Forage = HCSurvivalPolicy.DecayedFamiliarity(row.Forage, days);
        row.DecayUtc = row.DecayUtc + days * 86400;
        HCChanged();
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
        string characterKey = HCSurvivalRuntime.HCCharacterKey(player);
        if (characterKey == "") { HCIdentityRefusal(); return 0; }
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
            HCChanged();
        }
        if (found.CharacterKey != characterKey)
        {
            HCResetLife(found, characterKey, false, now);
        }
        if (found.Dead) { return 0; }
        if (found.DecayUtc > now || found.GainUtc > now) { HCFail(); return 0; }
        HCDecay(found, now);
        if (now - found.GainUtc >= 60)
        {
            if (found.Forage < 100) { found.Forage = found.Forage + 1; }
            found.GainUtc = now;
            HCChanged();
            // Bounded diagnostic, no identities in logs.
            if (found.Forage == 1 || (found.Forage / 10) * 10 == found.Forage)
            {
                Print("[HC Progression] forage familiarity=" + found.Forage.ToString());
            }
        }
        return found.Forage;
    }

    static void HCCharacterDied(PlayerBase player)
    {
        if (!s_HCInstance) { return; }
        s_HCInstance.HCObserveDeath(player);
    }

    protected void HCObserveDeath(PlayerBase player)
    {
        if (!m_Healthy || !HCSurvivalRuntime.HCIsServer() || !player) { return; }
        // Identity can already be detached. Match the observed character, never
        // let an old corpse reset a newer character for the same account.
        string characterKey = HCSurvivalRuntime.HCCharacterKey(player);
        if (characterKey == "") { HCIdentityRefusal(); return; }
        int now = HCGroupClock.Utc();
        if (now < m_SaveUtc || now > 2146000000) { HCFail(); return; }
        foreach (HCProgressionRow row : m_State.Players)
        {
            if (row.CharacterKey != characterKey || row.Dead) { continue; }
            HCResetLife(row, characterKey, true, now);
            // Death must not sit in the routine checkpoint queue. Finish any
            // older snapshot AND persist the tombstone before continuing.
            HCFlush(now);
            return;
        }
    }

    int HCStepCheckpoint()
    {
        if (!m_Healthy) { return HCSaveJob.STEP_FAILED; }
        if (m_SaveStage == 0)
        {
            m_Snapshot = new HCProgressionState;
            foreach (HCProgressionRow row : m_State.Players)
            {
                HCProgressionRow copy = new HCProgressionRow;
                copy.Key = row.Key;
                copy.CharacterKey = row.CharacterKey;
                copy.Dead = row.Dead;
                copy.Forage = row.Forage;
                copy.DecayUtc = row.DecayUtc;
                copy.GainUtc = row.GainUtc;
                m_Snapshot.Players.Insert(copy);
            }
            m_SnapshotRevision = m_Revision;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        if (!HCV2ThreatStore<HCProgressionState>.Save(PATH, m_Snapshot, 65536))
        {
            HCFail();
            return HCSaveJob.STEP_FAILED;
        }
        m_SaveStage = 0;
        m_Snapshot = null;
        if (m_SnapshotRevision != m_Revision) { return HCSaveJob.STEP_MORE; }
        m_Dirty = false;
        m_SaveUtc = HCGroupClock.Utc();
        return HCSaveJob.STEP_DONE;
    }

    protected void HCFlush(int now)
    {
        if (!m_Dirty || !m_SaveJob) { return; }
        m_SaveJob.HCDirty = true;
        if (!HCSaveScheduler.HCFlush(m_SaveJob)) { HCFail(); }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Healthy) { return; }
        int now = HCGroupClock.Utc();
        if (now < m_SaveUtc || now > 2146000000) { HCFail(); return; }
        int count = m_State.Players.Count();
        int work = 4;
        if (count < work) { work = count; }
        m_Units.HCReset(4);
        m_Work.HCReset(4);
        for (int tickIndex = 0; tickIndex < work; tickIndex++)
        {
            if (!m_Work.HCContinue() || !m_Units.HCTake(1)) { return; }
            if (m_Cursor >= count) { m_Cursor = 0; }
            HCProgressionRow row = m_State.Players[m_Cursor];
            m_Cursor = m_Cursor + 1;
            if (row.DecayUtc > now || row.GainUtc > now) { HCFail(); return; }
            HCDecay(row, now);
        }
        if (m_Dirty && now - m_SaveUtc >= 300) { m_SaveJob.HCDirty = true; }
    }

    override void OnStop()
    {
        if (m_Healthy) { HCFlush(HCGroupClock.Utc()); }
        m_Healthy = false;
        if (m_SaveJob)
        {
            HCSaveScheduler.HCUnregister(m_SaveJob);
            m_SaveJob.Owner = null;
            m_SaveJob = null;
        }
        m_Status.HCPublish("off", "stopped");
        if (s_HCInstance == this) { s_HCInstance = null; }
        m_State = null;
        m_Snapshot = null;
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

// N1/N17: the existing native death callback is sufficient; no mission hook,
// position write, native store-stream extension or fresh-character teleport.
modded class PlayerBase
{
    override void EEKilled(Object killer)
    {
        HCProgressionModule.HCCharacterDied(this);
        super.EEKilled(killer);
    }
}
