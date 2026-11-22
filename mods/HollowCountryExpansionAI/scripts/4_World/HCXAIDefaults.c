// Syntax-only DTO: unknown loadout members remain owned by Expansion.
class HCXAILoadoutProbe
{
    string ClassName;
}

// Loadout adapter: caller probes separately, then streams to an HC-private
// intent. The shared image verifies it BEFORE copying to the absent target.
// A retained .hcdefault.tmp is provenance for an interrupted HC publication.
// The pre-copy target recheck is a staged gate of HCXAILoadoutSave (one file
// operation per visit); this adapter only reports when the copy visit is next.
class HCXAILoadoutImage : HCStagedSaveImage
{
    bool HCPublished() { return m_PrimaryExists; }
    // True while the image waits at the copy_primary stage (shared image phase 3).
    bool HCCopyDue() { return m_Phase == 3; }
    // Same latch HCAbort sets before its step; the caller steps the image itself.
    void HCRefuseCopy() { m_Failed = true; }
    bool HCArmNew(string path, string text)
    {
        if (Active() || m_Failed || text.Length() < 1 || text.Length() > 65536) { return false; }
        if (!HCRecoveryGate.HCAllowWrite(path)) { return false; }
        m_Path = path;
        m_Temporary = path + ".hcdefault.tmp";
        m_Text = text;
        m_Limit = 65536;
        m_Mode = HC_IMAGE_REPLACE;
        m_CheckPrior = false;
        m_Backup = false;
        // The final preflight just proved target absence. No delete before copy.
        m_PrimaryKnown = true;
        m_PrimaryExists = false;
        m_Phase = 0;
        return true;
    }
}
// Each visit performs at most ONE native file operation or shared image stage.
// Source/target reads are <=4096 bytes/visit and <=65536 bytes per file. A
// per-name failure continues the catalog; failures never fault the whole job.
// Native EnSystem OpenFile/ReadFile/CloseFile/DeleteFile inspected in 1.30.164289.
class HCXAILoadoutSave : HCSaveJob
{
    ref array<string> Names = new array<string>();
    protected ref HCXAILoadoutImage m_Image = new HCXAILoadoutImage();
    protected int m_Cursor;
    protected int m_Phase;
    protected FileHandle m_Source;
    protected bool m_Open;
    protected string m_Text;
    protected string m_Existing;
    protected string m_Preserved;
    protected string m_Target;
    protected string m_TornPath;
    protected int m_TornSlot;
    // Pre-copy recheck: 0 unchecked, 1 target absent (copy may proceed), 2 target present,
    // 3 our intent present and to be retired, 4 refuse the image, 5 refused (the image drains).
    protected int m_Gate;
    bool Finished;
    int Provisioned;
    override string HCName() { return "HCX-loadouts"; }
    void ~HCXAILoadoutSave() { if (m_Open) { CloseFile(m_Source); } }
    protected void HCNext()
    {
        m_Cursor++;
        m_Phase = 1;
        m_Text = "";
        m_Existing = "";
        m_TornSlot = 0;
        m_Gate = 0;
        m_Image = new HCXAILoadoutImage();
    }
    protected void HCRefused(string reason)
    {
        Print("[HC Expansion AI] loadout default refused name=" + Names[m_Cursor] + " reason=" + reason);
    }
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
            if (FileExist(m_Target)) { m_Phase = 10; }
            else { m_Phase = 2; }
            return STEP_MORE;
        }
        if (m_Phase == 10)
        {
            // Without our private intent the existing file belongs to the
            // operator, even if invalid. Never repair it by guessing ownership.
            if (!FileExist(m_Target + ".hcdefault.tmp"))
            {
                HCXAIDefaults.HCSetLoadoutPresent(name, true);
                this.HCNext();
            }
            else { m_Phase = 11; }
            return STEP_MORE;
        }
        if (m_Phase == 11)
        {
            m_Source = OpenFile(m_Target, FileMode.READ);
            m_Open = m_Source != 0;
            m_Existing = "";
            if (m_Open) { m_Phase = 12; }
            else { this.HCRefused("target_open"); this.HCNext(); }
            return STEP_MORE;
        }
        if (m_Phase == 12)
        {
            string existingPiece;
            int existingCount = ReadFile(m_Source, existingPiece, 4096);
            if (existingCount < 0 || existingCount != existingPiece.Length() || m_Existing.Length() + existingCount > 65536)
            {
                // An unreadable/oversized operator file is not proof of a torn
                // HC target. Preserve it rather than infer ownership.
                this.HCRefused("target_read_or_size");
                m_Phase = 16;
            }
            else
            {
                m_Existing += existingPiece;
                if (existingCount < 4096) { m_Phase = 13; }
            }
            return STEP_MORE;
        }
        if (m_Phase == 13 || m_Phase == 16)
        {
            CloseFile(m_Source);
            m_Open = false;
            if (m_Phase == 16) { this.HCNext(); }
            else { m_Phase = 14; }
            return STEP_MORE;
        }
        if (m_Phase == 14)
        {
            if (HCXAIDefaults.HCWholeLoadout(m_Existing))
            {
                // Retire provenance now: later operator errors are not ours.
                HCXAIDefaults.HCSetLoadoutPresent(name, true);
                m_Phase = 141;
            }
            else { m_Phase = 15; }
            return STEP_MORE;
        }
        if (m_Phase == 141)
        {
            if (!DeleteFile(m_Target + ".hcdefault.tmp")) { this.HCRefused("intent_delete"); }
            else { Print("[HC Expansion AI] loadout default intent cleared name=" + name + " reason=whole_target"); }
            this.HCNext();
            return STEP_MORE;
        }
        if (m_Phase == 15)
        {
            // CopyFile is not assumed to overwrite: probe the numbered slots
            // (like HCPreserveRoute) ONE per visit and refuse when all five are
            // taken. The copy itself is its own visit (phase 151).
            if (m_TornSlot >= 5) { this.HCRefused("torn_preserve_slots_full"); this.HCNext(); return STEP_MORE; }
            string tornCandidate = m_Target + ".hcdefault.torn-" + m_TornSlot.ToString();
            if (FileExist(tornCandidate)) { m_TornSlot++; }
            else { m_TornPath = tornCandidate; m_Phase = 151; }
            return STEP_MORE;
        }
        if (m_Phase == 151)
        {
            if (!CopyFile(m_Target, m_TornPath)) { this.HCRefused("torn_preserve"); this.HCNext(); }
            else { m_Phase = 17; }
            return STEP_MORE;
        }
        if (m_Phase == 17)
        {
            m_Source = OpenFile(m_TornPath, FileMode.READ);
            m_Open = m_Source != 0;
            m_Preserved = "";
            if (!m_Open) { this.HCRefused("torn_preserve"); this.HCNext(); }
            else { m_Phase = 18; }
            return STEP_MORE;
        }
        if (m_Phase == 18)
        {
            string preservedPiece;
            int preservedCount = ReadFile(m_Source, preservedPiece, 4096);
            if (preservedCount < 0 || preservedCount != preservedPiece.Length() || m_Preserved.Length() + preservedCount > 65536)
            {
                this.HCRefused("torn_preserve");
                m_Phase = 16;
            }
            else
            {
                m_Preserved += preservedPiece;
                if (preservedCount < 4096) { m_Phase = 19; }
            }
            return STEP_MORE;
        }
        if (m_Phase == 19)
        {
            CloseFile(m_Source);
            m_Open = false;
            if (m_Preserved != m_Existing) { this.HCRefused("torn_preserve"); this.HCNext(); }
            else { m_Phase = 21; }
            return STEP_MORE;
        }
        if (m_Phase == 21)
        {
            if (!DeleteFile(m_Target)) { this.HCRefused("torn_delete"); this.HCNext(); }
            else
            {
                Print("[HC Expansion AI] loadout default recovered name=" + name + " reason=torn_preserved");
                m_Phase = 2;
            }
            return STEP_MORE;
        }
        if (m_Phase == 2)
        {
            m_Source = OpenFile(HCXAIDefaults.Shipped() + "loadouts/" + name + ".json", FileMode.READ);
            m_Open = m_Source != 0;
            if (!m_Open)
            {
                Print("[HC Expansion AI] loadout default missing name=" + name + " source=pbo");
                this.HCNext();
                return STEP_MORE;
            }
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
                this.HCRefused("source_read_or_size");
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
            if (!HCXAIDefaults.HCWholeLoadout(m_Text)) { this.HCRefused("source_shape"); this.HCNext(); return STEP_MORE; }
            if (FileExist(m_Target + ".hcdefault.tmp")) { m_Phase = 50; }
            else { m_Phase = 6; }
            return STEP_MORE;
        }
        if (m_Phase == 50)
        {
            if (!DeleteFile(m_Target + ".hcdefault.tmp")) { this.HCRefused("intent_delete"); this.HCNext(); }
            else { m_Phase = 6; }
            return STEP_MORE;
        }
        if (m_Phase == 6)
        {
            // Preserve a target that appeared while the source was being read.
            if (FileExist(m_Target))
            {
                HCXAIDefaults.HCSetLoadoutPresent(name, true);
                this.HCNext();
                return STEP_MORE;
            }
            if (!m_Image.HCArmNew(m_Target, m_Text)) { this.HCRefused("arm"); this.HCNext(); return STEP_MORE; }
            m_Phase = 7;
            return STEP_MORE;
        }
        if (m_Phase == 8)
        {
            // Only remove a target this writer successfully published. A failed
            // CopyFile may mean an operator file appeared: preserve it, retain
            // provenance, and let next boot distinguish whole objects/HC tears.
            if (m_Image.HCPublished() && !DeleteFile(m_Target)) { this.HCRefused("torn_delete"); }
            this.HCNext();
            return STEP_MORE;
        }
        // One file operation per visit: recheck the target immediately before the copy
        // visit. No target delete is performed by this job; an existing file is refused.
        if (m_Gate == 0 && m_Image.HCCopyDue())
        {
            if (FileExist(m_Target)) { m_Gate = 2; }
            else { m_Gate = 1; }
            return STEP_MORE;
        }
        if (m_Gate == 2)
        {
            // The target belongs to someone else now. Retire our private intent so a
            // later operator file is never mistaken for our tear. The shared .tmp may
            // already be gone: absence is not an intent_delete failure.
            if (FileExist(m_Target + ".hcdefault.tmp")) { m_Gate = 3; }
            else { m_Gate = 4; }
            return STEP_MORE;
        }
        if (m_Gate == 3)
        {
            m_Gate = 4;
            if (!DeleteFile(m_Target + ".hcdefault.tmp")) { this.HCRefused("intent_delete"); }
            return STEP_MORE;
        }
        if (m_Gate == 4)
        {
            // Latch the shared image failed (no file operation); the step below then
            // drains it one stage per visit and ends in the terminal refusal.
            m_Gate = 5;
            m_Image.HCRefuseCopy();
        }
        int result = m_Image.HCStepImage();
        if (result == STEP_FAILED) { this.HCRefused("write_readback"); m_Phase = 8; }
        if (result == STEP_DONE)
        {
            HCXAIDefaults.HCSetLoadoutPresent(name, true);
            Provisioned++;
            Print("[HC Expansion AI] loadout default provisioned name=" + name + " source=pbo; runtime=PENDING");
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

    // Structural whole-object guard before recovering an HC-owned torn target.
    // Preserve any complete object, including operator-specific loadout fields.
    static bool HCWholeLoadout(string text)
    {
        if (text.Length() < 2 || text.Length() > 65536) { return false; }
        HCTextWindow window = new HCTextWindow(text);
        array<string> stack = new array<string>();
        bool quoted;
        bool escaped;
        bool ended;
        bool started;
        for (int cursor = 0; cursor < window.Length(); cursor++)
        {
            string token = window.At(cursor);
            if (quoted)
            {
                if (escaped) { escaped = false; }
                else if (token == "\\") { escaped = true; }
                else if (token == "\"") { quoted = false; }
                continue;
            }
            if (window.HCWhitespace(cursor)) { continue; }
            if (ended) { return false; }
            if (!started && token != "{") { return false; }
            started = true;
            if (token == "\"") { quoted = true; }
            else if (token == "{" || token == "[")
            {
                if (stack.Count() >= 128) { return false; }
                stack.Insert(token);
            }
            else if (token == "}" || token == "]")
            {
                int depth = stack.Count();
                if (depth < 1) { return false; }
                string open = stack[depth - 1];
                if ((token == "}" && open != "{") || (token == "]" && open != "[")) { return false; }
                stack.Remove(depth - 1);
                ended = stack.Count() == 0;
            }
        }
        if (!ended || quoted || stack.Count() != 0) { return false; }
        HCXAILoadoutProbe probe;
        string error;
        return JsonFileLoader<HCXAILoadoutProbe>.LoadData(text, probe, error) && probe != null;
    }

    // Zone guards ask for their loadout when they create a site, on a server tick.
    // That path performs no file operation: the staged boot job (HCXAILoadoutSave)
    // owns provisioning and recovery for every name in HCCommonLoadouts() and the
    // site catalogue, and the site director reaches the run phase only after it
    // finished. This answers from the boot snapshot: true when the loadout file is
    // present. Operator loadout edits require restart.
    static bool ProvisionLoadout(string name)
    {
        if (!HCXAIDefaults.LoadoutNameSafe(name)) { return false; }
        return s_LoadoutsPresent.Contains(name) && s_LoadoutsPresent.Get(name);
    }

    // Every loadout name zone guards can assign (HCXZoneGuardsSite.HCZoneService).
    static array<string> HCCommonLoadouts()
    {
        return {"HollowCountry_Holdout", "HollowCountry_Patrol", "HollowCountry_Raider", "HollowCountry_Scavenger"};
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
            foreach (string commonName : HCXAIDefaults.HCCommonLoadouts())
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
