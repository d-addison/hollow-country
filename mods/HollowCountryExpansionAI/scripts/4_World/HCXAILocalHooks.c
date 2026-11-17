// Server-local trusted hook port. Installed once at server start, only when
// Expansion AI is loaded. It reports live engine observations (build, world,
// clock) and nothing it cannot verify: every trusted verification flag stays
// false and no digest or session is echoed, so ReceiptValid keeps admission
// closed until real artifact/dependency/observer/route/ledger/ownership
// verifiers replace this port. Route, lease and observer methods keep the base
// refusals (false/null), so no actor can be created through this port.
class HCXAILocalHooks extends HCXAIHooks
{
    protected int m_Sequence;
    override HCXAIAdmission Admission(string worldSession)
    {
        if (!GetGame() || !GetGame().IsServer()) { return null; }
        if (m_Sequence < 1000000) { m_Sequence++; }
        HCXAIAdmission receipt = new HCXAIAdmission();
        receipt.Sequence = m_Sequence;
        receipt.ObservedAtMs = GetGame().GetTime();
        receipt.BuildVersion = HCXAIStore.NativeBuild();
        receipt.WorldName = GetGame().GetWorldName();
        return receipt;
    }
}
