// Native PlayerBase.OnDisconnect exists in installed 1.30. Preserve its chain;
// remove every event binding before native identity/disconnection cleanup.
modded class PlayerBase
{
    override void OnDisconnect()
    {
        HCEventModule events = HCEventModule.Get();
        if (GetGame().IsServer() && events)
        {
            events.PlayerDisconnected(this);
        }
        super.OnDisconnect();
    }
}
