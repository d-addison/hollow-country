// HC-31 startup-only diagnostic. No server trigger, gameplay state, entity or RPC.
// Native scripts-1.30.164289: 1_Core/proto/EnDebug.c:96 Print;
// EnSystem.c:397 FileExist; EnScript.c:380 array Count;
// EnConvert.c:30 int.ToString. HCGroupJson supplies bounded JSON reads using
// EnSystem.c:417,425,443 and 3_Game/tools/JsonFileLoader.c:69 LoadData.
// Counts are per authored class with explicit instance geometry, never runtime
// qualification. Pending retains every authored class: the shared admission is
// admitted unverified (wave 16), so `ready` is a start receipt, not acceptance.
// No tick IO/work. HC-1 getters return the cached result without re-reading files.
class HCCellarsModule : HCModule
{
    protected ref HCOperationalStatus m_HC31Status = new HCOperationalStatus;
    protected bool m_HC31Started;
    protected int m_MeasuredClasses;
    protected int m_PendingClasses;
    protected ref HCCellarSamplerData m_Survey;
    protected ref HCCellarSamplerData m_Measurement;

    override string GetName() { return "Cellars"; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_HC31Status; }

    override bool IsEnabled(HCSettings settings)
    {
        bool requested = settings && settings.EnableAmbientLife;
        if (!requested) { m_HC31Status.HCPublish("off", "operator_preference_or_settings_off"); }
        return requested;
    }

    protected void HCReceipt(string state, string reason)
    {
        m_HC31Status.HCPublish(state, reason);
        string counts = " cellar_measured=" + m_MeasuredClasses.ToString() + " admitted=0 pending=" + m_PendingClasses.ToString();
        string key = " note=";
        if (state != "ready") { key = " refused="; }
        Print("[HC Plan] HC-31" + counts + " state=" + state + key + reason + " runtime=PENDING");
    }

    protected bool HCCountEvidence()
    {
        m_MeasuredClasses = 0;
        m_PendingClasses = 0;
        if (!m_Survey || m_Survey.SchemaVersion != 1 || m_Survey.WorldName != "chernarusplus" || !m_Survey.Classes) { return false; }
        int total = m_Survey.Classes.Count();
        if (total < 1 || total > 64) { return false; }
        for (int surveyIndex = 0; surveyIndex < total; surveyIndex++)
        {
            HCCellarSamplerClass survey = m_Survey.Classes[surveyIndex];
            if (!survey || survey.BuildingClass == "") { return false; }
            for (int priorSurvey = 0; priorSurvey < surveyIndex; priorSurvey++)
            {
                if (m_Survey.Classes[priorSurvey].BuildingClass == survey.BuildingClass) { return false; }
            }
        }
        m_PendingClasses = total;
        if (!m_Measurement) { return true; }
        if (m_Measurement.SchemaVersion != 1 || m_Measurement.WorldName != m_Survey.WorldName) { return false; }
        if (!m_Measurement.Complete || m_Measurement.SkippedTiles != 0 || !m_Measurement.Classes) { return false; }
        if (m_Measurement.Classes.Count() > total) { return false; }
        int measured = 0;
        int instances = 0;
        for (int classIndex = 0; classIndex < m_Measurement.Classes.Count(); classIndex++)
        {
            HCCellarSamplerClass row = m_Measurement.Classes[classIndex];
            if (!row || !row.Instances) { return false; }
            bool known = false;
            for (int knownIndex = 0; knownIndex < total; knownIndex++)
            {
                if (m_Survey.Classes[knownIndex].BuildingClass == row.BuildingClass) { known = true; }
            }
            if (!known) { return false; }
            for (int priorClass = 0; priorClass < classIndex; priorClass++)
            {
                if (m_Measurement.Classes[priorClass].BuildingClass == row.BuildingClass) { return false; }
            }
            instances = instances + row.Instances.Count();
            if (instances > 8192) { return false; }
            bool geometry = false;
            for (int instanceIndex = 0; instanceIndex < row.Instances.Count(); instanceIndex++)
            {
                HCCellarSamplerInstance instance = row.Instances[instanceIndex];
                if (!instance) { return false; }
                if (instance.GeometryMeasured) { geometry = true; }
            }
            if (geometry) { measured = measured + 1; }
        }
        m_MeasuredClasses = measured;
        return true;
    }

    protected bool HCReadCounts()
    {
        m_MeasuredClasses = 0;
        m_PendingClasses = 0;
        string path = "$mission:hollow-country/cellars/classes.json";
        if (FileExist("$profile:HollowCountry/cellar-classes.json")) { path = "$profile:HollowCountry/cellar-classes.json"; }
        if (!HCGroupJson<HCCellarSamplerData>.Load(path, 32768, m_Survey)) { return false; }
        if (!HCCountEvidence()) { return false; }
        string output = "$profile:HollowCountry/cellars-measured.json";
        if (FileExist(output + ".tmp")) { return false; }
        if (!FileExist(output)) { return !FileExist(output + ".bak"); }
        // HCGroupIO's shared read limit is 1 MiB. Oversize/invalid results refuse
        // counting rather than falling back to a guessed or stale measurement.
        if (!HCGroupJson<HCCellarSamplerData>.Load(output, HCGroupIO.HC_RAW_READ_CAP, m_Measurement)) { return false; }
        return HCCountEvidence();
    }

    override void OnStart(HCSettings settings)
    {
        if (m_HC31Started) { return; }
        m_HC31Started = true;
        bool preference = settings && settings.EnableAmbientLife;
        Print(HCV2Admission.Line("Cellars", preference, "EXP-A3", HCV2Gates.Qualified("EXP-A3")));
        // Admitted unverified: ready means started and the shared admission is open
        // for the retained client heuristic. There is no server tick work here; the
        // shared client sample is the runtime consumer (HCCellarsClient.HCSample).
        string state = "ready";
        string reason = HCCellarAdmission.HCReason();
        if (!HCCellarAdmission.HCAdmitted()) { state = "off"; reason = "cellar_admission_closed"; }
        if (!HCReadCounts()) { state = "degraded"; reason = "measurement_counts_unavailable"; }
        HCReceipt(state, reason);
        m_Survey = null;
        m_Measurement = null;
    }

    override void OnStop()
    {
        m_Survey = null;
        m_Measurement = null;
        m_MeasuredClasses = 0;
        m_PendingClasses = 0;
        m_HC31Started = false;
        m_HC31Status.HCStop();
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCCellarsModule);
    }
}
