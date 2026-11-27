// Lead-only smoke seams. Owners stage work; journal fixture receipts are synthetic.
// Native scripts-1.30.164289: EnScript.c arrays Count/Find/Insert;
// EnString.c IndexOf. All owner operations below are project interfaces.
class HCAdminFixtureProvider : Managed
{
    bool HCFixture(string command, vector pos, out string reason) { reason = "fixture-unknown"; return false; }
    void HCFixtureKit(array<string> lines) {}
}

class HCAdminFixtures
{
    protected static bool s_Enabled;
    protected static ref array<ref HCAdminFixtureProvider> s_Providers = new array<ref HCAdminFixtureProvider>;

    static void HCConfigure(bool enabled) { s_Enabled = enabled; }
    static bool HCEnabled() { return s_Enabled; }

    static bool HCRegister(HCAdminFixtureProvider provider)
    {
        if (!provider || s_Providers.Find(provider) >= 0 || s_Providers.Count() >= 8) { return false; }
        s_Providers.Insert(provider);
        return true;
    }

    static bool HCFixture(string command, vector pos, out string reason)
    {
        reason = "EnableSmokeFixtures-off";
        if (!s_Enabled) { return false; }
        if (command == "fx_holdout_due")
        {
            HCHoldouts holdouts = HCHoldouts.Get();
            reason = "holdout-service-unavailable";
            if (holdouts) { return holdouts.HCFixtureDue(pos, true, reason); }
            return false;
        }
        if (command == "fx_conflict_journal") { return HCFactionConflict.HCFixtureConflictJournal(pos, true, reason); }
        if (command == "fx_conflict")
        {
            HCWorldModule world = HCWorldModule.Get();
            reason = "conflict-service-unavailable";
            if (world) { return HCFactionConflict.HCFixtureConflict(pos, true, reason); }
            return false;
        }
        if (command == "fx_materialize")
        {
            HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
            reason = "materializer-service-unavailable";
            if (materializer) { return materializer.HCFixtureProposal(pos, true, reason); }
            return false;
        }
        foreach (HCAdminFixtureProvider provider : s_Providers)
        {
            reason = "fixture-unknown";
            bool ok = provider.HCFixture(command, pos, reason);
            if (reason != "fixture-unknown") { return ok; }
        }
        reason = "fixture-unknown";
        return false;
    }

    static void HCFixtureKit(array<string> lines)
    {
        // Read-only eligibility probes. Position only ranks; zero never adds a row.
        array<string> commands = {"fx_holdout_due", "fx_conflict_journal", "fx_conflict", "fx_materialize"};
        foreach (string command : commands)
        {
            bool available = false;
            string reason = "EnableSmokeFixtures-off";
            if (s_Enabled)
            {
                reason = "owner-unavailable";
                HCHoldouts holdouts = HCHoldouts.Get();
                HCWorldModule world = HCWorldModule.Get();
                HCWorldMaterializer materializer = HCWorldMaterializer.HCDebugGet();
                if (command == "fx_holdout_due" && holdouts) { available = holdouts.HCFixtureDue("0 0 0", false, reason); }
                if (command == "fx_conflict_journal") { available = HCFactionConflict.HCFixtureConflictJournal("0 0 0", false, reason); }
                if (command == "fx_conflict" && world) { available = HCFactionConflict.HCFixtureConflict("0 0 0", false, reason); }
                if (command == "fx_materialize" && materializer) { available = materializer.HCFixtureProposal("0 0 0", false, reason); }
            }
            string value = "0";
            if (available) { value = "1"; }
            lines.Insert(command + " available=" + value + " reason=" + reason + " fixture=1");
        }
        // Providers must list their own commands without side effects and honor off.
        foreach (HCAdminFixtureProvider provider : s_Providers) { provider.HCFixtureKit(lines); }
    }
}
