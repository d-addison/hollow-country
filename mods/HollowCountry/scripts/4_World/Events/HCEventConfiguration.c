class HCEventConfigurationIO : HCEventJournalIO
{
    void HCEventConfigurationIO()
    {
        m_Root = "$profile:HollowCountry/Events";
        m_Label = "configuration directory";
    }
}
class HCEventSettingsCodec
{
    string Encode(HCEventSettings settings)
    {
        string text;
        string error;
        if (!JsonFileLoader<HCEventSettings>.MakeData(settings, text, error, true)) return "";
        return text;
    }
    HCEventSettings Decode(string text)
    {
        HCEventSettings settings;
        string error;
        if (!JsonFileLoader<HCEventSettings>.LoadData(text, settings, error)) return null;
        return settings;
    }
}
// Operator policy for journal write coalescing. Optional private file
// HollowCountry/Events/journal.json; absent or invalid fields keep these defaults.
// MinJournalIntervalSeconds is the shortest gap between two routine (membership) journal
// writes; 0 writes every change immediately. Registry key Events.MinJournalIntervalSeconds.
class HCEventJournalConfig
{
    int MinJournalIntervalSeconds = 5;

    // True when a present value was out of range and was reset to the default.
    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "MinJournalIntervalSeconds")) { this.MinJournalIntervalSeconds = 5; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MinJournalIntervalSeconds", this.MinJournalIntervalSeconds)) { this.MinJournalIntervalSeconds = 5; invalid = true; }
        return invalid;
    }
}
class HCEventConfiguration
{
    protected ref HCEventConfigurationIO m_IO = new HCEventConfigurationIO;
    protected ref HCEventSettingsCodec m_Codec = new HCEventSettingsCodec;

    HCEventSettings Load()
    {
        if (!m_IO.Ensure())
        {
            Print("[HC Events] cannot create private configuration directory");
            return null;
        }
        HCEventSettings settings;
        if (m_IO.Exists("settings.json"))
        {
            settings = m_Codec.Decode(m_IO.Read("settings.json", 16384));
        }
        else
        {
            settings = new HCEventSettings;
            settings.Sites = HCEventSites.ChernarusPlus();
            string template = m_Codec.Encode(settings);
            if (!m_IO.WriteNew("settings.json", template, 16384))
            {
                Print("[HC Events] configuration template write failed");
                return null;
            }
            Print("[HC Events] generated enabled preference template; review world sites and provider prerequisites");
        }
        if (settings && HCEventSitesGate.Admitted())
        {
            // In memory only; settings.json is never rewritten with curated sites.
            HCEventReviewedSites.Merge(settings);
        }
        if (!HCEventRuntimePolicy.SettingsValid(settings))
        {
            Print("[HC Events] invalid existing configuration; no overwrite or default fallback");
            return null;
        }
        return settings;
    }

    HCEventJournalConfig LoadJournalPolicy()
    {
        HCOperatorSettingsRegistry.HCLocalPolicyInit();
        HCEventJournalConfig policy = new HCEventJournalConfig;
        if (m_IO.Exists("journal.json"))
        {
            string text = m_IO.Read("journal.json", 1024);
            string error;
            HCEventJournalConfig loaded;
            if (text == "" || !JsonFileLoader<HCEventJournalConfig>.LoadData(text, loaded, error) || !loaded)
            {
                Print("[HC Config] HCEventJournalConfig invalid_json defaults_restored runtime=PENDING");
            }
            else
            {
                if (loaded.HCNormalize(text)) { Print("[HC Config] HCEventJournalConfig invalid_range defaults_restored runtime=PENDING"); }
                policy = loaded;
            }
        }
        Print("[HC Config] HCEventJournalConfig min_journal_interval_s=" + policy.MinJournalIntervalSeconds.ToString() + " runtime=PENDING");
        return policy;
    }
}
