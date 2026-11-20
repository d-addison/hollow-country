// LC-T501 / EXP-POL-1. HC-27 coordinator owns effective settings and lifecycle.
// Installed scripts-1.30.164289 native evidence (paths relative to that dump):
// 3_Game/Client/Notifications/NotificationSystem.c:104,215 GetInstance/AddNotificationExtended.
// 3_Game/DayZGame.c:2178 GetDatabaseID (native character id, also used by analytics at :1557).
// 4_World/Entities/ManBase/PlayerBase.c:1088 GetBleedingBits, :2987 GetVirtualHud,
// :8215 GetStatEnergy, :8224 GetStatHeatComfort, :8242 GetStatWet.
// Those three stats are EPSstatsFlags.EMPTY in Classes/PlayerStats/PlayerStatsPCO.c:339-343;
// read their native replicated HUD levels, not stale client PlayerStat defaults:
// 4_World/Classes/VirtualHud/DisplayStatus.c:96,228 GetElement/client OnRPC;
// DisplayElementBase.c:55 GetValue; DisplayElementTendency.c:4,25 seriousness is value >> 3.
// 4_World/Classes/PlayerNotifiers/Notifiers/HungerNotfr.c:23-29 maps native energy;
// WarmthNotfr.c:24-34,65 maps native heat comfort to DSLevelsTemp;
// 4_World/Classes/Environment/Environment.c:461-471 maps native wet stat to wet badge.
// 3_Game/Entities/EntityAI.c:1897,2169 FindAttachmentBySlotName/GetWet;
// 4_World/Entities/ItemBase.c:190,3721 wetness sync and GetWet override.
// 3_Game/constants.c:934 STATE_SOAKING_WET. Check clothing to distinguish soaked from damp.
// 3_Game/Global/Game.c:943,944,1120 GetUIManager/GetPlayer/IsServer;
// 3_Game/tools/UIManager.c:59 GetMenu; Entities/Object.c:517 IsAlive;
// 4_World/Entities/ManBase/PlayerBase.c:3925 IsUnconscious.
// 3_Game/tools/JsonFileLoader.c:69,85 LoadData/MakeData;
// 1_Core/proto/EnSystem.c:397,525,528,531 FileExist/MakeDirectory/DeleteFile/CopyFile.
// 1_Core/proto/EnString.c:113,199,286 Substring/Length/Contains; EnConvert.c:30 int.ToString;
// 1_Core/proto/EnDebug.c:96 Print; 3_Game/DayZGame.c:4076 GetDayZGame; gameplay.c:636 GetGame.
// 5_Mission/mission/missionGameplay.c:102,266,287 OnInit/OnMissionFinish/OnUpdate.
// Existing project ports: HCGroupIO (bounded read/write with readback).
// Group gameplay uses UAMapToggle; the retired event input is no longer bound.
// First hour means accumulated playtime since this client first sees this character.
// API presence is source evidence only; native compile, reconnect and EXP-POL-1 pending.
class HCHintState
{
    int SchemaVersion;
    string CharacterId;
    int ShownBits = -1;
    float PlayedSeconds = -1;
    float NextHintSecond = -1;
}

// Character-local startup cache: discard only after the old character's save drains.
class HCHintLoad
{
    ref HCHintState State;
    string Path;
    bool NewState;
    protected bool m_Attempted;
    protected bool m_Valid;

    bool Valid(HCHintState state, string characterId)
    {
        bool matching = state && state.SchemaVersion == 1;
        if (!matching) { return false; }
        bool characterValid = state.CharacterId == characterId;
        bool bitsValid = state.ShownBits >= 0 && state.ShownBits <= HCHints.HCAllShownMask();
        bool playedValid = state.PlayedSeconds >= 0 && state.PlayedSeconds < 2147480000;
        bool nextValid = state.NextHintSecond >= 0 && state.NextHintSecond <= state.PlayedSeconds + 180;
        return characterValid && bitsValid && playedValid && nextValid;
    }

    bool Open(string characterId)
    {
        // One startup read per character session; failures are retained, never retried.
        if (m_Attempted) { return m_Valid; }
        m_Attempted = true;
        m_Valid = HCLoad(characterId);
        return m_Valid;
    }

    protected bool HCLoad(string characterId)
    {
        // No account fallback: it would collapse distinct lives into one record.
        if (characterId.Length() < 1 || characterId.Length() > 128) return false;
        string safe = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_";
        for (int i = 0; i < characterId.Length(); i++)
        {
            if (!safe.Contains(characterId.Substring(i, 1))) return false;
        }
        string root = "$profile:HollowCountry";
        if (!FileExist(root) && !MakeDirectory(root)) return false;
        root = root + "/Polish";
        if (!FileExist(root) && !MakeDirectory(root)) return false;
        root = root + "/Hints";
        if (!FileExist(root) && !MakeDirectory(root)) return false;
        Path = root + "/" + characterId + ".json";
        // An interrupted write is ambiguous: never replay hints from an older image.
        if (FileExist(Path + ".tmp")) return false;
        string error;
        if (FileExist(Path))
        {
            string text;
            if (!HCGroupIO.Read(Path, 4096, text)) return false;
            if (!JsonFileLoader<HCHintState>.LoadData(text, State, error)) return false;
            // A missing -1 sentinel native-zeroes and could replay old hints.
            if (!HCJsonFields.Has(text, "ShownBits") || !HCJsonFields.Has(text, "PlayedSeconds") || !HCJsonFields.Has(text, "NextHintSecond")) return false;
            return Valid(State, characterId);
        }
        if (FileExist(Path + ".bak")) return false;
        State = new HCHintState;
        State.SchemaVersion = 1;
        State.CharacterId = characterId;
        State.ShownBits = 0;
        State.PlayedSeconds = 0;
        State.NextHintSecond = 30;
        NewState = true;
        return true;
    }

}

class HCHints
{
    static const int HINT_COUNT = 14;

    static int HCAllShownMask() { return (1 << HINT_COUNT) - 1; }

    protected ref HCHintState m_State;
    protected string m_Path;
    protected bool m_Fault;
    protected bool m_Stopped;
    protected int m_Shown;
    protected float m_Check;
    protected float m_SinceSave;
    protected ref HCStagedSaveImage m_SaveImage = new HCStagedSaveImage;
    protected string m_Notification;
    protected bool m_Switching;

    bool Open(string characterId)
    {
        HCHintLoad loaded = new HCHintLoad;
        if (!loaded.Open(characterId)) { return false; }
        m_State = loaded.State;
        m_Path = loaded.Path;
        if (loaded.NewState) { return Save(); }
        return true;
    }

    // The client advances the shared image transaction by one stage per frame.
    // It does not register with the server-only scheduler. The 4096-byte format,
    // temp/backup names and commit-before-notification contract stay unchanged.
    bool Save()
    {
        if (m_Fault || !m_State || m_Path == "" || m_SaveImage.Active()) return false;
        string payload;
        string error;
        if (!JsonFileLoader<HCHintState>.MakeData(m_State, payload, error)) return false;
        return m_SaveImage.Begin(m_Path, payload, 4096, true, false);
    }

    protected bool HCAdvanceSave()
    {
        if (!m_SaveImage.Active()) { return true; }
        int result = m_SaveImage.HCStepImage();
        if (result == HCSaveJob.STEP_FAILED)
        {
            m_Fault = true;
            m_Notification = "";
            return false;
        }
        if (result == HCSaveJob.STEP_DONE && m_Notification != "")
        {
            PlayerBase recipient = PlayerBase.Cast(GetGame().GetPlayer());
            if (recipient && recipient.IsAlive() && GetDayZGame().GetDatabaseID() == m_State.CharacterId && NotificationSystem.GetInstance())
            {
                NotificationSystem.AddNotificationExtended(10, "Hollow Country", m_Notification);
                m_Shown++;
            }
            m_Notification = "";
        }
        return true;
    }

    bool Offer(int hint, string message)
    {
        if (m_Fault || !m_State || m_SaveImage.Active() || hint < 0 || hint > 13) { return false; }
        int bit = 1 << hint;
        if ((m_State.ShownBits & bit) != 0 || m_State.PlayedSeconds < m_State.NextHintSecond) return false;
        m_State.ShownBits = m_State.ShownBits | bit;
        m_State.NextHintSecond = m_State.PlayedSeconds + 180;
        // Commit before notification: a crash may skip a hint but cannot replay it.
        if (!Save())
        {
            m_Fault = true;
            return false;
        }
        m_Notification = message;
        return true;
    }

    int NativeLevel(PlayerBase player, eDisplayElements elementId)
    {
        VirtualHud hud = player.GetVirtualHud();
        if (!hud) return -1;
        DisplayElementBase element = hud.GetElement(elementId);
        if (!element) return -1;
        return element.GetValue() >> 3;
    }

    bool Soaked(PlayerBase player)
    {
        EntityAI body = player.FindAttachmentBySlotName("Body");
        EntityAI legs = player.FindAttachmentBySlotName("Legs");
        EntityAI feet = player.FindAttachmentBySlotName("Feet");
        return (body && body.GetWet() >= GameConstants.STATE_SOAKING_WET) || (legs && legs.GetWet() >= GameConstants.STATE_SOAKING_WET) || (feet && feet.GetWet() >= GameConstants.STATE_SOAKING_WET);
    }

    void Check(PlayerBase player)
    {
        // Conditions have priority; the same shared limiter covers every topic.
        if (player.GetBleedingBits() != 0 && Offer(7, "You are bleeding. Bandage cuts with clean dressings; stop the blood loss before travelling.")) return;
        if (Soaked(player) && Offer(8, "Your clothing is soaked. Find shelter, wring out suitable clothes and dry them by a safe fire.")) return;
        int warmth = NativeLevel(player, eDisplayElements.DELM_TDCY_TEMPERATURE);
        if (warmth >= DSLevelsTemp.WARNING_MINUS && warmth <= DSLevelsTemp.BLINKING_MINUS && Offer(9, "You are cold. Dry clothing, insulation and a safe fire help restore warmth.")) return;
        int hunger = NativeLevel(player, eDisplayElements.DELM_TDCY_ENERGY);
        if (hunger == EStatLevels.CRITICAL && Offer(10, "You are starving. Eat safely prepared food soon; an empty stomach can cost health.")) return;
        if (m_State.PlayedSeconds >= 3600) return;
        if (Offer(0, "Search eligible cupboards and containers as well as loose loot. Searches draw from the finite search economy; an empty result is possible.")) return;
        if (Offer(1, "Use your map key to open the group roster. Create a group, invite nearby players or accept an invitation there.")) return;
        if (Offer(2, "Carry a map to see group map layers and shared markers. The group roster opens without one.")) return;
        if (Offer(3, "Select a player in the group roster before inviting them. Select an invitation before accepting or declining it.")) return;
        if (Offer(4, "Hold a compatible weapon and carry duct tape and a Universal Light or pistol light. Tape the light to the weapon; removing it by hand does not return the tape.")) { return; }
        if (Offer(5, "Searches, gunshots and other noise can draw infected. Break sight and move carefully; noise can bring more than one.")) return;
        if (Offer(6, "Firearms are scarce. Search likely locations, conserve ammunition and keep useful tools while you work toward a weapon.")) { return; }
        if (Offer(11, "Press K by default to change Hollow Country grade intensity in 10% steps, including off. Rebind it in Controls.")) { return; }
        if (Offer(12, "Watch for signs of life: abandoned camps, chairs and cold hearths can tell you who passed through. Follow the details; supplies are not guaranteed.")) { return; }
        Offer(13, "Rural barn shelters offer a stopping place. Approach one to discover its history and share a trail pin with your group.");
    }

    void Update(float timeslice)
    {
        if (m_Stopped || m_Fault) return;
        if (!HCAdvanceSave()) { return; }
        if (m_Switching)
        {
            if (m_SaveImage.Active()) { return; }
            m_State = null;
            m_Switching = false;
        }
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive()) return;
        string characterId = GetDayZGame().GetDatabaseID();
        if (characterId == "") return;
        if (!m_State || characterId != m_State.CharacterId)
        {
            if (m_State)
            {
                if (m_SaveImage.Active()) { return; }
                if (!Save()) { m_Fault = true; return; }
                m_Switching = true;
                // An old life's pending notification must never reach the new life.
                m_Notification = "";
                return;
            }
            if (!Open(characterId)) { m_Fault = true; return; }
            m_SinceSave = 0;
        }
        if (m_State.ShownBits == HCAllShownMask()) return;
        m_State.PlayedSeconds = m_State.PlayedSeconds + timeslice;
        m_SinceSave = m_SinceSave + timeslice;
        if (m_SaveImage.Active()) { return; }
        if (m_SinceSave >= 60)
        {
            m_SinceSave = 0;
            if (!Save()) { m_Fault = true; return; }
        }
        m_Check = m_Check + timeslice;
        if (m_Check < 5) return;
        m_Check = 0;
        if (player.IsUnconscious() || GetGame().GetUIManager().GetMenu() || !NotificationSystem.GetInstance()) return;
        if (m_State.PlayedSeconds >= m_State.NextHintSecond) Check(player);
    }

    void Stop()
    {
        if (m_Stopped) return;
        m_Stopped = true;
        m_Notification = "";
        if (!m_Fault && !m_SaveImage.Finish()) { m_Fault = true; }
        if (m_State && !m_Fault)
        {
            if (!Save() || !m_SaveImage.Finish()) { m_Fault = true; }
        }
        // HC-27 inspected NotificationSystem.c:215-230 returns no handle;
        // :239-263 owns expiration and deferred promotion. No public cancellation
        // API exists. Do not purge native/other mods' notifications or fabricate
        // a cancel. Future checks/saves stop now; existing notices expire natively.
        if (m_Shown > 0)
        {
            Print("[HC Plan] HC-27 presentation=refused handles=0 off_callbacks=0 reason=hint_cancel_unsupported scope=hints native_expiry=retained runtime=PENDING");
        }
        Print("[HollowCountry] V2 client hints shown=" + m_Shown.ToString());
    }
}
