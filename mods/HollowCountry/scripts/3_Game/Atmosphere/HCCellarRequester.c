// W5 #60. Native scripts-1.30.164289:
// 3_Game/PPEManager/Requesters/PPERUndergroundAcco.c:1-6 native eye setter;
// Requesters/PPERequestPlatformsBase.c:38-56 Start/Stop/IsRequesterRunning;
// PPERequesterBank.c:78 GetRequester(typename), :174 RegisterRequester,
// :262-273 RegisterAdditionalRequesters. Uses a separate requester so stock
// underground areas keep sole ownership of REQ_UNDERGROUND. Client visuals only.
class HCCellarRequester : PPERUndergroundAcco
{
}

modded class PPERequesterRegistrations
{
    override protected void RegisterAdditionalRequesters()
    {
        super.RegisterAdditionalRequesters();
        PPERequesterBank.RegisterRequester(HCCellarRequester);
    }
}
