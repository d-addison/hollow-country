// HC-38 / #148. Compatibility shell for existing map consumers and old IDs.
// No listener, request, retry, view cache or per-frame engine work remains.
class HCEventClient
{
    protected static ref HCEventClient s_Instance;

    static HCEventClient Get()
    {
        if (!s_Instance) { s_Instance = new HCEventClient; }
        return s_Instance;
    }
    void Start() { return; }
    void Reset() { return; }
    void Stop() { return; }
    void SetBrowsing(bool browsing) { return; }
    bool Fresh() { return false; }
    bool IsBusy() { return false; }
    string GetNotice() { return ""; }
    HCEventPublicView GetView() { return null; }
    void Transmit(HCEventWireRequest request) { return; }
    bool Browse() { return false; }
    HCEventPublicRow Row(int id) { return null; }
    bool CanSend(int op, int id) { return false; }
    bool Send(int op, int id) { return false; }
    bool ViewValid(HCEventPublicView view) { return false; }
    bool Receive(HCEventPublicView view) { return false; }
    void OnRPC(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx) { return; }
    void Update() { return; }
}
