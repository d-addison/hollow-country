// Loadout-only adapter: base BeginNew probes both temporary and primary in
// one call. HCXAILoadoutSave separates those probes before arming a fresh image;
// all writing/readback/handle cleanup still uses the shared image state machine.
class HCXAILoadoutImage : HCStagedSaveImage
{
    bool HCArmNew(string path, string text)
    {
        if (Active() || m_Failed || text.Length() < 1 || text.Length() > 65536) { return false; }
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        // Fresh instance per loadout: remaining base cursors/handles retain
        // constructor defaults. Immutable mode writes and verifies the primary.
        m_Path = path;
        m_Temporary = path + ".tmp";
        m_Text = text;
        m_Limit = 65536;
        m_Mode = HC_IMAGE_CREATE;
        m_CheckPrior = false;
        m_Backup = false;
        m_Phase = 0;
        return true;
    }
}
// Provider-ready startup work: one native file operation or image stage/visit.
// Native EnSystem OpenFile/ReadFile/CloseFile, EnScript map.Contains/Set were
// inspected in scripts-1.30.164289. No operator file is overwritten.
class HCXAILoadoutSave : HCSaveJob
{
    ref array<string> Names = new array<string>();
    protected ref HCXAILoadoutImage m_Image = new HCXAILoadoutImage();
    protected int m_Cursor;
    protected int m_Phase;
    protected FileHandle m_Source;
    protected bool m_Open;
    protected string m_Text;
    protected string m_Target;
    bool Finished;
    int Provisioned;
    override string HCName() { return "HCX-loadouts"; }
    void ~HCXAILoadoutSave() { if (m_Open) { CloseFile(m_Source); } }
    protected void HCNext()
    {
        m_Cursor++;
        m_Phase = 1;
        m_Text = "";
        m_Image = new HCXAILoadoutImage();
    }
    // Each visit probes once, opens once, reads <=4096 bytes, closes once,
    // or delegates one staged-image operation. Phases always yield separately.
    override int HCStep()
    {
        if (Finished) { return STEP_DONE; }
        if (m_Phase == 0)
        {
            if (!FileExist(EXPANSION_LOADOUT_FOLDER))
            {
                Print("[HC Expansion AI] loadout defaults skipped: Expansion loadout folder absent");
                Finished = true;
                return STEP_DONE;
            }
            m_Phase = 1;
            return STEP_MORE;
        }
        if (m_Cursor >= Names.Count()) { Finished = true; return STEP_DONE; }
        string name = Names[m_Cursor];
        if (m_Phase == 1)
        {
            m_Target = EXPANSION_LOADOUT_FOLDER + name + ".json";
            if (FileExist(m_Target))
            {
                HCXAIDefaults.HCSetLoadoutPresent(name, true);
                this.HCNext();
            }
            else { m_Phase = 2; }
            return STEP_MORE;
        }
        if (m_Phase == 2)
        {
            m_Source = OpenFile(HCXAIDefaults.Shipped() + "loadouts/" + name + ".json", FileMode.READ);
            m_Open = m_Source != 0;
            if (!m_Open) { this.HCNext(); return STEP_MORE; }
            m_Text = "";
            m_Phase = 3;
            return STEP_MORE;
        }
        if (m_Phase == 3)
        {
            string piece;
            int count = ReadFile(m_Source, piece, 4096);
            if (count < 0 || count != piece.Length() || m_Text.Length() + count > 65536)
            {
                m_Text = "";
                m_Phase = 4;
            }
            else
            {
                m_Text += piece;
                if (count < 4096) { m_Phase = 4; }
            }
            return STEP_MORE;
        }
        if (m_Phase == 4)
        {
            CloseFile(m_Source);
            m_Open = false;
            m_Phase = 5;
            return STEP_MORE;
        }
        if (m_Phase == 5)
        {
            if (m_Text == "") { this.HCNext(); return STEP_MORE; }
            if (FileExist(m_Target + ".tmp")) { return STEP_FAILED; }
            m_Phase = 6;
            return STEP_MORE;
        }
        if (m_Phase == 6)
        {
            // Recheck immediately before arming: preserve operator files that
            // appeared while the shipped source was being read.
            if (FileExist(m_Target))
            {
                HCXAIDefaults.HCSetLoadoutPresent(name, true);
                this.HCNext();
                return STEP_MORE;
            }
            if (!m_Image.HCArmNew(m_Target, m_Text)) { return STEP_FAILED; }
            m_Phase = 7;
            return STEP_MORE;
        }
        int result = m_Image.HCStepImage();
        if (result == STEP_FAILED) { return STEP_FAILED; }
        if (result == STEP_DONE)
        {
            HCXAIDefaults.HCSetLoadoutPresent(name, true);
            Provisioned++;
            this.HCNext();
        }
        return STEP_MORE;
    }
}
// Self-provisioned HCX defaults (owner report 2026-11-18: the Workshop install
// route has no deploy step, so a fresh server had no site policy ("sites off")
// and no HollowCountry_* loadouts ("loadout file missing"), and AI_ENCOUNTER
// waited for sites forever). The reviewed defaults ship inside this addon's PBO
// under HollowCountryExpansionAI/data/defaults/ (byte-identical to
// mission/hollow-country/ai; the full 528-site map policy since #236 and the
// matching 523-row locality catalogue). Operator files are never
// overwritten; a stale operator policy is only reported.
// Native evidence (scripts-1.30.164289): 1_Core/proto/EnSystem.c:397 FileExist,
// :528 DeleteFile, :531 CopyFile; 1_Core/proto/EnString.c:286 Contains;
// 3_Game/tools/JsonFileLoader.c:69 LoadData. Profile/PBO reads and writes reuse
// HollowCountry HCProfileDefaults (Core/HCProfileDefaults.c). The loadout folder
// is Expansion's EXPANSION_LOADOUT_FOLDER ($profile:ExpansionMod\Loadouts\, created
// by Expansion when its settings load); it is never created here.
class HCXAIDefaults
{
    protected static bool s_LoadoutsProbed;
    protected static ref HCXAILoadoutSave s_LoadoutSave;
    protected static int s_ProvisionedLoadouts;
    // Native EnScript.c:866/902/917 Get/Set/Contains. Boot snapshot after
    // Expansion settings are loaded; operator loadout edits require restart.
    protected static ref map<string, bool> s_LoadoutsPresent = new map<string, bool>();
    static bool HCLoadoutPresent(string name) { return s_LoadoutsPresent.Get(name); }
    protected static void HCProbeLoadout(string name)
    {
        s_LoadoutsPresent.Set(name, FileExist(EXPANSION_LOADOUT_FOLDER + name + ".json"));
    }

    static string Shipped()
    {
        return "HollowCountryExpansionAI/data/defaults/";
    }

    static string SitesFile()
    {
        return "expansion-ai-sites.json";
    }

    // Copies the shipped site policy to $profile:HollowCountry only when absent.
    static bool ProvisionSites()
    {
        return HCProfileDefaults.Ensure(HCXAIDefaults.SitesFile(), HCXAIDefaults.Shipped());
    }

    static bool ProvisionLocalities()
    {
        return HCProfileDefaults.Ensure("expansion-ai-localities.json", HCXAIDefaults.Shipped());
    }

    // Our own reviewed loadout names only: HollowCountry_<token>, no path parts.
    static bool LoadoutNameSafe(string name)
    {
        int length = name.Length();
        if (length < 15 || length > 64) { return false; }
        if (name.Substring(0, 14) != "HollowCountry_") { return false; }
        if (name.Contains("..") || name.Contains("/") || name.Contains("\\") || name.Contains(":") || name.Contains("|")) { return false; }
        return true;
    }

    // Copies one shipped loadout into Expansion's loadout folder when that file
    // is absent; temp, copy and readback, never overwriting an operator file.
    static bool ProvisionLoadout(string name)
    {
        if (!HCXAIDefaults.LoadoutNameSafe(name)) { return false; }
        string target = EXPANSION_LOADOUT_FOLDER + name + ".json";
        if (FileExist(target)) { return false; }
        string source = HCXAIDefaults.Shipped() + "loadouts/" + name + ".json";
        string text = HCProfileDefaults.ReadText(source);
        if (text == "")
        {
            Print("[HC Expansion AI] loadout default missing name=" + name + " source=" + source + "; loadout admission keeps its own diagnostic");
            return false;
        }
        string temporary = target + ".hcdefault.tmp";
        // The target was absent before this copy, so a copy that fails readback is removed and retried next boot.
        bool provCopied = false;
        bool provOk = HCProfileDefaults.WriteText(temporary, text);
        if (provOk) { provCopied = CopyFile(temporary, target); provOk = provCopied; }
        if (provOk) { provOk = HCProfileDefaults.ReadText(target) == text; }
        if (!provOk)
        {
            DeleteFile(temporary);
            if (provCopied) { DeleteFile(target); }
            Print("[HC Expansion AI] loadout default refused name=" + name + " reason=write_readback");
            return false;
        }
        DeleteFile(temporary);
        Print("[HC Expansion AI] loadout default provisioned name=" + name + " source=pbo; operator files are never overwritten; runtime=PENDING");
        return true;
    }

    static void HCSetLoadoutPresent(string name, bool present) { s_LoadoutsPresent.Set(name, present); }
    static bool HCLoadoutsReady() { return s_LoadoutSave && (s_LoadoutSave.Finished || s_LoadoutSave.HCFaulted); }
    static void HCStopLoadouts()
    {
        if (s_LoadoutSave) { HCSaveScheduler.HCUnregister(s_LoadoutSave); }
        s_LoadoutSave = null;
        s_LoadoutsProbed = false;
        s_LoadoutsPresent.Clear();
    }
    // The provider-ready tick queues one bounded job instead of copying a
    // whole catalog synchronously. Admission waits for its completed snapshot.
    static int ProvisionLoadouts(HCXAISitePolicy policy)
    {
        if (!policy || !policy.Sites) { return 0; }
        if (!s_LoadoutsProbed)
        {
            s_LoadoutsProbed = true;
            s_LoadoutSave = new HCXAILoadoutSave();
            map<string, bool> seen = new map<string, bool>();
            foreach (HCXAISite site : policy.Sites)
            {
                if (!site || !HCXAIDefaults.LoadoutNameSafe(site.Loadout) || seen.Contains(site.Loadout)) { continue; }
                seen.Set(site.Loadout, true);
                s_LoadoutSave.Names.Insert(site.Loadout);
            }
            array<string> common = {"HollowCountry_Holdout", "HollowCountry_Patrol", "HollowCountry_Scavenger"};
            foreach (string commonName : common)
            {
                if (seen.Contains(commonName)) { continue; }
                s_LoadoutSave.Names.Insert(commonName);
            }
            s_LoadoutSave.HCDirty = true;
            s_LoadoutSave.HCUrgent = true;
            HCSaveScheduler.HCRegister(s_LoadoutSave);
        }
        HCSaveScheduler.HCPumpFallback(s_LoadoutSave);
        if (s_LoadoutSave) { s_ProvisionedLoadouts = s_LoadoutSave.Provisioned; }
        return s_ProvisionedLoadouts;
    }

    static bool MatchesShipped()
    {
        string shipped = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (shipped == "") { return false; }
        return HCWorldStore.Read(HCXAISiteDirector.POLICY) == shipped;
    }

    static int ShippedSiteCount()
    {
        string data = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (data == "") { return 0; }
        string error;
        HCXAISitePolicy policy;
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(data, policy, error) || !policy || !policy.Sites) { return 0; }
        return policy.Sites.Count();
    }

    // Native scripts-1.30.164289: 3_Game/tools/JsonFileLoader.c:69 LoadData,
    // :85 MakeData. Compare typed values so JSON whitespace is not site drift.
    protected static string PolicyDifferences()
    {
        HCXAISitePolicy profile;
        HCXAISitePolicy shipped;
        string error;
        string profileData = HCWorldStore.Read(HCXAISiteDirector.POLICY);
        string shippedData = HCWorldStore.Read(HCXAIDefaults.Shipped() + HCXAIDefaults.SitesFile());
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(profileData, profile, error) || !profile) { return "comparison=profile_unreadable"; }
        if (!JsonFileLoader<HCXAISitePolicy>.LoadData(shippedData, shipped, error) || !shipped) { return "comparison=shipped_unreadable"; }
        if (!profile.Sites || !shipped.Sites) { return "comparison=sites_unreadable"; }
        if (profile.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows() || shipped.Sites.Count() > HCXAISiteRules.HCMaxCatalogRows()) { return "comparison=sites_row_budget"; }
        if (profile.BuildVersion != shipped.BuildVersion)
        {
            Print("[HC Expansion AI] sites policy build stamp differs: profile=" + profile.BuildVersion + " shipped=" + shipped.BuildVersion);
        }
        string keys = "";
        int count = 0;
        HCXAIDefaults.DriftKey(profile.SchemaVersion != shipped.SchemaVersion, "SchemaVersion", keys, count);
        HCXAIDefaults.DriftKey(profile.WorldName != shipped.WorldName, "WorldName", keys, count);
        HCXAIDefaults.DriftKey(profile.BuildVersion != shipped.BuildVersion, "BuildVersion", keys, count);
        HCXAIDefaults.DriftKey(profile.ObserverPolicy != shipped.ObserverPolicy, "ObserverPolicy", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxActiveAI != shipped.MaxActiveAI, "MaxActiveAI", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxActiveSites != shipped.MaxActiveSites, "MaxActiveSites", keys, count);
        HCXAIDefaults.DriftKey(profile.MinPlayerDistance != shipped.MinPlayerDistance, "MinPlayerDistance", keys, count);
        HCXAIDefaults.DriftKey(profile.LineOfSightRange != shipped.LineOfSightRange, "LineOfSightRange", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxLegLength != shipped.MaxLegLength, "MaxLegLength", keys, count);
        HCXAIDefaults.DriftKey(profile.CacheClearRadius != shipped.CacheClearRadius, "CacheClearRadius", keys, count);
        HCXAIDefaults.DriftKey(profile.AIRespawnSeconds != shipped.AIRespawnSeconds, "AIRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.PatrolRespawnSeconds != shipped.PatrolRespawnSeconds, "PatrolRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.HoldoutRespawnSeconds != shipped.HoldoutRespawnSeconds, "HoldoutRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MilitaryRespawnSeconds != shipped.MilitaryRespawnSeconds, "MilitaryRespawnSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MemberReplaceSeconds != shipped.MemberReplaceSeconds, "MemberReplaceSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.RaidCooldownFloorSeconds != shipped.RaidCooldownFloorSeconds, "RaidCooldownFloorSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.ActivationRadiusScale != shipped.ActivationRadiusScale, "ActivationRadiusScale", keys, count);
        HCXAIDefaults.DriftKey(profile.BetrayalRetentionSeconds != shipped.BetrayalRetentionSeconds, "BetrayalRetentionSeconds", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxBetrayalRows != shipped.MaxBetrayalRows, "MaxBetrayalRows", keys, count);
        HCXAIDefaults.DriftKey(profile.MaxSignalWorkPerSecond != shipped.MaxSignalWorkPerSecond, "MaxSignalWorkPerSecond", keys, count);
        string profileSites;
        string shippedSites;
        if (!JsonFileLoader<array<ref HCXAISite>>.MakeData(profile.Sites, profileSites, error, false)) { return "comparison=sites_unreadable"; }
        if (!JsonFileLoader<array<ref HCXAISite>>.MakeData(shipped.Sites, shippedSites, error, false)) { return "comparison=sites_unreadable"; }
        string sites = "same";
        if (profileSites != shippedSites) { sites = "different"; }
        if (keys == "") { keys = "none"; }
        return "policy_keys=" + keys + " differing_key_count=" + count.ToString() + " site_list=" + sites;
    }

    protected static void DriftKey(bool differs, string key, inout string keys, inout int count)
    {
        if (!differs) { return; }
        if (count < 3)
        {
            if (keys != "") { keys = keys + ","; }
            keys = keys + key;
        }
        count++;
    }

    // "" when the operator policy is the shipped default; otherwise one line
    // naming the drift. The operator file is kept either way.
    static string PolicyDrift(bool identical, int profileSites, int shippedSites)
    {
        if (identical) { return ""; }
        if (shippedSites < 1) { return "[HC Expansion AI] sites policy shipped default unreadable; operator file kept"; }
        return "[HC Expansion AI] sites policy differs from shipped default: " + HCXAIDefaults.PolicyDifferences() + "; profile sites=" + profileSites.ToString() + " shipped sites=" + shippedSites.ToString() + "; operator file kept; delete it to adopt the shipped default";
    }
}
