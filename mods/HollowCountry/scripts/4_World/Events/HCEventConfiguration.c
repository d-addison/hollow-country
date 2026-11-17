class HCEventConfigurationIO : HCEventJournalIO
{
    void HCEventConfigurationIO()
    {
        m_Root = "$profile:HollowCountry/Events";
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
        if (!HCEventRuntimePolicy.SettingsValid(settings))
        {
            Print("[HC Events] invalid existing configuration; no overwrite or default fallback");
            return null;
        }
        return settings;
    }
}
