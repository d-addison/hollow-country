// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:917/926 map.Contains/Insert.
// Optional tuning only; absent keys retain declared defaults (native JSON zero-fills).
// Native scripts-1.30.164289: 1_Core/proto/EnSystem.c:397 FileExist;
// 3_Game/tools/JsonFileLoader.c:69 LoadData; 1_Core/proto/EnDebug.c:96 Print.
// HCGroupIO.Read owns bounded native file IO; HCJsonFields owns key presence.
// Native 1_Core/proto/EnScript.c:380 Count, :394 Find, :407 Insert.
class HCRadioDefaults
{
    float ReportRangeMetres = 1000.0;
    int MaxListeners = 32;
    int ChannelCountLimit = 64;
    float LocalsMHz = 87.8;
    float VolunteersMHz = 89.5;
    float ScavengersMHz = 91.3;
    float RaidersMHz = 94.6;
    float TravellersMHz = 96.6;
    int BroadcastGapSeconds = 600;
    protected static ref HCRadioDefaults s_Config;

    // Validates a supplied candidate list only; no inspected native channel
    // catalogue is available. This helper is not a startup prerequisite.
    bool HCQualifyChannels(array<float> channels)
    {
        if (!channels || channels.Count() < 1 || channels.Count() > this.ChannelCountLimit) { return false; }
        map<float, bool> seen = new map<float, bool>;
        foreach (float frequency : channels)
        {
            if (!(frequency >= 87.8 && frequency <= 102.5) || seen.Contains(frequency)) { return false; }
            seen.Insert(frequency, true);
        }
        bool restored = false;
        if (channels.Find(this.LocalsMHz) < 0)
        {
            if (channels.Find(87.8) < 0) { return false; }
            this.LocalsMHz = 87.8;
            restored = true;
        }
        if (channels.Find(this.VolunteersMHz) < 0)
        {
            if (channels.Find(89.5) < 0) { return false; }
            this.VolunteersMHz = 89.5;
            restored = true;
        }
        if (channels.Find(this.ScavengersMHz) < 0)
        {
            if (channels.Find(91.3) < 0) { return false; }
            this.ScavengersMHz = 91.3;
            restored = true;
        }
        if (channels.Find(this.RaidersMHz) < 0)
        {
            if (channels.Find(94.6) < 0) { return false; }
            this.RaidersMHz = 94.6;
            restored = true;
        }
        if (channels.Find(this.TravellersMHz) < 0)
        {
            if (channels.Find(96.6) < 0) { return false; }
            this.TravellersMHz = 96.6;
            restored = true;
        }
        if (restored) { Print("[HC Config] HCRadioDefaults unsupported_frequency defaults_restored runtime=PENDING"); }
        return true;
    }

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "ReportRangeMetres")) { this.ReportRangeMetres = 1000.0; }
        if (!(this.ReportRangeMetres >= 1 && this.ReportRangeMetres <= 1000)) { this.ReportRangeMetres = 1000.0; invalid = true; }
        if (!HCJsonFields.Has(text, "ChannelCountLimit")) { this.ChannelCountLimit = 64; }
        if (!(this.ChannelCountLimit >= 1 && this.ChannelCountLimit <= 64)) { this.ChannelCountLimit = 64; invalid = true; }
        if (!HCJsonFields.Has(text, "MaxListeners")) { this.MaxListeners = 32; }
        if (!(this.MaxListeners >= 1 && this.MaxListeners <= 32)) { this.MaxListeners = 32; invalid = true; }
        if (!HCJsonFields.Has(text, "LocalsMHz")) { this.LocalsMHz = 87.8; }
        if (!(this.LocalsMHz >= 87.8 && this.LocalsMHz <= 102.5)) { this.LocalsMHz = 87.8; invalid = true; }
        if (!HCJsonFields.Has(text, "VolunteersMHz")) { this.VolunteersMHz = 89.5; }
        if (!(this.VolunteersMHz >= 87.8 && this.VolunteersMHz <= 102.5)) { this.VolunteersMHz = 89.5; invalid = true; }
        if (!HCJsonFields.Has(text, "ScavengersMHz")) { this.ScavengersMHz = 91.3; }
        if (!(this.ScavengersMHz >= 87.8 && this.ScavengersMHz <= 102.5)) { this.ScavengersMHz = 91.3; invalid = true; }
        if (!HCJsonFields.Has(text, "RaidersMHz")) { this.RaidersMHz = 94.6; }
        if (!(this.RaidersMHz >= 87.8 && this.RaidersMHz <= 102.5)) { this.RaidersMHz = 94.6; invalid = true; }
        if (!HCJsonFields.Has(text, "TravellersMHz")) { this.TravellersMHz = 96.6; }
        if (!(this.TravellersMHz >= 87.8 && this.TravellersMHz <= 102.5)) { this.TravellersMHz = 96.6; invalid = true; }
        if (!HCJsonFields.Has(text, "BroadcastGapSeconds")) { this.BroadcastGapSeconds = 600; }
        if (!(this.BroadcastGapSeconds >= 60 && this.BroadcastGapSeconds <= 86400)) { this.BroadcastGapSeconds = 600; invalid = true; }
        return invalid;
    }
    // Translate persisted channel identity to operator-selected receive frequency.
    static float Tuned(float canonical)
    {
        if (canonical == 87.8) { return HCRadioDefaults.Get().LocalsMHz; }
        if (canonical == 89.5) { return HCRadioDefaults.Get().VolunteersMHz; }
        if (canonical == 91.3) { return HCRadioDefaults.Get().ScavengersMHz; }
        if (canonical == 94.6) { return HCRadioDefaults.Get().RaidersMHz; }
        if (canonical == 96.6) { return HCRadioDefaults.Get().TravellersMHz; }
        return 0;
    }

    static HCRadioDefaults Get()
    {
        if (s_Config) { return s_Config; }
        s_Config = new HCRadioDefaults;
        string path = "$profile:HollowCountry/radio.json";
        if (!FileExist(path)) { return s_Config; }
        string text;
        string error;
        HCRadioDefaults loaded;
        if (!HCGroupIO.Read(path, 16384, text) || !JsonFileLoader<HCRadioDefaults>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCRadioDefaults invalid_json defaults_restored runtime=PENDING");
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCRadioDefaults invalid_range defaults_restored runtime=PENDING"); }
        return s_Config;
    }
}

// HC-20 / #148: radio text is a retained environmental clue. Morse is folded
// into the same delayed shared fact path, never a live event/player lookup.
// Native evidence, scripts-1.30.164289:
// 4_World/Entities/Core/Inherited/InventoryItem.c:14,18,22 PersonalRadio base,
// GetTunedFrequency/IsReceiving; Entities/ItemBase/TransmitterBase/PersonalRadio.c:1;
// Entities/ItemBase/TransmitterBase.c:96,107 powered receive lifecycle;
// Entities/ManBase/PlayerBase.c:2638,6733 IsPlayerDisconnected/GetItemInHands;
// 3_Game/Entities/EntityAI.c:882,3409 root custody/GetCompEM;
// 3_Game/Entities/Object.c:215,287,517,1219 deletion/position/alive/ruined;
// 3_Game/Entities/Man.c:21 GetIdentity; gameplay.c:368 identity GetId;
// 3_Game/tools/Component/ComponentEnergyManager.c:884,925 switch/work;
// 3_Game/Systems/DynamicMusicPlayer/DynamicMusicPlayer.c:210-211 flat vector;
// 3_Game/Global/Game.c:1120 IsServer; 1_Core/proto/EnConvert.c:210 DistanceSq;
// EnConvert.c:30,115 int/float.ToString;
// 3_Game/Client/Notifications/NotificationSystem.c:141 identity-targeted notification;
// 1_Core/proto/EnString.c:199,223 Length/Hash; EnScript.c:94 Cast,
// :380,385,407,470 Count/Clear/Insert/RemoveOrdered; EnDebug.c:96 Print.
// HCPerfPlayers and HCWorkBudget own inspected native roster/time operations.


class HCRadioChatter : HCModule
{
    protected static HCRadioChatter s_Instance;
    protected ref HCLeadStore m_Store;
    protected ref HCMorseRateStore m_LegacyRates;
    protected ref HCRadioDefaults m_Defaults = new HCRadioDefaults;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_UnitBudget = new HCUnitBudget;
    protected ref HCWorkBudget m_WorkBudget = new HCWorkBudget;
    protected ref array<Man> m_Listeners = new array<Man>();
    protected ref array<ref HCWorldLead> m_Fallback = new array<ref HCWorldLead>();
    protected ref array<ref HCWorldFact> m_Facts = new array<ref HCWorldFact>();
    protected ref HCWorldLead m_Report;
    protected HCRadioChannel m_Channel;
    protected string m_Text;
    protected int m_ChannelCursor;
    protected int m_ListenerCursor;
    protected int m_Reports;
    protected int m_Recipients;
    protected float m_Elapsed = 60;
    protected bool m_Committed;
    protected int m_ChannelReceipt = -1;
    protected bool m_ReceiptPending;
    protected bool m_FromFallback;
    protected bool m_Ready;
    protected bool m_AdmissionPrinted;
    protected string m_Refusal;

    static HCRadioChatter Get() { return s_Instance; }

    // Persisted channel identity: HCLeadStore validates these schema values.
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
    override bool IsEnabled(HCSettings settings)
    {
        bool enabled = settings && settings.EnableLeads;
        if (!enabled)
        {
            m_Status.HCPublish("off", "leads_disabled");
            Print("[HC Plan] HC-20 radio=off morse=folded reports=0 reason=leads_disabled runtime=PENDING");
        }
        return enabled;
    }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    // Non-terminal refusal: publishes the HC-1 status every call and keeps the radio
    // running; the log line prints once per reason change (BeginChannel retries each minute).
    string Refusal() { return m_Refusal; }
    bool HCRefuseAs(string state, string reason)
    {
        m_Status.HCPublish(state, reason);
        if (m_Refusal != reason)
        {
            m_Refusal = reason;
            Print("[HC Plan] HC-20 radio=" + state + " morse=folded reports=" + m_Reports.ToString() + " reason=" + reason + " runtime=PENDING");
        }
        return false;
    }

    override void OnStart(HCSettings settings)
    {
        if (!settings || !settings.EnableLeads || s_Instance || !GetGame().IsServer()) { return; }
        m_Defaults = HCRadioDefaults.Get();
        // Installed vanilla PersonalRadio config has no frequencies property.
        // Keep validated operator tuning; numeric validation does not establish
        // native channel membership. Store health still controls readiness.
        Print("[HC Radio] frequencies=configured native_membership=unobserved runtime=PENDING");
        m_Status.HCPublish("refused", "lead_store_unavailable");
        if (!m_AdmissionPrinted)
        {
            Print(HCV2Admission.Line("Radio", true, "EXP-S2", HCV2Gates.Qualified("EXP-S2")));
            m_AdmissionPrinted = true;
        }
        m_Store = HCLeadStore.Get();
        if (!m_Store || !m_Store.Healthy())
        {
            Print("[HC Plan] HC-20 radio=refused morse=folded reports=0 reason=lead_store_unavailable runtime=PENDING");
            return;
        }
        m_LegacyRates = new HCMorseRateStore;
        // The retired ledger is advisory migration input. Its own one-line
        // fault diagnostic leaves ordinary shared channel receipts authoritative.
        m_LegacyRates.Open();
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
            if (!m_Store.Save())
            {
                HCRefuse("channel_store_save_failed");
                return;
            }
        }
        m_Ready = true;
        s_Instance = this;
        m_Status.HCPublish("ready", "environmental_facts_admitted_native_link_unobserved");
        Print("[HC Plan] HC-20 radio=environmental morse=folded reports=0 state=ready recipients=0 runtime=PENDING");
        // IsReceiving is a receiver switch, not an acknowledgment of a native
        // source-to-recipient link. No inspected transmitter method proves it.
        Print("[HC Plan] HC-20 refusal=native_radio_link_unobserved transport=native_notification range=fact_place runtime=PENDING");
    }

    bool Fallback(HCWorldLead offer)
    {
        // A failed physical note is not evidence of an event. Only already
        // delayed shared world facts may enter the ordinary report queue.
        if (!m_Ready || !m_Store || !m_Store.Healthy() || !HCLeadPolicy.Valid(offer) || m_Fallback.Count() >= 4) { return false; }
        if (offer.Source != "world")
        {
            Print("[HC Plan] HC-20 refusal=unproven_fallback morse=folded runtime=PENDING");
            return false;
        }
        m_Fallback.Insert(HCLeadPolicy.Copy(offer));
        return true;
    }

    bool Receiving(PlayerBase player, float frequency)
    {
        if (!player || !player.IsAlive() || player.IsPendingDeletion() || player.IsPlayerDisconnected() || !player.GetIdentity()) { return false; }
        // Held means actually in hands: a quickbar assignment does not establish
        // custody outside cargo, and stored/attached radios cannot receive text.
        PersonalRadio radio = PersonalRadio.Cast(player.GetItemInHands());
        if (!radio || radio.IsPendingDeletion() || radio.IsRuined() || radio.GetHierarchyRootPlayer() != player || !radio.GetCompEM()) { return false; }
        if (!radio.GetCompEM().IsSwitchedOn() || !radio.GetCompEM().IsWorking() || !radio.IsReceiving()) { return false; }
        float tuned = radio.GetTunedFrequency();
        // Retained representation tolerance, never adjacent channels.
        return tuned > frequency - 0.01 && tuned < frequency + 0.01;
    }

    bool InReportRange(PlayerBase player, HCWorldLead report)
    {
        if (!player || !HCLeadPolicy.Valid(report) || report.Source != "world" || !(m_Defaults.ReportRangeMetres > 0)) { return false; }
        HCWorldPlace place = HCLeadPolicy.Place(report.TargetPlaceId);
        if (!place) { return false; }
        // Authored place height is not terrain height: range is horizontal.
        vector listenerPosition = player.GetPosition();
        vector placePosition = place.Position;
        listenerPosition[1] = 0;
        placePosition[1] = 0;
        float distanceSq = vector.DistanceSq(listenerPosition, placePosition);
        return distanceSq >= 0 && distanceSq <= m_Defaults.ReportRangeMetres * m_Defaults.ReportRangeMetres;
    }

    bool HasListener(HCWorldLead report)
    {
        foreach (Man candidateListener : m_Listeners)
        {
            PlayerBase player = PlayerBase.Cast(candidateListener);
            if (Receiving(player, HCRadioDefaults.Tuned(m_Channel.Frequency)) && InReportRange(player, report)) { return true; }
        }
        return false;
    }

    HCWorldLead LatestInRange()
    {
        HCWorldModule world = HCWorldModule.Get();
        if (!world) { return null; }
        // Shared history is bounded and newest-first. At most 32 candidate facts
        // and MaxListeners retained players are considered per channel start.
        world.GetRecentFacts(604800, m_Facts);
        int now = HCWorldClock.UTC();
        int checked;
        foreach (HCWorldFact fact : m_Facts)
        {
            checked = checked + 1;
            if (checked > 32) { break; }
            HCWorldLead candidate = new HCWorldLead;
            if (!HCLeadPolicy.Build(fact, candidate, fact.PlaceId, HCLeadPolicy.Kind(fact.Kind), now) || !HCLeadPolicy.Valid(candidate)) { continue; }
            candidate.Id = fact.Kind + "-" + fact.PlaceId + "-" + fact.At.ToString();
            candidate.Source = "world";
            if (HasListener(candidate)) { return candidate; }
        }
        return null;
    }

    void BeginChannel()
    {
        if (m_Store.Data.Channels.Count() != 5)
        {
            HCRefuseAs("degraded", "channel_roster_invalid");
            return;
        }
        m_Channel = m_Store.Data.Channels[m_ChannelCursor];
        m_ChannelCursor = (m_ChannelCursor + 1) % 5;
        int now = HCWorldClock.UTC();
        if (now < 1 || m_Channel.LastSent > now || now - m_Channel.LastSent < HCRadioDefaults.Get().BroadcastGapSeconds || m_Channel.Sequence >= 2147483647)
        {
            m_Status.HCPublish("ready", "channel_cooldown_or_clock");
            m_Channel = null;
            return;
        }
        // Only a channel that passed the roster, cooldown and clock checks ends a standing refusal.
        m_Refusal = "";
        array<Man> roster = HCPerfPlayers.HCGet();
        m_Listeners.Clear();
        if (roster.Count() > m_Defaults.MaxListeners)
        {
            Print("[HC Plan] HC-20 radio=refused morse=folded reports=" + m_Reports.ToString() + " recipients=0 reason=listener_cap runtime=PENDING");
            m_Channel = null;
            return;
        }
        foreach (Man listener : roster) { m_Listeners.Insert(listener); }
        m_Report = null;
        m_FromFallback = false;
        // Only note-origin fallback entries may survive a channel attempt.
        // Scan the initial bounded queue once; distant notes cannot block facts.
        int queuedCount = m_Fallback.Count();
        while (queuedCount > 0)
        {
            queuedCount = queuedCount - 1;
            HCWorldLead queued = m_Fallback[0];
            m_Fallback.RemoveOrdered(0);
            if (!HCLeadPolicy.Valid(queued) || queued.Expires <= now || queued.Source != "world") { continue; }
            if (!HasListener(queued)) { m_Fallback.Insert(queued); continue; }
            m_Report = queued;
            m_FromFallback = true;
            break;
        }
        if (!m_Report) { m_Report = LatestInRange(); }
        // No canned NPC advice, briefing or notification when no fact exists.
        if (!m_Report || !HCLeadPolicy.Valid(m_Report) || m_Report.Source != "world" || m_Report.Expires <= now)
        {
            m_Status.HCPublish("ready", "no_in_range_fact");
            m_Channel = null;
            return;
        }
        m_Text = HCLeadPolicy.Text(m_Report);
        if (m_Report.TextId == "morse_lead")
        {
            HCWorldPlace place = HCLeadPolicy.Place(m_Report.TargetPlaceId);
            if (!place) { m_Status.HCPublish("ready", "fact_place_unavailable"); m_Channel = null; return; }
            m_Text = "An earlier event was reported near " + place.Name + ". This is old news; things may have changed.";
        }
        m_ListenerCursor = 0;
        m_Recipients = 0;
        m_Committed = false;
        m_ChannelReceipt = -1;
    }

    bool RetainReport(HCWorldLead report, PlayerBase listener)
    {
        HCLeadModule leads = HCLeadModule.Get();
        if (!leads || !listener || !listener.GetIdentity()) { return false; }
        // ReceivePlayer has a void return. Reuse its authoritative membership
        // resolver and Receive barrier so a failed receipt never displays text.
        HCGroupService groups = HCGroupService.Get();
        string groupId = HCLeadPolicy.SoloGroup(listener.GetIdentity().GetId());
        if (groups) { groupId = groups.HCLeadGroup(listener); }
        if (groupId == "") { return false; }
        int result = leads.ReceiveResult(report, groupId, "radio");
        m_ReceiptPending = result == HCLeadReceiveResult.PENDING;
        return result == HCLeadReceiveResult.RETAINED;
    }

    void HCRefuse(string reason)
    {
        m_Ready = false;
        s_Instance = null;
        m_Channel = null;
        m_Report = null;
        m_Listeners.Clear();
        m_Fallback.Clear();
        m_Facts.Clear();
        m_FromFallback = false;
        m_Status.HCPublish("refused", reason);
        Print("[HC Plan] HC-20 radio=refused morse=folded reports=" + m_Reports.ToString() + " reason=" + reason + " runtime=PENDING");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Ready || !(deltaTime > 0) || !GetGame().IsServer()) { return; }
        if (!m_Store || !m_Store.Healthy()) { HCRefuse("lead_store_fault"); return; }
        m_UnitBudget.HCReset(1);
        m_WorkBudget.HCReset(1);
        if (!m_UnitBudget.HCTake(1) || !m_WorkBudget.HCContinue()) { return; }
        if (!m_Channel)
        {
            m_Elapsed += deltaTime;
            if (m_Elapsed < 60) { return; }
            m_Elapsed = 0;
            BeginChannel();
        }
        if (!m_Channel) { return; }
        HCReached.Mark("radio.channel");
        if (m_ListenerCursor >= m_Listeners.Count())
        {
            if (m_FromFallback && !m_Committed && m_Report && m_Fallback.Count() < 4) { m_Fallback.Insert(m_Report); }
            m_Channel = null;
            m_Report = null;
            m_Listeners.Clear();
            return;
        }
        // Retained finite roster: late join never joins an in-flight report.
        PlayerBase listener = PlayerBase.Cast(m_Listeners[m_ListenerCursor]);
        m_ListenerCursor = m_ListenerCursor + 1;
        if (!Receiving(listener, HCRadioDefaults.Tuned(m_Channel.Frequency)) || !InReportRange(listener, m_Report)) { return; }
        int now = HCWorldClock.UTC();
        if (now < 1 || m_Report.Expires <= now) { return; }
        PlayerIdentity identity = listener.GetIdentity();
        if (!identity || identity.GetId().Length() < 1 || identity.GetId().Length() > 96) { return; }
        if (!m_LegacyRates.Allowed(identity.GetId().Hash(), now)) { return; }
        if (!m_Committed)
        {
            // Keep this roster cursor until the channel receipt has committed.
            // A crash may lose text, but cannot replay a channel cooldown.
            if (m_ChannelReceipt < 0)
            {
                m_Channel.LastSent = now;
                m_Channel.Sequence = m_Channel.Sequence + 1;
                m_ChannelReceipt = m_Store.HCRequestBarrier();
                if (m_ChannelReceipt < 0) { HCRefuse("channel_receipt_fault"); return; }
            }
            if (!m_Store.HCDurable(m_ChannelReceipt)) { m_ListenerCursor--; return; }
            m_Committed = true;
            if (m_Reports < 2147483647) { m_Reports = m_Reports + 1; }
        }
        m_ReceiptPending = false;
        if (!RetainReport(m_Report, listener))
        {
            if (m_ReceiptPending) { m_ListenerCursor--; }
            if (!m_Store.Healthy()) { HCRefuse("lead_receipt_fault"); }
            return;
        }
        // Revalidate after both durable receipts. Never pass a null identity
        // to native notification: null there means ALL players, not a refusal.
        if (listener.GetIdentity() != identity || !Receiving(listener, HCRadioDefaults.Tuned(m_Channel.Frequency)) || !InReportRange(listener, m_Report) || m_Report.Expires <= HCWorldClock.UTC()) { return; }
        float receiveFrequency = HCRadioDefaults.Tuned(m_Channel.Frequency);
        NotificationSystem.SendNotificationToPlayerIdentityExtended(identity, 12, "Radio " + receiveFrequency.ToString() + " MHz", m_Text);
        m_Recipients = m_Recipients + 1;
        Print("[HC Plan] HC-20 radio=environmental morse=folded reports=" + m_Reports.ToString() + " state=ready recipients=" + m_Recipients.ToString() + " runtime=PENDING");
    }

    override void OnStop()
    {
        s_Instance = null;
        m_Ready = false;
        m_Channel = null;
        m_Report = null;
        m_Store = null;
        m_LegacyRates = null;
        m_Listeners.Clear();
        m_Fallback.Clear();
        m_Facts.Clear();
        m_FromFallback = false;
        m_ChannelCursor = 0;
        m_ListenerCursor = 0;
        m_Elapsed = 60;
        m_Reports = 0;
        m_Recipients = 0;
        m_Committed = false;
        m_ChannelReceipt = -1;
        m_Text = "";
        m_Status.HCPublish("off", "server_stopped");
    }
}
