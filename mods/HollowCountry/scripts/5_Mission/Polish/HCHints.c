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
// #256: one authored text source for contextual notices and the native Tutorials help list.
// Recipe/action evidence: HCNoConstruction, HCTapedLightActions/HCTapedLightRuntime,
// HCClaimBuildingActions, HCCampModule.Candidate, HCCampScan, HCInteriorAction,
// HCMeleeShove and HCMeleeInfectedHit. Native CraftFireplace uses one unit of
// each ingredient; CarScript.CheckOperationalRequirements/ActionFillCoolant own car basics.
class HCHintGuide
{
    static const int TOPIC_COUNT = 8;

    static int HintId(int row)
    {
        switch (row)
        {
            case 0: return 4;
            case 1: return 14;
            case 2: return 15;
            case 3: return 16;
            case 4: return 1;
            case 5: return 17;
            case 6: return 0;
            case 7: return 18;
        }
        return -1;
    }

    static string Title(int row)
    {
        switch (row)
        {
            case 0: return "Taped lights";
            case 1: return "Shelters";
            case 2: return "Camp hearth";
            case 3: return "Building claim";
            case 4: return "Group invite";
            case 5: return "Melee: block, shove, execute";
            case 6: return "Scavenging and loot search";
            case 7: return "First vehicle repair";
        }
        return "";
    }

    static string Text(int hint)
    {
        switch (hint)
        {
            case 4: return "Hold a compatible weapon, helmet or pack. Carry a loose Universal Light or pistol light and duct tape, then choose 'Tape light to held item'. Only supported pairs offer it. 'Remove taped light' needs room for the light; tape is not returned.";
            case 14: return "Use existing buildings, rural barn shelters or pitch a found tent for shelter. Shelter-kit crafting and improvised shelter construction are disabled in Hollow Country; rope and sticks do not make a shelter kit.";
            case 15: return "Combine one short stick with one rag or piece of bark to make a fireplace. Place it, add fuel and ignite it. A burning ground fireplace near a group member can become the group's hearth. A pitched tent and storage within 12 metres improve the camp; a building claim alone does not provide camp respawn.";
            case 16: return "A group owner or officer can aim at an unlocked door of an eligible building and hold 'Claim building for group'. Each group can hold one building. Use 'Release group's building claim' there to release it. Claiming does not lock doors; use a lockpick for native door locking.";
            case 1: return "Use your map key to open the group roster, even without a map item. Create a group, select a nearby player and choose Invite. The recipient selects the invitation and accepts or declines it. Carry a map item to use map layers and shared markers.";
            case 17: return "With fists or a melee weapon raised, walk backwards to block. Attack while blocking upright to shove; it costs stamina and briefly pushes infected back. A strong heavy melee hit to an unarmoured infected head can execute it; heavy leg hits can cripple infected. Head and leg bonuses apply only to infected.";
            case 0: return "With empty hands, aim at eligible storage within reach and hold 'Search storage' until it finishes. Searches draw from finite supplies, can be empty and make noise. With a wrench, screwdriver or pliers, eligible wrecks also offer 'Salvage wreck'. Loose loot still uses normal pickup.";
            case 18: return "For a common petrol car, fit matching wheels, a charged car battery, spark plug and usable radiator. Add petrol at the fuel point and water at the radiator before driving. Repair a damaged engine with a blowtorch fitted with gas; ruined engines cannot be repaired. Find replacement parts in the world or use 'Salvage wreck' on eligible wrecks with a wrench, screwdriver or pliers.";
            case 19: return "Choose 'Hollow Country help' in the pause menu or Tutorials screen for the recipe and action list. Contextual tips appear once per life, with at least three minutes between notices.";
        }
        return "";
    }

    // Fixed number of type checks; no inventory walk, area query or gameplay mutation.
    static int ItemTopics(EntityAI item)
    {
        if (!item) { return 0; }
        int bits;
        ItemBase held = ItemBase.Cast(item);
        if (item.IsKindOf("DuctTape") || item.IsKindOf("UniversalLight") || item.IsKindOf("TLRLight") || HCTapedLightRuntime.KnownHost(held)) { bits = bits | (1 << 4); }
        if (item.IsKindOf("Rope") || item.IsKindOf("LongWoodenStick") || item.IsKindOf("ShelterKit") || item.IsKindOf("TentBase") || item.IsKindOf("Fabric")) { bits = bits | (1 << 14); }
        if (item.IsKindOf("WoodenStick") || item.IsKindOf("Firewood") || item.IsKindOf("Rag") || item.IsKindOf("Bark_ColorBase") || item.IsKindOf("FireplaceBase") || item.IsKindOf("Matchbox")) { bits = bits | (1 << 15); }
        if (item.IsKindOf("Lockpick")) { bits = bits | (1 << 16); }
        if (item.IsKindOf("ItemMap")) { bits = bits | (1 << 1); }
        if (held && held.IsMeleeWeapon()) { bits = bits | (1 << 17); }
        if (item.IsKindOf("CarBattery") || item.IsKindOf("SparkPlug") || item.IsKindOf("CarRadiator") || item.IsKindOf("CarWheel") || item.IsKindOf("Wrench") || item.IsKindOf("Screwdriver") || item.IsKindOf("Pliers") || item.IsKindOf("TireRepairKit")) { bits = bits | (1 << 18); }
        if (item.IsKindOf("Wrench") || item.IsKindOf("Screwdriver") || item.IsKindOf("Pliers")) { bits = bits | 1; }
        return bits;
    }
}

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
    // Append bits only: existing schema-1 life records retain all fourteen old topics.
    static const int HINT_COUNT = 20;
    protected static int s_PendingTopics;
    protected static string s_ObservedLife;

    static void HCObserveItem(EntityAI item)
    {
        HCObserveTopics(HCHintGuide.ItemTopics(item));
    }

    static void HCObserveTopics(int topics)
    {
        if (!GetGame() || GetGame().IsServer()) { return; }
        PlayerBase observer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!observer || !observer.IsAlive()) { return; }
        string life = GetDayZGame().GetDatabaseID();
        if (life == "") { return; }
        if (life != s_ObservedLife) { s_PendingTopics = 0; s_ObservedLife = life; }
        s_PendingTopics = s_PendingTopics | topics;
    }

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
                NotificationSystem.AddNotificationExtended(14, "Hollow Country", m_Notification);
                m_Shown++;
                HCModuleReadiness.HCUse("Polish", "hint_shown");
            }
            m_Notification = "";
        }
        return true;
    }

    bool Offer(int hint, string message)
    {
        if (m_Fault || !m_State || m_SaveImage.Active() || hint < 0 || hint >= HINT_COUNT) { return false; }
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
        // Observed topics stay queued across the shared cooldown/menu suppression, but
        // never across lives. Contextual help remains available after the first hour.
        for (int row = 0; row < HCHintGuide.TOPIC_COUNT; row++)
        {
            int topic = HCHintGuide.HintId(row);
            if ((s_PendingTopics & (1 << topic)) != 0 && Offer(topic, HCHintGuide.Text(topic))) { return; }
        }
        if (m_State.PlayedSeconds >= 3600) return;
        if (Offer(19, HCHintGuide.Text(19))) return;
        if (Offer(0, HCHintGuide.Text(0))) return;
        if (Offer(1, HCHintGuide.Text(1))) return;
        if (Offer(2, "Carry a map to see group map layers and shared markers. The group roster opens without one.")) return;
        if (Offer(3, "Select a player in the group roster before inviting them. Select an invitation before accepting or declining it.")) return;
        if (Offer(5, "Searches, gunshots and other noise can draw infected. Break sight and move carefully; noise can bring more than one.")) return;
        if (Offer(6, "Search likely locations for firearms and ammunition. Keep useful tools and check a weapon's condition before relying on it.")) { return; }
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
        HCObserveItem(player.GetItemInHands());
        if (!player.GetItemInHands() && player.IsRaised()) { HCObserveTopics(1 << 17); }
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

// Native scripts-1.30.164289: 5_Mission/GUI/InspectMenuNew.c SetItem;
// GUI/NewUI/MainMenu/TutorialsMenu.c Init/OnClick/Update; UIScriptedMenu.c
// OnItemSelected; 1_Core/proto/EnWidgets.c CreateWidgets/FindAnyWidget/SetText.
// GUI/InGameMenu.c Init. All modded classes remain in their native 5_Mission module.
modded class InspectMenuNew
{
    override void SetItem(EntityAI item)
    {
        super.SetItem(item);
        // Queue only. Inspecting never pushes notifications over an open menu.
        HCHints.HCObserveItem(item);
    }
}

// Menu-local handler: the same hint layout/text is available during play and
// from the existing Tutorials surface, without registering another scripted menu.
class HCHintHelpView : ScriptedWidgetEventHandler
{
    protected Widget m_HCRecipeHelp;
    protected ButtonWidget m_HCRecipeHelpToggle;
    protected TextListboxWidget m_HCRecipeTopics;
    protected RichTextWidget m_HCRecipeDetail;
    protected bool m_HCRecipeHelpOpen;

    void Init(Widget root)
    {
        Widget helpRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_recipe_help.layout", root);
        if (!helpRoot) { return; }
        m_HCRecipeHelp = helpRoot.FindAnyWidget("HCRecipeHelpPanel");
        m_HCRecipeHelpToggle = ButtonWidget.Cast(helpRoot.FindAnyWidget("HCRecipeHelpToggle"));
        m_HCRecipeTopics = TextListboxWidget.Cast(helpRoot.FindAnyWidget("HCRecipeTopics"));
        m_HCRecipeDetail = RichTextWidget.Cast(helpRoot.FindAnyWidget("HCRecipeDetail"));
        if (!m_HCRecipeHelp || !m_HCRecipeHelpToggle || !m_HCRecipeTopics || !m_HCRecipeDetail)
        {
            helpRoot.Show(false);
            return;
        }
        for (int row = 0; row < HCHintGuide.TOPIC_COUNT; row++)
        {
            m_HCRecipeTopics.AddItem(HCHintGuide.Title(row), null, 0);
        }
        helpRoot.SetHandler(this);
        m_HCRecipeTopics.SelectRow(0);
        m_HCRecipeDetail.SetText(HCHintGuide.Text(HCHintGuide.HintId(0)));
    }

    override bool OnClick(Widget w, int x, int y, int button)
    {
        if (w == m_HCRecipeHelpToggle && m_HCRecipeHelp && button == MouseState.LEFT)
        {
            m_HCRecipeHelpOpen = !m_HCRecipeHelpOpen;
            m_HCRecipeHelp.Show(m_HCRecipeHelpOpen);
            if (m_HCRecipeHelpOpen) { m_HCRecipeHelpToggle.SetText("Close HC help"); }
            else { m_HCRecipeHelpToggle.SetText("Hollow Country help"); }
            return true;
        }
        return super.OnClick(w, x, y, button);
    }

    override bool OnItemSelected(Widget w, int x, int y, int row, int column, int oldRow, int oldColumn)
    {
        if (w == m_HCRecipeTopics && m_HCRecipeDetail && row >= 0 && row < HCHintGuide.TOPIC_COUNT)
        {
            m_HCRecipeDetail.SetText(HCHintGuide.Text(HCHintGuide.HintId(row)));
            return true;
        }
        return super.OnItemSelected(w, x, y, row, column, oldRow, oldColumn);
    }
}

modded class TutorialsMenu
{
    protected ref HCHintHelpView m_HCHintHelp;

    override Widget Init()
    {
        Widget root = super.Init();
        if (root)
        {
            m_HCHintHelp = new HCHintHelpView;
            m_HCHintHelp.Init(root);
        }
        return root;
    }
}

modded class InGameMenu
{
    protected ref HCHintHelpView m_HCHintHelp;

    override Widget Init()
    {
        Widget root = super.Init();
        if (root)
        {
            m_HCHintHelp = new HCHintHelpView;
            m_HCHintHelp.Init(root);
        }
        return root;
    }
}
