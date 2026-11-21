// Lead-only test-profile selectors. No tick, native dependency calls or use credit.
class HCXAIFixtureProvider : HCAdminFixtureProvider
{
    protected static ref HCXAIFixtureProvider s_Provider;

    static void HCRegisterOnce()
    {
        if (s_Provider) { return; }
        HCXAIFixtureProvider provider = new HCXAIFixtureProvider;
        if (HCAdminModule.HCRegisterFixtureProvider(provider)) { s_Provider = provider; }
    }

    override bool HCFixture(string command, vector pos, out string reason)
    {
        return HCSelect(command, pos, true, reason);
    }

    protected bool HCSelect(string command, vector pos, bool apply, out string reason)
    {
        reason = "fixture-unknown";
        if (command != "fx_incident" && command != "fx_tactic" && command != "fx_trade" && command != "fx_bridge" && command != "fx_convoy_stuck") { return false; }
        reason = "EnableSmokeFixtures-off";
        if (!HCAdminFixtures.HCEnabled()) { return false; }
        if (command == "fx_incident") { return HCXAIIncidentResponse.HCFixtureIncident(pos, apply, reason); }
        if (command == "fx_tactic") { return HCXAITactics.HCFixtureTactic(pos, apply, reason); }
        if (command == "fx_trade") { return HCXAITradeProducer.HCFixtureTrade(pos, apply, reason); }
        if (command == "fx_convoy_stuck") { return HCXAIStuckRecovery.HCFixtureStuck(pos, apply, reason); }
        reason = "use-fx_materialize";
        return false;
    }

    override void HCFixtureKit(array<string> lines)
    {
        array<string> commands = {"fx_incident", "fx_tactic", "fx_trade", "fx_bridge", "fx_convoy_stuck"};
        foreach (string command : commands)
        {
            string reason;
            bool available = HCSelect(command, "0 0 0", false, reason);
            string value = "0";
            if (available) { value = "1"; }
            lines.Insert(command + " available=" + value + " reason=" + reason + " fixture=1");
        }
    }
}
