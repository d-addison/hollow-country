// Optional tuning only; absent keys retain declared defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// HCGroupIO.Read owns bounded native file IO; HCJsonFields owns key presence.
class HCProgressionConfig
{
    int GainPeriodSeconds = 60;
    int SavePeriodSeconds = 60;
    protected static ref HCProgressionConfig s_Config;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "GainPeriodSeconds")) { this.GainPeriodSeconds = 60; }
        if (!(this.GainPeriodSeconds >= 1 && this.GainPeriodSeconds <= 86400)) { this.GainPeriodSeconds = 60; invalid = true; }
        if (!HCJsonFields.Has(text, "SavePeriodSeconds")) { this.SavePeriodSeconds = 60; }
        if (!(this.SavePeriodSeconds >= 60 && this.SavePeriodSeconds <= 3600)) { this.SavePeriodSeconds = 60; invalid = true; }
        return invalid;
    }
    static HCProgressionConfig Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new HCProgressionConfig;
        string path = "$profile:HollowCountry/progression-config.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCProgressionConfig loaded;
        if (!HCGroupIO.Read(path, 16384, text) || !JsonFileLoader<HCProgressionConfig>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCProgressionConfig invalid_json defaults_restored runtime=PENDING");
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCProgressionConfig invalid_range defaults_restored runtime=PENDING"); }
        return s_Config;
    }
}

// HC-13: account lookup plus native character-generation key; death is a
// synchronous reset barrier, reconnect keeps only the same living generation.
// Native scripts-1.30.164289: 3_Game/Entities/EntityAI.c:3374 GetPersistentID
// (four out ints; all-zero refuses rather than inventing a life identity).
// 4_World/Entities/ManBase/PlayerBase.c:1214,1252 EEKilled/super; native
// :7353/:7408 store hooks inspected but NOT extended (no legacy stream guessing).
// Persistence-ID allocation/stability across reconnect/restart remains PENDING.
// Shared budget/scheduler evidence: Core/HCUnitBudget.c, World/HCWorkBudget.c.
// #169: unmapped v1 rows stay in the capped v2 array until a living pickup.
// Archive raw bytes through HCGroupIO.Read/WriteNew (EnSystem.c:417,425,443,462)
// so an identical archive is safe to reuse after an interrupted migration.
// W5 #130 forage familiarity. Tick bound: decay <=4 of <=128 records with a
// cursor, no routine player scan; routine <=65536-byte checkpoints wait >=60s.
// Death/Stop are durability barriers. Legacy migration inspects <=16 players.
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
    bool LegacyDeferred; // Missing in older JSON: native bool defaults to false.
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
    static const string LEGACY_PATH = "$profile:HollowCountry/progression.v1.json";
    protected static HCProgressionModule s_HCInstance;
    protected ref HCProgressionState m_State;
    protected bool m_Healthy;
    protected bool m_Dirty;
    protected int m_Cursor;
    protected int m_RowCap = 128;
    protected int m_SaveUtc;
    protected int m_Revision;
    protected int m_SnapshotRevision;
    protected ref HCV2ThreatStore<HCProgressionState> m_Writer = new HCV2ThreatStore<HCProgressionState>;
    protected int m_SaveStage;
    protected ref HCProgressionState m_Snapshot;
    protected ref HCProgressionSaveJob m_SaveJob;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_IdentityRefused;
    protected static int s_UnavailableCalls;
    protected int m_SummaryUtc;
    protected int m_ForageCalls;
    protected int m_ForageGains;
    protected int m_Checkpoints;
    protected int m_PersistedRows;
    protected ref map<string, int> m_ForageSkips = new map<string, int>;

    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }

    // Fixed reason vocabulary, bounded by the guards below, never player keys.
    // One detail per reason/window plus a ten-minute summary, including idle windows.
    protected int HCSkipForage(string reason)
    {
        int count = 0;
        m_ForageSkips.Find(reason, count);
        if (count == 0) { Print("[HC Progression] forage skipped reason=" + reason + " runtime=PENDING"); }
        m_ForageSkips.Set(reason, count + 1);
        return 0;
    }

    protected void HCSummary(int now)
    {
        int records = 0;
        if (m_State && m_State.Players) { records = m_State.Players.Count(); }
        string skips = "";
        for (int skipIndex = 0; skipIndex < m_ForageSkips.Count(); skipIndex++)
        {
            skips = skips + " skip_" + m_ForageSkips.GetKey(skipIndex) + "=" + m_ForageSkips.GetElement(skipIndex).ToString();
        }
        bool registered = HCSaveScheduler.HCRegistered(m_SaveJob);
        bool queued = m_SaveJob && m_SaveJob.HCDirty;
        Print("[HC Progression] summary players_tracked=" + records.ToString() + " calls=" + m_ForageCalls.ToString() + " gains=" + m_ForageGains.ToString() + " unavailable=" + s_UnavailableCalls.ToString() + skips + " checkpoints=" + m_Checkpoints.ToString() + " persisted_rows=" + m_PersistedRows.ToString() + " dirty=" + m_Dirty.ToString() + " queued=" + queued.ToString() + " registered=" + registered.ToString() + " shared_saves=" + HCPerfConfig.HCGet().EnableSharedSaves.ToString() + " runtime=PENDING");
        m_SummaryUtc = now;
        m_ForageCalls = 0;
        m_ForageGains = 0;
        m_Checkpoints = 0;
        s_UnavailableCalls = 0;
        m_ForageSkips.Clear();
    }

    protected void HCChanged()
    {
        m_Dirty = true;
        m_Revision = m_Revision + 1;
    }

    protected void HCReceipt(string state, string reason)
    {
        int records = 0;
        if (m_State && m_State.Players) { records = m_State.Players.Count(); }
        Print("[HC Plan] HC-13 familiarity_scope=character-life state=" + state + " reason=" + reason + " records=" + records.ToString() + " cap=" + m_RowCap.ToString() + " runtime=PENDING");
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
        row.LegacyDeferred = false;
        row.Forage = 0;
        row.GainUtc = 0;
        row.DecayUtc = now;
        HCChanged();
    }

    // Only a server-observed living account with an allocated native ID can
    // carry a legacy score forward. Unknown/corpse IDs never share a row.
    protected string HCLegacyCharacterKey(string key)
    {
        array<Man> players = HCPerfPlayers.HCGet();
        if (!players || players.Count() > 16) { return ""; }
        foreach (Man observed : players)
        {
            PlayerBase player = PlayerBase.Cast(observed);
            if (!player || !player.IsAlive()) { continue; }
            if (HCSurvivalRuntime.HCIdentityKey(player) != key) { continue; }
            string characterKey = HCSurvivalRuntime.HCCharacterKey(player);
            if (characterKey == "") { HCIdentityRefusal(); }
            return characterKey;
        }
        return "";
    }

    protected bool HCMigrate(int now)
    {
        if (!m_State) { return false; }
        if (m_State.Version == 2) { return true; }
        if (m_State.Version != 1) { return false; }
        // Preserve the exact validated v1 image, including absent fields and
        // whitespace. Reuse an identical archive on retry; never overwrite one.
        if (!HCV2ThreatStore<HCProgressionState>.CanOpen(LEGACY_PATH)) { return false; }
        string legacyImage;
        if (!HCGroupIO.Read(PATH, 65536, legacyImage)) { return false; }
        if (FileExist(LEGACY_PATH))
        {
            string archivedImage;
            if (!HCGroupIO.Read(LEGACY_PATH, 65536, archivedImage)) { return false; }
            if (archivedImage != legacyImage) { return false; }
        }
        else
        {
            if (!HCGroupIO.WriteNew(LEGACY_PATH, legacyImage, 65536)) { return false; }
        }
        HCProgressionState migrated = new HCProgressionState;
        int mapped = 0;
        int deferred = 0;
        int droppedOverCap = 0;
        foreach (HCProgressionRow row : m_State.Players)
        {
            if (migrated.Players.Count() >= m_RowCap) { droppedOverCap = droppedOverCap + 1; continue; }
            string characterKey = HCLegacyCharacterKey(row.Key);
            row.CharacterKey = characterKey;
            row.Dead = false;
            row.LegacyDeferred = characterKey == "";
            if (row.LegacyDeferred) { deferred = deferred + 1; }
            else { mapped = mapped + 1; }
            migrated.Players.Insert(row);
        }
        m_State = migrated;
        HCChanged();
        Print("[HC Plan] HC-13 legacy migrated=" + mapped.ToString() + " deferred=" + deferred.ToString() + " dropped_over_cap=" + droppedOverCap.ToString() + " archive=progression.v1.json runtime=PENDING");
        return true;
    }

    // Native scripts-1.30.164289: 1_Core/proto/EnScript.c:493 array.Sort.
    // Select the eviction threshold once; ties retain the original oldest-first
    // array order. Rebuild survivors once instead of scanning/shifting per eviction.
    protected void HCPruneRows(int limit)
    {
        int excess = m_State.Players.Count() - limit;
        if (excess <= 0) { return; }
        array<int> activityTimes = new array<int>;
        foreach (HCProgressionRow candidate : m_State.Players)
        {
            int activity = candidate.GainUtc;
            if (activity == 0) { activity = candidate.DecayUtc; }
            activityTimes.Insert(activity);
        }
        activityTimes.Sort();
        int threshold = activityTimes[excess - 1];
        int below = 0;
        foreach (int timestamp : activityTimes)
        {
            if (timestamp < threshold) { below++; }
        }
        int ties = excess - below;
        int removedBeforeCursor = 0;
        array<ref HCProgressionRow> retained = new array<ref HCProgressionRow>;
        for (int rowIndex = 0; rowIndex < m_State.Players.Count(); rowIndex++)
        {
            HCProgressionRow row = m_State.Players[rowIndex];
            int rowActivity = row.GainUtc;
            if (rowActivity == 0) { rowActivity = row.DecayUtc; }
            bool remove = rowActivity < threshold;
            if (rowActivity == threshold && ties > 0) { remove = true; ties--; }
            if (remove)
            {
                if (rowIndex < m_Cursor) { removedBeforeCursor++; }
                HCChanged();
            }
            else { retained.Insert(row); }
        }
        m_State.Players = retained;
        m_Cursor = m_Cursor - removedBeforeCursor;
        if (m_Cursor >= retained.Count()) { m_Cursor = 0; }
    }

    override string GetName() { return "Progression"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableProgression; }

    protected void HCFail()
    {
        m_Healthy = false;
        HCSummary(HCGroupClock.Utc());
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
                HCTextWindow characterKey = new HCTextWindow(row.CharacterKey);
                if (row.CharacterKey != "" && (row.CharacterKey.Length() < 8 || row.CharacterKey.Length() > 49 || characterKey.At(0) != "c")) { return false; }
                if (row.LegacyDeferred)
                {
                    if (row.CharacterKey != "" || row.Dead) { return false; }
                }
                else
                {
                    if ((row.Dead || row.CharacterKey == "") && row.Forage != 0) { return false; }
                }
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
        m_Healthy = false;
        m_IdentityRefused = false;
        m_ForageCalls = 0;
        m_ForageGains = 0;
        m_Checkpoints = 0;
        m_PersistedRows = 0;
        m_ForageSkips.Clear();
        m_RowCap = 128;
        if (settings.MaxFamiliarityRows > 0) { m_RowCap = settings.MaxFamiliarityRows; }
        m_Cursor = 0;
        m_SaveStage = 0;
        m_Revision = 0;
        m_SnapshotRevision = 0;
        m_Dirty = false;
        Print(HCV2Admission.Line("Progression", settings.EnableProgression, "W5-130", false));
        if (!settings.EnableProgression || !HCSurvivalRuntime.HCIsServer())
        {
            m_Status.HCPublish("off", "preference_or_authority");
            HCReceipt("off", "preference_or_authority");
            return;
        }
        int now = HCGroupClock.Utc();
        m_SummaryUtc = now;
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
        HCPruneRows(m_RowCap);
        // Migration/pruning cannot publish changes before the image is durable.
        if (m_Dirty)
        {
            if (!HCV2ThreatStore<HCProgressionState>.Save(PATH, m_State, 65536)) { HCFail(); return; }
            m_Dirty = false;
        }
        m_SaveUtc = now;
        m_PersistedRows = m_State.Players.Count();
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

    // No client input: Forage reports exact-item collection AND retirement here.
    // Null-player retirement earns nothing. No rewards for arbitrary CE food
    // or re-dropping; Forage clears its exact handle before calling this.
    static int HCRecordForage(PlayerBase player)
    {
        if (!s_HCInstance)
        {
            if (s_UnavailableCalls == 0) { Print("[HC Progression] forage skipped reason=module_unavailable runtime=PENDING"); }
            // Saturate while no active module can consume/reset the counter.
            if (s_UnavailableCalls < 2146000000) { s_UnavailableCalls++; }
            return 0;
        }
        return s_HCInstance.HCAwardForage(player);
    }

    protected int HCAwardForage(PlayerBase player)
    {
        m_ForageCalls++;
        if (!m_Healthy) { return HCSkipForage("unhealthy"); }
        if (!HCSurvivalRuntime.HCIsServer()) { return HCSkipForage("not_server"); }
        // Forage also releases expired/deleted items and non-player custody.
        // Those releases legitimately have no player and must never earn a row.
        if (!player) { return HCSkipForage("no_player"); }
        if (!player.IsAlive()) { return HCSkipForage("not_alive"); }
        string identityReason;
        string key = HCSurvivalRuntime.HCIdentityKeyChecked(player, identityReason);
        if (key == "") { return HCSkipForage(identityReason); }
        string characterKey = HCSurvivalRuntime.HCCharacterKey(player);
        if (characterKey == "") { HCIdentityRefusal(); return HCSkipForage("character_id_unavailable"); }
        int now = HCGroupClock.Utc();
        if (now < m_SaveUtc || now > 2146000000) { HCSkipForage("clock_fault"); HCFail(); return 0; }
        HCProgressionRow found;
        foreach (HCProgressionRow candidate : m_State.Players)
        {
            if (candidate.Key == key) { found = candidate; break; }
        }
        if (!found)
        {
            HCPruneRows(m_RowCap - 1);
            found = new HCProgressionRow;
            found.Key = key;
            found.DecayUtc = now;
            m_State.Players.Insert(found);
            HCChanged();
        }
        // Consume the deferred marker in place. Future pickups and restarts
        // follow the normal generation/rate-limit path, never replay the archive.
        if (found.LegacyDeferred)
        {
            found.CharacterKey = characterKey;
            found.LegacyDeferred = false;
            HCChanged();
        }
        if (found.CharacterKey != characterKey)
        {
            HCResetLife(found, characterKey, false, now);
        }
        if (found.Dead) { return HCSkipForage("dead_generation"); }
        if (found.DecayUtc > now || found.GainUtc > now) { HCSkipForage("row_clock_fault"); HCFail(); return 0; }
        HCDecay(found, now);
        if (now - found.GainUtc < HCProgressionConfig.Get().GainPeriodSeconds)
        {
            HCSkipForage("gain_cooldown");
            return found.Forage;
        }
        if (found.Forage < 100)
        {
            found.Forage = found.Forage + 1;
            m_ForageGains++;
            // One award receipt per window; totals remain visible in the summary.
            if (m_ForageGains == 1) { Print("[HC Progression] forage familiarity=" + found.Forage.ToString() + " runtime=PENDING"); }
        }
        else { HCSkipForage("score_cap"); }
        found.GainUtc = now;
        HCChanged();
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
        string key = HCSurvivalRuntime.HCIdentityKey(player);
        foreach (HCProgressionRow row : m_State.Players)
        {
            bool matches = row.CharacterKey == characterKey;
            // No living pickup yet: an observed account death must consume its
            // deferred score too, rather than transfer it to the next life.
            if (row.LegacyDeferred && key != "" && row.Key == key) { matches = true; }
            if (!matches || row.Dead) { continue; }
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
            HCSaveJob.HCOperation = "snapshot";
            m_Snapshot = new HCProgressionState;
            foreach (HCProgressionRow row : m_State.Players)
            {
                HCProgressionRow copy = new HCProgressionRow;
                copy.Key = row.Key;
                copy.CharacterKey = row.CharacterKey;
                copy.Dead = row.Dead;
                copy.LegacyDeferred = row.LegacyDeferred;
                copy.Forage = row.Forage;
                copy.DecayUtc = row.DecayUtc;
                copy.GainUtc = row.GainUtc;
                m_Snapshot.Players.Insert(copy);
            }
            m_SnapshotRevision = m_Revision;
            m_SaveStage = 1;
            return HCSaveJob.STEP_MORE;
        }
        int result = m_Writer.SaveStep(PATH, m_Snapshot, 65536);
        if (result == HCSaveJob.STEP_MORE) { return result; }
        if (result == HCSaveJob.STEP_FAILED)
        {
            HCFail();
            return HCSaveJob.STEP_FAILED;
        }
        m_SaveStage = 0;
        m_Checkpoints++;
        m_PersistedRows = m_Snapshot.Players.Count();
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
        if (now - m_SummaryUtc >= 600) { HCSummary(now); }
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
            HCReached.Mark("progression.row");
        }
        if (m_Dirty && now - m_SaveUtc >= HCProgressionConfig.Get().SavePeriodSeconds) { m_SaveJob.HCDirty = true; }
    }

    override void OnStop()
    {
        if (m_Healthy) { HCFlush(HCGroupClock.Utc()); }
        HCSummary(HCGroupClock.Utc());
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
