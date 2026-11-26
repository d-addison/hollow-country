// Native scripts-1.30.164289: 3_Game/gameplay.c:104-117 ScriptRPC/Send (null identity
// broadcasts); 3_Game/Client/Notifications/NotificationSystem.c:141
// SendNotificationToPlayerIdentityExtended; 3_Game/Global/Game.c:914 GetTickTime;
// 3_Game/Global/Game.c GetPlayers; 1_Core/proto/EnMath.c Floor/Cos/Sin/PI2;
// 1_Core/proto/EnString.c:223 Hash; EnConvert.c:30 int.ToString; EnDebug.c:96 Print.
// Operator policy for the public mission map. Optional profile file
// HollowCountry/mission-beacon.json; absent or invalid fields keep these defaults.
// A per-type radius key that is absent follows MissionZoneRadiusMeters; a present value must be
// 50-1500 and anything else is reset to MissionZoneRadiusMeters with the config marked invalid.
class HCMissionBeaconConfig
{
    bool MissionMapMarkers = true;
    bool MissionNotifications = true;
    int MissionZoneRadiusMeters = 250;
    float MissionZoneOffsetFraction = 0.35;
    int MissionNotificationSeconds = 10;
    int MissionMapMaxRows = 8;
    int MissionRadiusRecovery = 250;
    int MissionRadiusDelivery = 250;
    int MissionRadiusInvestigation = 250;
    int MissionRadiusSalvage = 250;
    int MissionRadiusEncounter = 250;
    int MissionRadiusPresence = 250;
    int MissionRadiusInfectedClear = 250;
    protected static ref HCMissionBeaconConfig s_Config;

    bool HCNormalize(string text)
    {
        bool invalid = false;
        if (!HCJsonFields.Has(text, "MissionMapMarkers")) { this.MissionMapMarkers = true; }
        if (!HCJsonFields.Has(text, "MissionNotifications")) { this.MissionNotifications = true; }
        if (!HCJsonFields.Has(text, "MissionZoneRadiusMeters")) { this.MissionZoneRadiusMeters = 250; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionZoneRadiusMeters", this.MissionZoneRadiusMeters)) { this.MissionZoneRadiusMeters = 250; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionZoneOffsetFraction")) { this.MissionZoneOffsetFraction = 0.35; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionZoneOffsetFraction", this.MissionZoneOffsetFraction)) { this.MissionZoneOffsetFraction = 0.35; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionNotificationSeconds")) { this.MissionNotificationSeconds = 10; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionNotificationSeconds", this.MissionNotificationSeconds)) { this.MissionNotificationSeconds = 10; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionMapMaxRows")) { this.MissionMapMaxRows = 8; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionMapMaxRows", this.MissionMapMaxRows)) { this.MissionMapMaxRows = 8; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusRecovery")) { this.MissionRadiusRecovery = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusRecovery", this.MissionRadiusRecovery)) { this.MissionRadiusRecovery = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusDelivery")) { this.MissionRadiusDelivery = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusDelivery", this.MissionRadiusDelivery)) { this.MissionRadiusDelivery = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusInvestigation")) { this.MissionRadiusInvestigation = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusInvestigation", this.MissionRadiusInvestigation)) { this.MissionRadiusInvestigation = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusSalvage")) { this.MissionRadiusSalvage = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusSalvage", this.MissionRadiusSalvage)) { this.MissionRadiusSalvage = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusEncounter")) { this.MissionRadiusEncounter = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusEncounter", this.MissionRadiusEncounter)) { this.MissionRadiusEncounter = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusPresence")) { this.MissionRadiusPresence = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusPresence", this.MissionRadiusPresence)) { this.MissionRadiusPresence = this.MissionZoneRadiusMeters; invalid = true; }
        if (!HCJsonFields.Has(text, "MissionRadiusInfectedClear")) { this.MissionRadiusInfectedClear = this.MissionZoneRadiusMeters; }
        if (!HCOperatorSettingsRegistry.HCValid("Events.MissionRadiusInfectedClear", this.MissionRadiusInfectedClear)) { this.MissionRadiusInfectedClear = this.MissionZoneRadiusMeters; invalid = true; }
        return invalid;
    }

    void HCReport()
    {
        Print("[HC Config] HCMissionBeaconConfig markers=" + MissionMapMarkers.ToString() + " notices=" + MissionNotifications.ToString() + " radius_m=" + MissionZoneRadiusMeters.ToString() + " offset=" + MissionZoneOffsetFraction.ToString() + " seconds=" + MissionNotificationSeconds.ToString() + " rows=" + MissionMapMaxRows.ToString() + " runtime=PENDING");
    }

    // Zone radius in metres for one mission family (always 50-1500).
    int RadiusFor(int family)
    {
        int value = MissionZoneRadiusMeters;
        if (family == HCEventFamily.RECOVERY) { value = MissionRadiusRecovery; }
        else if (family == HCEventFamily.DELIVERY) { value = MissionRadiusDelivery; }
        else if (family == HCEventFamily.INVESTIGATION) { value = MissionRadiusInvestigation; }
        else if (family == HCEventFamily.STATIC_SALVAGE) { value = MissionRadiusSalvage; }
        else if (family == HCEventFamily.AI_ENCOUNTER) { value = MissionRadiusEncounter; }
        else if (family == HCEventFamily.PRESENCE) { value = MissionRadiusPresence; }
        else if (family == HCEventFamily.INFECTED_CLEAR) { value = MissionRadiusInfectedClear; }
        return value;
    }

    // Rows the table and the snapshot may hold (registry range 1-16, wire cap 16).
    int RowCap()
    {
        int cap = MissionMapMaxRows;
        if (cap > HCBeaconWire.MAX_ROWS) { cap = HCBeaconWire.MAX_ROWS; }
        if (cap < 1) { cap = 1; }
        return cap;
    }

    static HCMissionBeaconConfig HCGet()
    {
        if (s_Config) { return s_Config; }
        HCOperatorSettingsRegistry.HCLocalPolicyInit();
        s_Config = new HCMissionBeaconConfig;
        string path = "$profile:HollowCountry/mission-beacon.json";
        if (!FileExist(path)) { s_Config.HCReport(); return s_Config; }
        string text;
        string error;
        HCMissionBeaconConfig loaded;
        if (!HCGroupIO.Read(path, 4096, text) || !JsonFileLoader<HCMissionBeaconConfig>.LoadData(text, loaded, error) || !loaded)
        {
            Print("[HC Config] HCMissionBeaconConfig invalid_json defaults_restored runtime=PENDING");
            s_Config.HCReport();
            return s_Config;
        }
        bool invalid = loaded.HCNormalize(text);
        s_Config = loaded;
        if (invalid) { Print("[HC Config] HCMissionBeaconConfig invalid_range defaults_restored runtime=PENDING"); }
        s_Config.HCReport();
        return s_Config;
    }
}

// One published mission: the zone the players see, never the exact site.
class HCMissionBeaconEntry
{
    string Id;
    string Kind;
    string Title;
    string Place;
    float ZoneX = 0;
    float ZoneZ = 0;
    float Radius = 0;
    float Offset = 0;
    int Expires = 0;
    ref HCReleaseRadius ReleaseRadius = new HCReleaseRadius;
}

// Server owner of the public mission map: derives the public set from the
// committed runtime, keeps a bounded table, pushes full snapshots on change and
// sends bounded toasts. Pure server state; clients only display what is pushed.
// Owned by HCEventModule (created in OnStart, closed in OnStop).
class HCMissionBeacon
{
    // Start/end toast sends per minute across all missions.
    static const int NOTICES_PER_MINUTE = 12;
    static const string ICON = "set:dayz_gui image:icon_flag";
    protected ref HCMissionBeaconConfig m_Config;
    protected ref array<ref HCMissionBeaconEntry> m_Entries = new array<ref HCMissionBeaconEntry>();
    protected ref array<ref HCEventBeaconSource> m_Sources = new array<ref HCEventBeaconSource>();
    protected bool m_Open = false;
    protected float m_Elapsed = 0;
    protected int m_Sequence = 0;
    protected int m_ReleaseRadiusCursor = 0;
    protected int m_LastNow = 0;
    protected float m_LastNowAt = 0;
    protected float m_NoticeWindow = -100;
    protected int m_NoticeCount = 0;
    protected bool m_CapLogged = false;
    protected bool m_FullLogged = false;
    // Connect summaries have their own cap, apart from the start/end toasts: one per
    // identity per minute, at most SUMMARY_TRACKED identities remembered.
    static const int SUMMARY_TRACKED = 64;
    protected ref map<string, float> m_SummaryAt = new map<string, float>();

    void HCOpen()
    {
        m_Config = HCMissionBeaconConfig.HCGet();
        m_Entries.Clear();
        m_Sources.Clear();
        m_Elapsed = 0;
        m_Sequence = 0;
        m_ReleaseRadiusCursor = 0;
        m_NoticeWindow = -100;
        m_NoticeCount = 0;
        m_CapLogged = false;
        m_FullLogged = false;
        m_SummaryAt.Clear();
        m_Open = true;
    }

    // Shutdown: everything ends without toasts; clients get an empty snapshot.
    void HCClose()
    {
        if (!m_Open) { return; }
        m_Open = false;
        bool hadRows = m_Entries.Count() > 0;
        foreach (HCMissionBeaconEntry entry : m_Entries)
        {
            Print("[HC Events] mission ended id=" + entry.Id + " reason=shutdown");
        }
        m_Entries.Clear();
        m_SummaryAt.Clear();
        if (hadRows) { HCBroadcast(); }
    }

    int HCRowCount() { return m_Entries.Count(); }

    static string KindName(int family)
    {
        if (family == HCEventFamily.RECOVERY) { return "recovery"; }
        if (family == HCEventFamily.DELIVERY) { return "delivery"; }
        if (family == HCEventFamily.INVESTIGATION) { return "investigation"; }
        if (family == HCEventFamily.STATIC_SALVAGE) { return "salvage"; }
        if (family == HCEventFamily.AI_ENCOUNTER) { return "encounter"; }
        if (family == HCEventFamily.PRESENCE) { return "presence"; }
        if (family == HCEventFamily.INFECTED_CLEAR) { return "clearing"; }
        return "mission";
    }

    static string TitleFor(int family, bool cache)
    {
        if (family == HCEventFamily.RECOVERY && cache) { return "Supply cache"; }
        if (family == HCEventFamily.RECOVERY) { return "Recover the item"; }
        if (family == HCEventFamily.DELIVERY) { return "Delivery run"; }
        if (family == HCEventFamily.INVESTIGATION) { return "Investigate the site"; }
        if (family == HCEventFamily.STATIC_SALVAGE) { return "Salvage"; }
        if (family == HCEventFamily.AI_ENCOUNTER) { return "Armed encounter"; }
        if (family == HCEventFamily.PRESENCE) { return "Hold the site"; }
        if (family == HCEventFamily.INFECTED_CLEAR) { return "Clear the infected"; }
        return "Field mission";
    }

    static string Pad3(int value)
    {
        string digits = value.ToString();
        while (digits.Length() < 3) { digits = "0" + digits; }
        return digits;
    }

    // Map grid reference of the zone centre (100 m squares), never of the site.
    static string Grid(float x, float z)
    {
        int gridX = Math.Floor(x / 100);
        int gridZ = Math.Floor(z / 100);
        if (gridX < 0) { gridX = 0; }
        if (gridZ < 0) { gridZ = 0; }
        return "grid " + Pad3(gridX) + " " + Pad3(gridZ);
    }

    // Deterministic per-mission zone: the same id always yields the same centre,
    // offset by 30-100 percent of fraction*radius so the circle (radius > offset)
    // always contains the site without revealing its exact spot.
    static void ZoneCentre(string id, vector site, float radius, float fraction, out float zoneX, out float zoneZ, out float offset)
    {
        int hash = id.Hash();
        // Enforce rejects bitwise operators inside a float expression; keep them int-only.
        int lowBits = hash & 65535;
        int highShift = hash >> 16;
        int highBits = highShift & 32767;
        float angle = lowBits / 65536.0 * Math.PI2;
        float unit = highBits / 32767.0;
        offset = radius * fraction * (0.3 + 0.7 * unit);
        zoneX = site[0] + Math.Cos(angle) * offset;
        zoneZ = site[2] + Math.Sin(angle) * offset;
        if (zoneX < 0) { zoneX = 0; }
        if (zoneZ < 0) { zoneZ = 0; }
    }

    static string Minutes(int seconds)
    {
        int minutes = Math.Floor((seconds + 59) / 60);
        if (minutes < 1) { minutes = 1; }
        return minutes.ToString();
    }

    int HCRemaining(HCMissionBeaconEntry entry)
    {
        float since = 0;
        if (GetGame()) { since = GetGame().GetTickTime() - m_LastNowAt; }
        if (since != since || since < 0) { since = 0; }
        int remaining = entry.Expires - m_LastNow - Math.Floor(since);
        if (remaining > HCBeaconWire.MAX_REMAINING) { remaining = HCBeaconWire.MAX_REMAINING; }
        return remaining;
    }

    // One bounded poll every two seconds of committed runtime state, including
    // at most one published radius sample within the shared work-budget unit.
    void HCTick(HCEventRuntime runtime, HCEventContext context, float deltaTime)
    {
        if (!m_Open || !runtime || !context || !context.Server) { return; }
        m_Elapsed = m_Elapsed + deltaTime;
        if (m_Elapsed < 2) { return; }
        HCUnitBudget sharedWork = HCServer.HCTickWork();
        if (!sharedWork || !sharedWork.HCTakeFor(HCUnitBudget.HC_WORK_MISSION_BEACON, 1)) { return; }
        m_Elapsed = 0;
        m_LastNow = context.Now;
        m_LastNowAt = GetGame().GetTickTime();
        int cap = m_Config.RowCap();
        m_Sources.Clear();
        int available = runtime.HCPublicMissions(m_Sources, cap + 1, context.Now);
        bool changed = false;
        int index = m_Entries.Count() - 1;
        while (index >= 0)
        {
            ref HCMissionBeaconEntry present = m_Entries[index];
            // Direct runtime check, never membership of the truncated source list.
            if (!runtime.HCIsPublic(present.Id, context.Now))
            {
                string reason = runtime.HCMissionOutcome(present.Id);
                m_Entries.RemoveOrdered(index);
                HCLogEnded(present.Id, reason);
                HCNoticeEnded(present, reason);
                changed = true;
            }
            index--;
        }
        foreach (HCEventBeaconSource source : m_Sources)
        {
            if (HCHeld(source.Id)) { continue; }
            if (m_Entries.Count() >= cap)
            {
                if (!m_FullLogged)
                {
                    m_FullLogged = true;
                    HCLogFull(cap, source.Id);
                }
                continue;
            }
            HCPublish(source, context);
            changed = true;
        }
        if (available <= cap) { m_FullLogged = false; }
        if (changed) { HCBroadcast(); }
        HCSampleReleaseRadius();
    }

    protected void HCSampleReleaseRadius()
    {
        if (!m_Config.MissionMapMarkers || m_Entries.Count() == 0) { return; }
        if (m_ReleaseRadiusCursor >= m_Entries.Count()) { m_ReleaseRadiusCursor = 0; }
        HCMissionBeaconEntry entry = m_Entries[m_ReleaseRadiusCursor];
        m_ReleaseRadiusCursor++;
        vector centre = Vector(entry.ZoneX, 0, entry.ZoneZ);
        entry.ReleaseRadius.HCSample(centre, entry.Radius, HCReleaseRadiusWire.MISSION);
    }

    // One line per mission end, at most the table cap per poll.
    protected void HCLogEnded(string id, string reason)
    {
        Print("[HC Events] mission ended id=" + id + " reason=" + reason);
    }

    // Latched by m_FullLogged: one line per overflow episode.
    protected void HCLogFull(int cap, string id)
    {
        Print("[HC Events] mission map table full cap=" + cap.ToString() + " refused id=" + id + " reason=table_full");
    }

    protected bool HCHeld(string id)
    {
        foreach (HCMissionBeaconEntry entry : m_Entries)
        {
            if (entry.Id == id) { return true; }
        }
        return false;
    }

    protected void HCPublish(HCEventBeaconSource source, HCEventContext context)
    {
        HCMissionBeaconEntry entry = new HCMissionBeaconEntry;
        entry.Id = source.Id;
        entry.Kind = KindName(source.Family);
        entry.Title = TitleFor(source.Family, source.Cache);
        entry.Radius = m_Config.RadiusFor(source.Family);
        float zoneX;
        float zoneZ;
        float offset;
        ZoneCentre(source.Id, source.Source, entry.Radius, m_Config.MissionZoneOffsetFraction, zoneX, zoneZ, offset);
        entry.ZoneX = zoneX;
        entry.ZoneZ = zoneZ;
        entry.Offset = offset;
        entry.Place = Grid(zoneX, zoneZ);
        entry.Expires = source.Expires;
        m_Entries.Insert(entry);
        int players = HCPlayerCount();
        int radiusMeters = Math.Floor(entry.Radius);
        int offsetMeters = Math.Floor(entry.Offset);
        Print("[HC Events] mission public id=" + entry.Id + " kind=" + entry.Kind + " radius=" + radiusMeters.ToString() + " offset=" + offsetMeters.ToString() + " players=" + players.ToString());
        if (m_Config.MissionMapMarkers) { HCModuleReadiness.HCUse("Events", "mission_marker"); }
        string detail = entry.Place;
        if (m_Config.MissionMapMarkers) { detail = detail + ", zone marked on your map"; }
        detail = detail + ", ends in " + Minutes(HCRemaining(entry)) + " min";
        HCNotice("Mission: " + entry.Title, detail, players);
    }

    protected void HCNoticeEnded(HCMissionBeaconEntry entry, string reason)
    {
        string detail = "The zone is cleared from your map.";
        if (!m_Config.MissionMapMarkers) { detail = "The mission is over."; }
        if (reason == "completed") { detail = "Completed. " + detail; }
        else if (reason == "expired") { detail = "Time ran out. " + detail; }
        HCNotice("Mission ended: " + entry.Title, detail, HCPlayerCount());
    }

    protected int HCPlayerCount()
    {
        if (!GetGame()) { return 0; }
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        int counted = 0;
        foreach (Man man : players)
        {
            if (man && man.GetIdentity()) { counted = counted + 1; }
        }
        return counted;
    }

    // At most NOTICES_PER_MINUTE toast sends per minute; the cap only drops toasts,
    // the map rows still publish.
    protected bool HCNoticeAllowed()
    {
        float now = GetGame().GetTickTime();
        if (now < m_NoticeWindow || now - m_NoticeWindow >= 60)
        {
            m_NoticeWindow = now;
            m_NoticeCount = 0;
            m_CapLogged = false;
        }
        if (m_NoticeCount >= NOTICES_PER_MINUTE)
        {
            if (!m_CapLogged)
            {
                m_CapLogged = true;
                Print("[HC Events] mission notices capped per_minute=" + NOTICES_PER_MINUTE.ToString() + " reason=notice_rate");
            }
            return false;
        }
        m_NoticeCount = m_NoticeCount + 1;
        return true;
    }

    // One summary toast per identity per minute; does not draw on the start/end toast cap.
    protected bool HCSummaryAllowed(PlayerIdentity identity)
    {
        string key = identity.GetId();
        float now = GetGame().GetTickTime();
        float last = 0;
        if (m_SummaryAt.Find(key, last) && now >= last && now - last < 60) { return false; }
        if (m_SummaryAt.Count() >= SUMMARY_TRACKED && !m_SummaryAt.Contains(key))
        {
            for (int index = m_SummaryAt.Count() - 1; index >= 0; index--)
            {
                float stamp = m_SummaryAt.GetElement(index);
                if (now < stamp || now - stamp >= 60) { m_SummaryAt.RemoveElement(index); }
            }
            if (m_SummaryAt.Count() >= SUMMARY_TRACKED) { return false; }
        }
        m_SummaryAt.Set(key, now);
        return true;
    }

    // One vanilla toast broadcast to every connected player.
    protected void HCNotice(string title, string detail, int players)
    {
        if (!m_Config.MissionNotifications || players <= 0) { return; }
        if (!HCNoticeAllowed()) { return; }
        NotificationSystem.SendNotificationToPlayerIdentityExtended(null, m_Config.MissionNotificationSeconds, title, detail, ICON);
        HCModuleReadiness.HCUse("Events", "mission_notice");
    }

    protected void HCWriteSnapshot(ScriptRPC rpc)
    {
        int count = 0;
        if (m_Config.MissionMapMarkers) { count = m_Entries.Count(); }
        rpc.Write(HCBeaconWire.VERSION);
        rpc.Write(m_Sequence);
        rpc.Write(count);
        if (count == 0) { return; }
        foreach (HCMissionBeaconEntry entry : m_Entries)
        {
            int remaining = HCRemaining(entry);
            if (remaining < 1) { remaining = 1; }
            rpc.Write(entry.Id);
            rpc.Write(entry.Kind);
            rpc.Write(entry.Title);
            rpc.Write(entry.Place);
            rpc.Write(entry.ZoneX);
            rpc.Write(entry.ZoneZ);
            rpc.Write(entry.Radius);
            rpc.Write(remaining);
        }
    }

    // Full snapshot to every connected client (one reliable send).
    protected void HCBroadcast()
    {
        m_Sequence = m_Sequence + 1;
        ScriptRPC rpc = new ScriptRPC;
        HCWriteSnapshot(rpc);
        rpc.Send(null, HCBeaconWire.RPC_PUBLIC, true, null);
    }

    // Connect/respawn path: the current list once, and at most one summary toast
    // when the player is in the world (never one per earlier announcement).
    void HCConnected(PlayerIdentity identity, bool inWorld)
    {
        if (!m_Open || !identity) { return; }
        if (m_Entries.Count() == 0 && m_Sequence == 0) { return; }
        ScriptRPC rpc = new ScriptRPC;
        HCWriteSnapshot(rpc);
        rpc.Send(null, HCBeaconWire.RPC_PUBLIC, true, identity);
        if (!inWorld || !m_Config.MissionMapMarkers || !m_Config.MissionNotifications || m_Entries.Count() == 0) { return; }
        if (!HCSummaryAllowed(identity)) { return; }
        string text = m_Entries.Count().ToString() + " active missions marked on your map";
        if (m_Entries.Count() == 1) { text = "1 active mission marked on your map"; }
        NotificationSystem.SendNotificationToPlayerIdentityExtended(identity, m_Config.MissionNotificationSeconds, "Missions", text, ICON);
        HCModuleReadiness.HCUse("Events", "mission_notice");
    }
}
