// Original bounded native persistence. Readback is not fsync or a promise about
// power loss. Immutable intent/image/commit triples; never load an older ACL
// when the highest discovered revision is incomplete, corrupt or incompatible.
class HCGroupStore
{
    static bool HCFieldsPresent(string text)
    {
        // Legacy explorer Visits share this depth but are not markers.
        return HCJsonFields.Every(text, "Color", 5, "CreatorId");
    }

    protected string m_Root = "$profile:HollowCountry/Groups/state";
    protected ref HCGroupSettings m_Settings;
    protected int m_Latest;
    protected bool m_Fault;
    protected bool m_HCDamaged;

    bool Fault()
    {
        m_Fault = true;
        Print("[HC Groups] persistence fault; service disabled, preserve state for recovery");
        return false;
    }

    static HCGroupSettings LoadSettings(out string refusal)
    {
        refusal = "groups_settings_directory_unavailable";
        // Ensure the parent first on an otherwise fresh profile.
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return null;
        string root = "$profile:HollowCountry/Groups";
        if (!FileExist(root) && !MakeDirectory(root)) return null;
        string path = root + "/settings.json";
        HCGroupSettings settings = new HCGroupSettings;
        bool migrate = false;
        refusal = "groups_settings_recovery_required";
        if (!HCV2ThreatStore<HCGroupSettings>.CanOpen(path)) return null;
        if (FileExist(path))
        {
            // Same bounded/recovery-gated read as HCGroupJson.Load, retaining
            // raw keys for native zero-fill default restoration. Native snapshot
            // 1.30.164289: 3_Game/tools/JsonFileLoader.c:69 LoadData.
            string content;
            string error;
            refusal = "groups_settings_read_refused";
            if (!HCGroupIO.Read(path, 8192, content)) return null;
            refusal = "groups_settings_json_invalid";
            if (!JsonFileLoader<HCGroupSettings>.LoadData(content, settings, error)) return null;
            // ShareDiscovery is the only supported missing-key default.
            bool baselinePresent = true;
            if (!HCJsonFields.Has(content, "SchemaVersion") || !HCJsonFields.Has(content, "Enabled") || !HCJsonFields.Has(content, "HCTeamPingEnabled") || !HCJsonFields.Has(content, "WorldIcons") || !HCJsonFields.Has(content, "MapIcons") || !HCJsonFields.Has(content, "RequireGPS") || !HCJsonFields.Has(content, "RequireLOS")) { baselinePresent = false; }
            if (!HCJsonFields.Has(content, "RequireRadio") || !HCJsonFields.Has(content, "NavigationLayer") || !HCJsonFields.Has(content, "DiscoveryLayer") || !HCJsonFields.Has(content, "MissionLayer") || !HCJsonFields.Has(content, "MaxLOSRaysPerTick") || !HCJsonFields.Has(content, "MaxDiscoveries") || !HCJsonFields.Has(content, "MaxExplorers")) { baselinePresent = false; }
            if (!HCJsonFields.Has(content, "DiscoveryIntervalSeconds") || !HCJsonFields.Has(content, "IconScale") || !HCJsonFields.Has(content, "LabelScale") || !HCJsonFields.Has(content, "MaxGroups") || !HCJsonFields.Has(content, "MaxMembers") || !HCJsonFields.Has(content, "MaxMarkers") || !HCJsonFields.Has(content, "MaxInvites")) { baselinePresent = false; }
            if (!HCJsonFields.Has(content, "MaxRequestsPerSecond") || !HCJsonFields.Has(content, "MaxStoreBytes") || !HCJsonFields.Has(content, "KeepRevisions") || !HCJsonFields.Has(content, "InviteSeconds") || !HCJsonFields.Has(content, "MarkerRetentionSeconds") || !HCJsonFields.Has(content, "PositionIntervalSeconds") || !HCJsonFields.Has(content, "PositionStaleSeconds") || !HCJsonFields.Has(content, "MaxIconDistance")) { baselinePresent = false; }
            if (!baselinePresent)
            {
                refusal = "groups_settings_missing_baseline_fields";
                Print("[HC Groups] settings_missing_baseline_fields; preserving settings.json; service inactive runtime=PENDING");
                return null;
            }
            HCGroupSettingDefaults.HCRestoreMissingDefaults(settings, content);
            if (settings && settings.SchemaVersion == 1)
            {
                settings.SchemaVersion = 2;
                settings.ShareDiscovery = true;
                migrate = true;
            }
        }
        else
        {
            refusal = "groups_settings_initial_write_refused";
            if (!HCGroupJson<HCGroupSettings>.WriteNew(path, settings, 8192)) return null;
        }
        refusal = "groups_settings_values_invalid";
        if (!HCGroupRules.SettingsValid(settings)) return null;
        if (migrate)
        {
            refusal = "groups_settings_migration_write_refused";
            if (!HCV2ThreatStore<HCGroupSettings>.Save(path, settings, 8192)) return null;
            Print("[HC Groups] settings migrated v1->v2 ShareDiscovery=true (owner default-on; set false to opt out)");
        }
        refusal = "";
        return settings;
    }

    string PathFor(string prefix, int revision)
    {
        return m_Root + "/" + prefix + revision.ToString() + ".json";
    }

    int RevisionInName(string name, string prefix)
    {
        if (name.IndexOf(prefix) != 0 || name.Length() < prefix.Length() + 6) return 0;
        int number = name.Substring(prefix.Length(), name.Length() - prefix.Length() - 5).ToInt();
        if (number < 1 || number > 1000000000 || prefix + number.ToString() + ".json" != name) return 0;
        return number;
    }

    bool Open(HCGroupSettings settings, out HCGroupState state)
    {
        m_Settings = settings;
        if (!HCGroupRules.SettingsValid(settings)) return Fault();
        if (!FileExist(m_Root))
        {
            if (!MakeDirectory(m_Root)) return Fault();
            state = new HCGroupState;
            state.WorldName = GetGame().GetWorldName();
            state.Revision = 1;
            return Save(state);
        }
        string filename;
        FileAttr attr;
        FindFileHandle handle = FindFile(m_Root + "/*", filename, attr, FindFileFlags.DIRECTORIES);
        if (!handle) return Fault();
        int highestIntent = 0;
        int highestImage = 0;
        int highestCommit = 0;
        int count = 0;
        bool valid = true;
        bool found = filename != "";
        while (found)
        {
            if (filename != "." && filename != "..")
            {
                count++;
                int intent = RevisionInName(filename, "intent_");
                int image = RevisionInName(filename, "state_");
                int commit = RevisionInName(filename, "commit_");
                if (attr == FileAttr.DIRECTORY || count > 3 * (settings.KeepRevisions + 2) || (intent == 0 && image == 0 && commit == 0))
                {
                    valid = false;
                    break;
                }
                highestIntent = Math.Max(highestIntent, intent);
                highestImage = Math.Max(highestImage, image);
                highestCommit = Math.Max(highestCommit, commit);
            }
            found = FindNextFile(handle, filename, attr);
        }
        CloseFindFile(handle);
        if (valid && count == 0)
        {
            state = new HCGroupState;
            state.WorldName = GetGame().GetWorldName();
            state.Revision = 1;
            return Save(state);
        }
        if (!valid || highestIntent < 1 || highestIntent != highestImage || highestImage != highestCommit) { m_HCDamaged = true; return Fault(); }
        string imageText;
        if (!HCGroupIO.Read(PathFor("state_", highestImage), settings.MaxStoreBytes, imageText)) { m_HCDamaged = true; return Fault(); }
        string error;
        HCGroupReceipt receipt;
        HCGroupReceipt intentReceipt;
        if (!HCGroupJson<HCGroupReceipt>.Load(PathFor("commit_", highestCommit), 1024, receipt) || !HCGroupJson<HCGroupReceipt>.Load(PathFor("intent_", highestIntent), 1024, intentReceipt) || !receipt || !intentReceipt) { m_HCDamaged = true; return Fault(); }
        if (!JsonFileLoader<HCGroupState>.LoadData(imageText, state, error) || !HCGroupRules.StateValid(state, settings, GetGame().GetWorldName())) { m_HCDamaged = true; return Fault(); }
        if (!HCFieldsPresent(imageText)) { Print("[HC Groups] missing Color; runtime=PENDING"); m_HCDamaged = true; return Fault(); }
        if (receipt.Version != 1 || intentReceipt.Version != 1 || receipt.WorldName != state.WorldName || intentReceipt.WorldName != state.WorldName || intentReceipt.Revision != receipt.Revision || intentReceipt.Length != receipt.Length || intentReceipt.Hash != receipt.Hash) { m_HCDamaged = true; return Fault(); }
        if (!HCGroupRules.LatestComplete(highestIntent, highestImage, highestCommit, receipt.Revision, state.Revision, receipt.Length, imageText.Length(), receipt.Hash, imageText.Hash())) { m_HCDamaged = true; return Fault(); }
        HCGroupRules.MigrateExplorers(state);
        state.Invitations.Clear();
        m_Latest = state.Revision;
        return true;
    }

    protected ref HCStagedSaveImage m_Image = new HCStagedSaveImage;
    protected int m_Part;
    protected string m_PendingText;
    protected string m_ReceiptText;
    protected int m_TargetRevision;

    // Write/verify immutable intent, then image, then commit. Publish/prune only
    // after all three agree. A partial highest triple keeps Open fail-closed.
    int SaveStep(HCGroupState state)
    {
        if (m_Fault) { return HCSaveJob.STEP_FAILED; }
        if (m_Part == 0)
        {
            if (!state || state.Revision != m_Latest + 1 || !HCGroupRules.StateValid(state, m_Settings, GetGame().GetWorldName())) { Fault(); return HCSaveJob.STEP_FAILED; }
            string error;
            array<ref HCGroupInvitation> invitations = state.Invitations;
            state.Invitations = new array<ref HCGroupInvitation>;
            bool serialized = JsonFileLoader<HCGroupState>.MakeData(state, m_PendingText, error);
            state.Invitations = invitations;
            if (!serialized || m_PendingText.Length() > m_Settings.MaxStoreBytes) { Fault(); return HCSaveJob.STEP_FAILED; }
            HCGroupReceipt receipt = new HCGroupReceipt;
            receipt.Revision = state.Revision;
            receipt.WorldName = state.WorldName;
            receipt.Length = m_PendingText.Length();
            receipt.Hash = m_PendingText.Hash();
            if (!JsonFileLoader<HCGroupReceipt>.MakeData(receipt, m_ReceiptText, error)) { Fault(); return HCSaveJob.STEP_FAILED; }
            m_TargetRevision = state.Revision;
            m_Part = 1;
            return HCSaveJob.STEP_MORE;
        }
        int old = m_TargetRevision - m_Settings.KeepRevisions;
        if (m_Part > 6 || (m_Part > 3 && old < 1))
        {
            m_Latest = m_TargetRevision;
            m_Part = 0;
            m_PendingText = "";
            m_ReceiptText = "";
            return HCSaveJob.STEP_DONE;
        }
        if (!m_Image.Active())
        {
            bool began;
            if (m_Part == 1) { began = m_Image.BeginNew(PathFor("intent_", m_TargetRevision), m_ReceiptText, 1024); }
            if (m_Part == 2) { began = m_Image.BeginNew(PathFor("state_", m_TargetRevision), m_PendingText, m_Settings.MaxStoreBytes); }
            if (m_Part == 3) { began = m_Image.BeginNew(PathFor("commit_", m_TargetRevision), m_ReceiptText, 1024); }
            if (m_Part == 4) { began = m_Image.BeginRemove(PathFor("intent_", old)); }
            if (m_Part == 5) { began = m_Image.BeginRemove(PathFor("state_", old)); }
            if (m_Part == 6) { began = m_Image.BeginRemove(PathFor("commit_", old)); }
            if (!began) { Fault(); return HCSaveJob.STEP_FAILED; }
        }
        int result = m_Image.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED) { Fault(); return result; }
        if (result == HCSaveJob.STEP_DONE) { m_Part++; }
        return HCSaveJob.STEP_MORE;
    }

    bool Save(HCGroupState state)
    {
        int result = HCSaveJob.STEP_MORE;
        int stages;
        // Startup and explicit owner barriers only; routine batches use SaveStep.
        while (result == HCSaveJob.STEP_MORE && stages < HCStagedSaveImage.HC_MAX_STAGES + 32)
        {
            result = SaveStep(state);
            stages++;
        }
        if (result == HCSaveJob.STEP_MORE)
        {
            Print("[HC Persistence] owner=HCGroupStore guard=save_stage_guard steps=" + stages.ToString());
            return Fault();
        }
        return result == HCSaveJob.STEP_DONE;
    }
}
