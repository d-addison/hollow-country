// Authored HC metadata, shared by client UI and server ingress. No engine work.
// Add one HCAdd line and its server handler; the UI has no command dispatch list.
class HCAdminCommand
{
    string Id;
    string Section;
    string Label;
    string Help;
    bool ReadOnly;
    bool AtPosition;
    bool Integer;
    protected int m_Min;
    protected int m_Max;
    int DefaultValue;
    string Unit;

    int HCClamp(int value)
    {
        return Math.Clamp(value, m_Min, m_Max);
    }

    int HCStep(int value, int direction)
    {
        value = HCClamp(value);
        // Check first, so +/- cannot overflow even at native integer limits.
        if (direction < 0 && value > m_Min) { return value - 1; }
        if (direction > 0 && value < m_Max) { return value + 1; }
        return value;
    }

    string HCRange()
    {
        return m_Min.ToString() + " - " + m_Max.ToString() + " " + Unit;
    }

    void HCAdminCommand(string id, string section, string label, string help, bool readOnly, bool atPosition, bool integer, int minimum, int maximum, int defaultValue, string unit)
    {
        Id = id;
        Section = section;
        Label = label;
        Help = help;
        ReadOnly = readOnly;
        AtPosition = atPosition;
        Integer = integer;
        m_Min = minimum;
        m_Max = maximum;
        DefaultValue = HCClamp(defaultValue);
        Unit = unit;
    }
}

class HCAdminSection
{
    string Id;
    string Label;
    string Help;

    void HCAdminSection(string id, string label, string help)
    {
        Id = id;
        Label = label;
        Help = help;
    }
}

class HCAdminCatalog
{
    protected static ref array<ref HCAdminCommand> s_Commands;
    protected static ref array<ref HCAdminSection> s_Sections;

    protected static void HCSection(string id, string label, string help)
    {
        s_Sections.Insert(new HCAdminSection(id, label, help));
    }

    protected static void HCAdd(string id, string section, string label, string help, bool readOnly, bool atPosition, bool integer, int minimum, int maximum, int defaultValue, string unit)
    {
        s_Commands.Insert(new HCAdminCommand(id, section, label, help, readOnly, atPosition, integer, minimum, maximum, defaultValue, unit));
    }

    protected static void HCInit()
    {
        if (s_Commands) { return; }
        s_Commands = new array<ref HCAdminCommand>;
        s_Sections = new array<ref HCAdminSection>;
        HCSection("overview", "Overview", "Inspect module availability and state. Runtime acceptance remains pending.");
        HCSection("infected", "Infected", "Use normal infected admissions, budgets and memory at your position.");
        HCSection("ai", "AI & Camps", "Evaluate nearby camps and hold-outs through their normal rules.");
        HCSection("world", "World & Events", "Request the normal directors and world services; all caps still apply.");
        HCSection("economy", "Economy", "Prime existing refresh and forage work without creating duplicate loot.");
        HCSection("time", "Time & Weather", "Adjust HC escalation and weather profiles. Native time of day is unchanged.");
        HCSection("map", "Map", "Inspect the latest snapshot. Request one from Overview; toggle layers below.");
        // id, section, label, help, read-only, at-my-position, integer, min, max, default, unit
        HCAdd("tp", "overview", "Teleport for testing", "Admin only: choose an index from tplist; safe ground or refusal.", false, false, true, 0, 255, 0, "destination");
        HCAdd("tplist", "overview", "Teleport destinations", "Read the server destination snapshot; value selects its page.", true, false, true, 0, 255, 0, "page");
        HCAdd("tprefresh", "overview", "Refresh destinations", "Rebuild the server snapshot; teleport waits until complete.", true, false, false, 0, 0, 0, "");
        HCAdd("status", "overview", "Module status", "Inspect bounded metrics for every running HC module.", true, false, false, 0, 0, 0, "");
        HCAdd("kit", "overview", "Kit availability", "List each command's availability and admission reason.", true, false, false, 0, 0, 0, "");
        HCAdd("list", "overview", "State near me", "Inspect nearby infected, heat, drops, forage and decaying towns.", true, true, false, 0, 0, 0, "");
        HCAdd("snapshot", "overview", "Request snapshot", "Capture debug map layers over several ticks; five-second cooldown.", true, false, false, 0, 0, 0, "");
        HCAdd("sitter", "infected", "Place sitter", "Admit one sitter eight metres ahead; one body including its corpse.", false, true, false, 0, 0, 0, "");
        HCAdd("dormant", "infected", "Dormant admission", "Queue a fresh dormant body near you through normal placement and infected budgets.", false, true, false, 0, 0, 0, "");
        HCAdd("horde", "infected", "Adopt native horde", "Adopt an eligible native cohort within 100 m using normal budgets.", false, true, false, 0, 0, 0, "");
        HCAdd("clear", "infected", "Clear admin sitter", "Delete only the admin sitter; other infected remain untouched.", false, false, false, 0, 0, 0, "");
        HCAdd("memory", "infected", "Infected memory", "Record heat shots in your 500 m cell; zero clears this cell.", false, true, true, 0, 3, 1, "shots");
        HCAdd("camp", "ai", "Evaluate camp", "Evaluate the nearest recognised camp within 100 m; no forced age.", false, true, false, 0, 0, 0, "");
        HCAdd("camptier", "ai", "Force camp tier", "Persist nearest camp tier; next normal scan reclassifies.", false, true, true, 0, 3, 1, "tier");
        HCAdd("campvisit", "ai", "Request camp visit", "Request a physical visit to the nearest eligible camp; normal attendance and cooldown guards apply.", false, true, false, 0, 0, 0, "");
        HCAdd("campraid", "ai", "Request camp raid", "Request a raid on the nearest eligible camp; normal warning and cooldown guards apply.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_holdout_due", "ai", "Smoke: due funded holdout", "Lead-only R3: select an existing naturally due funded row; no aging or supplies.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_conflict", "ai", "Smoke: distant conflict", "Lead-only R3: prioritize an existing eligible distant opposed cell; normal guards apply.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_materialize", "ai", "Smoke: offered proposal", "Lead-only R3: prioritize an existing unclaimed proposal; real provider outcome required.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_incident", "world", "Test setup: AI incident", "Dev test addon only: select a nearby real incident through the XAI handler.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_tactic", "world", "Test setup: AI tactic", "Dev test addon only: select a nearby real tactic through the XAI handler.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_trade", "world", "Test setup: AI trade", "Dev test addon only: select a nearby real trade through the XAI handler.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_convoy_stuck", "world", "Test setup: stuck convoy", "Dev test addon only: select a real stuck convoy through the XAI handler.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_bridge", "world", "Test setup: bridge selector", "Dev test addon only: report use-fx_materialize from the XAI handler.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_shoot_held", "world", "Test setup: held weapon shot", "Dev test addon only: fire one chambered round from your held weapon at the nearest AI within 60 m.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_door_press", "world", "Test setup: infected door pressure", "Dev test addon only: place three infected outside the nearest closed door within 30 m; stand inside or near it.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_hearth", "world", "Test setup: standalone fire", "Dev test addon only: light one fireplace 6-12 m away; SignsOfLife building selection still applies.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_die", "world", "Test setup: requester death", "Dev test addon only: set only your health to zero through the normal death path.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_car_zeds", "world", "Test setup: occupied car infected", "Dev test addon only: place two infected 10-20 m from the car you occupy; natural pursuit and contact required.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_car_side", "world", "Test setup: car on its side", "Dev test addon only: roll one parked or new car onto its side 8-15 m away; the real flip code runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_camp_setup", "world", "Test setup: built camp", "Dev test addon only: pitch a tent, crate and lit fire 6-15 m away; the real camp code runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_wreck", "world", "Test setup: salvage wreck", "Dev test addon only: place one reviewed car wreck 8-15 m away; the real salvage code runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_animal", "world", "Test setup: otter", "Dev test addon only: place one Animal_Otter 8-15 m away when the animal pack is loaded; its normal init runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_food", "world", "Test setup: pack food", "Dev test addon only: place one food-pack item 3-8 m away; its normal temperature init runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_cooking", "world", "Test setup: cooking pot", "Dev test addon only: light a fire with a tripod and a pot holding a pack dish 6-12 m away; the normal cooking tick runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_kit_place", "world", "Test setup: shelter kit", "Dev test addon only: run the real deploy finish for a shelter-scale fortification kit; the normal claim gate decides.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_kit_refuse", "world", "Test setup: oversize kit", "Dev test addon only: run the real deploy finish for a non-shelter RaG kit; the normal claim gate refuses it.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_barricade", "world", "Test setup: barricaded door", "Dev test addon only: build a door barricade at the nearest building door with infected outside; the real breach code runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_melee", "world", "Test setup: melee strikes", "Dev test addon only: strike infected ahead of you with your melee weapon through the engine melee entry; the real melee code runs.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_shoot", "world", "Test setup: one shot", "Dev test addon only: one chambered round from a world weapon through the native fire call, aimed at the nearest AI or ahead of you; the real shot handlers run.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_site_patrol_kill", "world", "Test setup: patrol death", "Dev test addon only: kill one nearby police-chernogorsk patrol member through its real death handler; normal cleanup and counters run.", false, true, false, 0, 0, 0, "");
        HCAdd("fx_site_clear", "world", "Test setup: site clear", "Dev test addon only: clear a nearby live patrol; 0 attributed requester damage (default), 1 health; normal cleanup and counters run.", false, true, true, 0, 1, 0, "mode");
        HCAdd("holdout", "ai", "Evaluate hold-out", "Run normal occupancy on the nearest hold-out within 100 m.", false, true, false, 0, 0, 0, "");
        HCAdd("event", "world", "Start reviewed event", "Request the nearest reviewed site through normal event admission.", false, true, false, 0, 0, 0, "");
        HCAdd("scene", "world", "Place due scene", "Request the nearest due reviewed scene; maximum two scene leases.", false, true, false, 0, 0, 0, "");
        HCAdd("radio", "world", "Prime radio line", "Ready a channel you can hear; requires a powered receiving radio.", false, true, false, 0, 0, 0, "");
        HCAdd("deaddrop", "world", "Make dead drop due", "Ready the nearest drop within 1000 m for its normal deposit tick.", false, true, false, 0, 0, 0, "");
        HCAdd("decay", "world", "Queue settlement decay", "Queue the nearest town within 1000 m for its normal decay step.", false, true, false, 0, 0, 0, "");
        HCAdd("loot", "economy", "Ready loot refresh", "Age the oldest pending refresh timer; search its container again.", false, false, false, 0, 0, 0, "");
        HCAdd("forage", "economy", "Ready forage cell", "Clear your cell for normal forest forage; season and caps apply.", false, true, false, 0, 0, 0, "");
        HCAdd("day", "time", "Escalation day", "Set the persisted escalation day; camp age and other clocks stay as-is.", false, false, true, 0, 3650, 1, "day");
        HCAdd("weather", "time", "Weather-day profile", "30 min override: 0 clear, 1 plain, 2 calm, 3 fog, 4 bad.", false, false, true, 0, 4, 1, "profile");
    }

    static array<ref HCAdminCommand> Commands()
    {
        HCInit();
        return s_Commands;
    }

    static array<ref HCAdminSection> Sections()
    {
        HCInit();
        return s_Sections;
    }

    static bool HCKnown(string command)
    {
        if (HCAdminWire.HCIsLootMap(command)) { return true; }
        array<ref HCAdminCommand> entries = Commands();
        for (int index = 0; index < entries.Count(); index++)
        {
            if (entries[index].Id == command) { return true; }
        }
        return false;
    }
}
