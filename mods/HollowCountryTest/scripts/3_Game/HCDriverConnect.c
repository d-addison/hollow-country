// Dev-only client connection trace. No retry or connection state changes.
// Native 1.30.164289 signatures: 3_Game/DayZGame.c OnInitialize (2109),
// Connect (2711), OnEvent (1479).
// Separate budgets keep frame/event storms bounded; event payloads, CLI values,
// addresses, passwords and identities are never logged.
#ifndef SERVER
modded class DayZGame
{
    protected int m_HCConnectEntries;
    protected int m_HCConnectEvents;
    protected bool m_HCConnectInitialized;

    override bool OnInitialize()
    {
        bool trace = !m_HCConnectInitialized;
        m_HCConnectInitialized = true;
        if (trace)
        {
            string address;
            bool present = GetCLIParam("connect", address);
            Print("[HC Driver] connect initialize load=" + GetLoadState().ToString() + " game=" + GetGameState().ToString() + " cli=" + present.ToString());
        }
        bool result = super.OnInitialize();
        if (trace)
        {
            Print("[HC Driver] connect initialized load=" + GetLoadState().ToString() + " game=" + GetGameState().ToString());
        }
        return result;
    }

    // CGame.Connect(menu, address, port, password) is proto native and cannot be
    // overridden (client compile: Multiple declaration of function 'Connect', build 185).
    // Vanilla Connect() hides the native result; a nonzero result shows up as a session
    // fail event or as the load state below.
    override void Connect()
    {
        bool trace = m_HCConnectEntries < 16;
        if (trace)
        {
            m_HCConnectEntries++;
            Print("[HC Driver] connect entry load=" + GetLoadState().ToString() + " game=" + GetGameState().ToString());
        }
        super.Connect();
        if (trace)
        {
            Print("[HC Driver] connect returned load=" + GetLoadState().ToString() + " game=" + GetGameState().ToString());
        }
    }

    override void OnEvent(EventType eventTypeId, Param params)
    {
        string eventName;
        if (eventTypeId == MPSessionStartEventTypeID) { eventName = "session start"; }
        else if (eventTypeId == MPSessionFailEventTypeID) { eventName = "session fail"; }
        else if (eventTypeId == MPSessionEndEventTypeID) { eventName = "session end"; }
        if (eventName != "" && m_HCConnectEvents < 16)
        {
            m_HCConnectEvents++;
            Print("[HC Driver] connect " + eventName);
        }
        super.OnEvent(eventTypeId, params);
    }
}
#endif
