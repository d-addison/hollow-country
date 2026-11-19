// HC-34 / LC-T409 lifecycle adjunct: install the existing picker's walk port.
// No population, route scan, cargo store, timer or provider-created party.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:1120 IsServer;
// 3_Game/gameplay.c:636 GetGame; 1_Core/proto/EnDebug.c:96 Print.
// Expansion calls and exact installed-source citations: HCXAIPickerWalk.c.
// Spec/plan/task HC-34 consumes HC-10 identity + HC-16 custody + route survey.
// Runtime acceptance PENDING; EnableEncounters remains the operator opt-out.
class HCXAIScavengeAdapter
{
    protected bool m_Enabled;
    protected bool m_Reported;
    protected bool m_Bound;
    protected ref HCXAIPickerWalk m_Port;

    void Open(HCSettings settings)
    {
        m_Enabled = settings && settings.EnableEncounters;
        m_Reported = false;
        m_Bound = false;
        if (m_Enabled) { m_Port = new HCXAIPickerWalk(); }
    }

    void Step()
    {
        if (!m_Enabled || m_Bound) { return; }
        if (!HCServer.HCTickWork().HCTake(1)) { return; }
        HCPickers pickers = HCPickers.Get();
        if (pickers && pickers.HCBindProvider(m_Port))
        {
            m_Bound = true;
            Print("[HC Pickers] addon walk=bound runtime=PENDING");
            return;
        }
        if (m_Reported) { return; }
        m_Reported = true;
        Print("[HC Pickers] addon walk=waiting reason=PICKER_IDLE_OWNER_UNAVAILABLE runtime=PENDING");
    }

    void Close()
    {
        m_Enabled = false;
        if (m_Port) { m_Port.HCFinishWalk(); }
        // HCPickers retains its inventory/custody handles until its own stop.
        m_Port = null;
        m_Bound = false;
    }
}

// Same owner-guarded addon install point as HCXAITradeAdapter's trade/combat
// bindings. Start attempts once, tick retries only until the base owner is idle
// (registry startup order independent); a live trip can never be replaced.
modded class HCXAIAdapter
{
    protected ref HCXAIScavengeAdapter m_HCPickerAdapter;

    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (!GetGame() || !GetGame().IsServer()) { return; }
        if (HCXAIService.Adapter() == this)
        {
            m_HCPickerAdapter = new HCXAIScavengeAdapter();
            m_HCPickerAdapter.Open(settings);
            m_HCPickerAdapter.Step();
        }
    }

    override void OnTick(float deltaTime)
    {
        super.OnTick(deltaTime);
        if (HCXAIService.Adapter() == this && m_HCPickerAdapter) { m_HCPickerAdapter.Step(); }
    }

    override void OnStop()
    {
        if (HCXAIService.Adapter() == this && m_HCPickerAdapter) { m_HCPickerAdapter.Close(); }
        m_HCPickerAdapter = null;
        super.OnStop();
    }
}
