// Dev-only client connection trace. No retry or connection state changes.
// Native 1.30.164289 signatures: 3_Game/DayZGame.c OnInitialize (2109),
// Connect (2711), OnEvent (1479); Global/Game.c native Connect (252).
// Separate budgets keep frame/event storms bounded; event payloads, CLI values,
// addresses, passwords and identities are never logged.
#ifndef SERVER
modded class DayZGame
{
    protected int m_HCConnectEntries;
    protected int m_HCConnectResults;
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

    override void Connect()
    {
        if (m_HCConnectEntries < 16)
        {
            m_HCConnectEntries++;
            Print("[HC Driver] connect entry load=" + GetLoadState().ToString() + " game=" + GetGameState().ToString());
        }
        super.Connect();
    }

    override int Connect(UIScriptedMenu parent, string IpAddress, int port, string password)
    {
        int result = super.Connect(parent, IpAddress, port, password);
        if (m_HCConnectResults < 16)
        {
            m_HCConnectResults++;
            Print("[HC Driver] connect native result=" + result.ToString());
        }
        return result;
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
