// HC-34 / #144. Lifecycle adjunct to HCXAIAdapter, never a population owner.
// Spec/plan/task: HC-34 consumes HC-10 identity, HC-16 funded homes and HC-18
// locality; no second materializer, party, cargo store, route scan or scheduler.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// gameplay.c:636 GetGame; EnDebug.c:96 Print. All other calls are HC ports.
// N17 alone cannot command AI. The supplied pinned Expansion script directory
// is missing in this worker environment. No provider method is invented or
// copied; no route is claimed surveyed. Runtime acceptance remains PENDING.
class HCXAIScavengeAdapter
{
    protected bool m_Enabled;
    protected bool m_Reported;
    protected int m_Reports;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;

    void Open(HCSettings settings)
    {
        m_Enabled = settings && settings.EnableEncounters;
        m_Reported = false;
        m_Reports = 0;
        if (!m_Enabled)
        {
            Print("[HC Plan] HC-34 party=none phase=off cargo_owner=none state=off count=0 runtime=PENDING");
        }
    }

    void Step()
    {
        // One refusal per start, no hidden observer/world/save loop while off
        // or refused. A later route implementation must use HCPerfPlayers' one
        // shared snapshot; there is deliberately no new proximity query here.
        if (!m_Enabled || m_Reported) { return; }
        m_Reported = true;
        Print("[HC Plan] HC-34 party=none phase=refused cargo_owner=none state=refused count=0 refusal=PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED runtime=PENDING");
    }

    // Call only from the existing site's party admission lifecycle, with the
    // exact proposal lease. No client RPC or JSON flag may qualify this port.
    void HCParty(string lease)
    {
        if (!m_Enabled || m_Reports >= 16 || !GetGame() || !GetGame().IsServer()) { return; }
        m_Units.HCReset(1);
        m_Work.HCReset(1);
        if (!m_Units.HCTake(1) || !m_Work.HCContinue()) { return; }
        HCAIPartyIdentity identity = HCWorldMaterializer.HCIdentity(lease);
        if (!HCAIPartyIdentity.HCValid(identity)) { return; }
        m_Reports++;
        string line = "[HC Plan] HC-34 party=" + identity.HCPartyId() + " phase=refused cargo_owner=unknown";
        line += " state=refused count=0 refusal=PROVIDER_SOURCE_MISSING_ROUTE_UNSURVEYED";
        Print(line + " runtime=PENDING");
    }

    void Close()
    {
        m_Enabled = false;
        // HCPickers owns its single inventory transaction and stop cleanup.
        // No provider override, actor or inventory is owned here to delete.
    }
}
