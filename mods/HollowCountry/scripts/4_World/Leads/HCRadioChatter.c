// LC-T307, #91/#119. Native evidence: scripts-1.30.164289/
// 4_World/Entities/Core/Inherited/InventoryItem.c:14,18,22 (ItemTransmitter,
// GetTunedFrequency, IsReceiving); Entities/ItemBase/TransmitterBase/PersonalRadio.c:1;
// 3_Game/tools/Component/ComponentEnergyManager.c:884,925 (switch/powered work);
// 4_World/Entities/ItemBase/TransmitterBase.c:96,107 (OnWorkStart/Stop receive);
// 3_Game/Systems/Inventory/Inventory.c:127,134 (enumerate/count),
// 3_Game/Entities/EntityAI.c:882,1884,3409 (root player/inventory/energy manager),
// 3_Game/Entities/Object.c:517,1219 (alive/ruined), Man.c:21 (identity),
// 3_Game/Global/Game.c:945 (GetPlayers),
// 3_Game/Client/Notifications/NotificationSystem.c:125 (server notification),
// 1_Core/proto/EnConvert.c:115 (float.ToString). Receiving follows the existing
// HCGroupEquipment.Read inventory pattern, adding explicit receive/switch checks.
// 1_Core/proto/EnScript.c:94 (Class.Cast).
class HCRadioChatter : HCModule
{
    protected static HCRadioChatter s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref array<Man> m_Listeners = new array<Man>();
    protected ref array<ref HCWorldLead> m_Fallback = new array<ref HCWorldLead>();
    protected ref HCWorldLead m_Report;
    protected HCRadioChannel m_Channel;
    protected string m_Text;
    protected string m_Kind;
    protected int m_ChannelCursor;
    protected int m_ListenerCursor;
    protected bool m_Committed;
    protected bool m_AdmissionPrinted;

    static HCRadioChatter Get() { return s_Instance; }

    static float Frequency(string faction)
    {
        if (faction == "locals") { return 87.8; }
        if (faction == "volunteers") { return 89.5; }
        if (faction == "scavengers") { return 91.3; }
        if (faction == "raiders") { return 94.6; }
        if (faction == "travellers") { return 96.6; }
        return 0;
    }

    override string GetName() { return "Radio"; }
    override bool IsEnabled(HCSettings settings) { return settings && settings.EnableLeads; }
    override void OnStart(HCSettings settings)
    {
        if (!IsEnabled(settings) || s_Instance) { return; }
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Radio", true, "EXP-S2", HCV2Gates.Qualified("EXP-S2")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy()) { return; }
        if (m_Store.Data.Channels.Count() == 0)
        {
            array<string> factions = {"locals", "volunteers", "scavengers", "raiders", "travellers"};
            foreach (string faction : factions)
            {
                HCRadioChannel channel = new HCRadioChannel;
                channel.Faction = faction;
                channel.Frequency = Frequency(faction);
                m_Store.Data.Channels.Insert(channel);
            }
            if (!m_Store.Save()) { return; }
        }
        s_Instance = this;
    }

    bool Fallback(HCWorldLead offer)
    {
        if (!m_Store || !m_Store.Healthy() || !HCLeadPolicy.Valid(offer) || m_Fallback.Count() >= 4) { return false; }
        m_Fallback.Insert(HCLeadPolicy.Copy(offer));
        return true;
    }

    bool Receiving(PlayerBase player, float frequency)
    {
        if (!player || !player.IsAlive() || !player.GetIdentity() || !player.GetInventory() || player.GetInventory().CountInventory() > 512) { return false; }
        array<EntityAI> inventory = new array<EntityAI>();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, inventory);
        if (inventory.Count() > 512) { return false; }
        foreach (EntityAI entity : inventory)
        {
            PersonalRadio radio = PersonalRadio.Cast(entity);
            if (!radio || radio.IsRuined() || radio.GetHierarchyRootPlayer() != player || !radio.GetCompEM()) { continue; }
            if (!radio.GetCompEM().IsSwitchedOn() || !radio.GetCompEM().IsWorking() || !radio.IsReceiving()) { continue; }
            float tuned = radio.GetTunedFrequency();
            // Tolerate float representation only, never adjacent channels.
            if (tuned > frequency - 0.01 && tuned < frequency + 0.01) { return true; }
        }
        return false;
    }

    string Chatter(string faction, int sequence)
    {
        if (faction == "locals")
        {
            if (sequence % 4 == 1) { return "Zimovniki: Leave the paths clear. Someone still has to get home."; }
            return "Zimovniki: If the well tastes wrong, boil it. Pass that along.";
        }
        if (faction == "volunteers") { return "Dobrovoltsy: Keep your weapon lowered when approaching strangers. We all want to get through the night."; }
        if (faction == "scavengers") { return "Sborshchiki: Check what you can carry before you open another crate. Nobody is coming with a truck."; }
        if (faction == "raiders") { return "Volki: Short transmissions. No names. Out."; }
        return "Travellers: A dry pair of socks is worth the stop. Take care of your feet.";
    }

    void BeginChannel()
    {
        if (m_Store.Data.Channels.Count() != 5) { return; }
        m_Channel = m_Store.Data.Channels[m_ChannelCursor];
        m_ChannelCursor = (m_ChannelCursor + 1) % 5;
        int now = HCWorldClock.UTC();
        if (now < 1 || now - m_Channel.LastSent < 600) { m_Channel = null; return; }
        GetGame().GetPlayers(m_Listeners);
        // Snapshot roster is capped, one player inventory examined per tick.
        if (m_Listeners.Count() > 32) { m_Listeners.Clear(); m_Channel = null; return; }
        m_ListenerCursor = 0;
        m_Committed = false;
        m_Report = null;
        while (m_Fallback.Count() > 0)
        {
            HCWorldLead queued = m_Fallback[0];
            m_Fallback.RemoveOrdered(0);
            if (queued.Expires > now) { m_Report = queued; break; }
        }
        HCLeadModule leads = HCLeadModule.Get();
        if (!m_Report && leads && m_Channel.Sequence % 2 == 0) { m_Report = leads.Select(); }
        m_Kind = "chatter";
        m_Text = Chatter(m_Channel.Faction, m_Channel.Sequence);
        if (m_Report)
        {
            m_Text = HCLeadPolicy.Text(m_Report);
            m_Kind = "report";
        }
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Store || !m_Store.Healthy()) { return; }
        if (!m_Channel) { BeginChannel(); }
        if (!m_Channel) { return; }
        if (m_ListenerCursor >= m_Listeners.Count())
        {
            if (!m_Committed && m_Report && m_Fallback.Count() < 4) { m_Fallback.Insert(m_Report); }
            m_Channel = null;
            m_Listeners.Clear();
            return;
        }
        PlayerBase listener = PlayerBase.Cast(m_Listeners[m_ListenerCursor++]);
        if (!Receiving(listener, m_Channel.Frequency)) { return; }
        if (m_Report && m_Report.Expires <= HCWorldClock.UTC()) { return; }
        if (!m_Committed)
        {
            // Persist the rate limit before the first recipient; a restart can
            // lose a line, but cannot replay a burst. One line shared by batch.
            m_Channel.LastSent = HCWorldClock.UTC();
            m_Channel.Sequence++;
            if (!m_Store.Save()) { return; }
            m_Committed = true;
            Print("[HollowCountry] V2 radio line freq=" + m_Channel.Frequency.ToString() + " kind=" + m_Kind);
        }
        NotificationSystem.SendNotificationToPlayerExtended(listener, 12, "Radio " + m_Channel.Frequency.ToString() + " MHz", m_Text);
        HCLeadModule leadModule = HCLeadModule.Get();
        if (m_Report && leadModule) { leadModule.ReceivePlayer(m_Report, listener, "radio"); }
    }

    override void OnStop()
    {
        s_Instance = null;
        m_Listeners.Clear();
    }
}
