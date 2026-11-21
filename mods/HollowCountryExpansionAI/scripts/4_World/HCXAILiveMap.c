// Owner request / GitHub #162: every live eAI unit on the HC admin map and in
// debug/snapshot.json, not only HC-site patrols (HCXAIPatrolDebug "ai" layer).
// Layer "ai-units": <=128 units per capture (two page contributors of <=64
// points, HCDebugSnapshot.AddPoint caps a contributor at 64), a cursor moves the
// window across captures when more than 128 units are alive. Read-only. No
// allocation while EnableDebugSnapshot is off (no contributor is created or
// registered; the module keeps one small counter object for the RPT line).
// Native scripts-1.30.164289: 3_Game/Entities/Object.c:287 GetPosition, :467
// GetType, :517 IsAlive; Entities/Man.c:83 GetEntityInHands;
// 1_Core/proto/EnScript.c:52 Type, :94 Cast, :380 Count; EnConvert.c:30
// int.ToString; EnDebug.c:96 Print. Read-only installed Expansion AI
// ai_scripts.pbo/4_World/DayZExpansion_AI/: Entities/AI/eAIBase.c:455 Get(index),
// :466 eAI_GetAll (the static list of every eAIBase, :33 s_AllAI);
// Classes/eAIGroup.c:100 GetAll (all groups, players too, so unused here),
// :671 GetFaction, :685 GetName, :695 GetID, :1123 IsInCombat, :1139 GetMember,
// :1150 GetIndex, :1185 Count; Entities/DayZPlayerImplement.c:234 GetGroup;
// Entities/AI/eAINPCBase.c:1 class eAINPCBase.
// Source: the HC site director names its groups "HC:<site id>"
// (HCXAISites.c config.Name); every other group is Expansion's own patrol
// (AIPatrolSettings.json, quests, player-recruited AI) and reads "expansion".
class HCXAILive
{
    protected string m_StatusLogLine;
    protected float m_StatusLogAt;
    static const int PAGE_POINTS = 64;
    static const int PAGES = 2;
    protected int m_Cursor;
    protected int m_Base;
    protected float m_Elapsed;
    protected float m_Due = 60;

    // "hc-site" for director patrol groups, otherwise "expansion".
    static string Source(eAIGroup group)
    {
        if (group)
        {
            string groupName = HCXExpansionBridge.HCGroupGetName(group);
            if (groupName.Length() >= 3 && groupName.Substring(0, 3) == "HC:") { return "hc-site"; }
        }
        return "expansion";
    }

    // Own bounded prefix strip: the provider GetName() Substring is not ours to rely on.
    static string FactionName(eAIGroup group)
    {
        if (!group) { return "unknown"; }
        eAIFaction faction = HCXExpansionBridge.HCGroupGetFaction(group);
        if (!faction) { return "unknown"; }
        string localId = HCXFactions.Id(faction);
        if (localId != "") { return localId; }
        string typeName = HCXExpansionBridge.HCFactionType(faction).ToString();
        if (typeName.Length() > 10 && typeName.Substring(0, 10) == "eAIFaction")
        {
            int rest = typeName.Length() - 10;
            return typeName.Substring(10, rest);
        }
        return typeName;
    }

    static string WeaponName(eAIBase ai)
    {
        EntityAI held = HCXExpansionBridge.HCBaseGetEntityInHands(ai);
        if (!held) { return "none"; }
        return held.GetType();
    }

    // One live grouped unit becomes one "ai-units" point; false when skipped.
    static bool Emit(HCDebugSnapshot snapshot, eAIBase ai)
    {
        if (!snapshot || !ai || !HCXExpansionBridge.HCBaseIsAlive(ai)) { return false; }
        eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai);
        if (!group) { return false; }
        int size = HCXExpansionBridge.HCGroupCount(group);
        string state = "patrol";
        if (HCXExpansionBridge.HCGroupIsInCombat(group)) { state = "combat"; }
        if (eAINPCBase.Cast(ai)) { state = "npc"; }
        string source = HCXAILive.Source(group);
        string faction = HCXAILive.FactionName(group);
        string weapon = HCXAILive.WeaponName(ai);
        int slot = HCXExpansionBridge.HCGroupGetIndex(group, ai);
        string id = "g" + HCXExpansionBridge.HCGroupGetID(group).ToString() + ":" + slot.ToString();
        string label = faction + " x" + size.ToString() + " " + state + " [" + source + "]";
        string detail = "source=" + source + " faction=" + faction + " group=" + HCXExpansionBridge.HCGroupGetID(group).ToString() + " size=" + size.ToString() + " state=" + state + " weapon=" + weapon + " name=" + HCXExpansionBridge.HCGroupGetName(group);
        snapshot.AddPoint("ai-units", id, HCXExpansionBridge.HCBaseGetPosition(ai), label, detail);
        return true;
    }

    // Page 0 fixes the window for the capture and moves the cursor; page 1 reuses it.
    void Describe(HCDebugSnapshot snapshot, int page)
    {
        int total = HCXExpansionBridge.HCBaseGetAll().Count();
        if (total > HCAILimits.Get().MaxObservedAI) { total = HCAILimits.Get().MaxObservedAI; }
        if (!snapshot || total <= 0)
        {
            m_Cursor = 0;
            m_Base = 0;
            return;
        }
        if (page == 0)
        {
            if (m_Cursor >= total) { m_Cursor = 0; }
            m_Base = m_Cursor;
            m_Cursor = 0;
            if (total > HCXAILive.PAGE_POINTS * HCXAILive.PAGES) { m_Cursor = (m_Base + HCXAILive.PAGE_POINTS * HCXAILive.PAGES) % total; }
        }
        if (m_Base >= total) { m_Base = 0; }
        int offset = page * HCXAILive.PAGE_POINTS;
        int step = 0;
        while (step < HCXAILive.PAGE_POINTS && offset + step < total)
        {
            int index = (m_Base + offset + step) % total;
            step++;
            HCXAILive.Emit(snapshot, HCXExpansionBridge.HCBaseGet(index));
        }
    }

    // True when ai is the first live eAI member of its group (counts the group once).
    static bool Leads(eAIGroup group, eAIBase ai)
    {
        int slot = 0;
        while (slot < HCXExpansionBridge.HCGroupCount(group) && slot < 64)
        {
            eAIBase member = eAIBase.Cast(HCXExpansionBridge.HCGroupGetMember(group, slot));
            slot++;
            if (member && HCXExpansionBridge.HCBaseIsAlive(member)) { return member == ai; }
        }
        return false;
    }

    // Sample every 300 s (first at 60 s); emit changes or a 30-minute heartbeat.
    // expansion/hc count groups by source, so a + b == N. "" otherwise.
    string Report(float deltaTime)
    {
        m_Elapsed = m_Elapsed + deltaTime;
        if (m_Elapsed < m_Due) { return ""; }
        m_Elapsed = 0;
        m_Due = 300;
        int units = 0;
        int groups = 0;
        int expansion = 0;
        int hc = 0;
        int total = HCXExpansionBridge.HCBaseGetAll().Count();
        if (total > HCAILimits.Get().MaxObservedAI) { total = HCAILimits.Get().MaxObservedAI; }
        int index = 0;
        while (index < total)
        {
            eAIBase ai = HCXExpansionBridge.HCBaseGet(index);
            index++;
            if (!ai || !HCXExpansionBridge.HCBaseIsAlive(ai)) { continue; }
            eAIGroup group = HCXExpansionBridge.HCDayZPlayerImplementGetGroup(ai);
            if (!group) { continue; }
            units++;
            if (!HCXAILive.Leads(group, ai)) { continue; }
            groups++;
            if (HCXAILive.Source(group) == "hc-site") { hc++; }
            else { expansion++; }
        }
        string statusLine = "[HC XAI] live groups=" + groups.ToString() + " units=" + units.ToString() + " expansion=" + expansion.ToString() + " hc=" + hc.ToString();
        float statusNow = GetGame().GetTickTime();
        if (statusLine == m_StatusLogLine && statusNow >= m_StatusLogAt && statusNow - m_StatusLogAt < 1800) { return ""; }
        m_StatusLogLine = statusLine;
        m_StatusLogAt = statusNow;
        return statusLine;
    }
}

class HCXAILiveDebug : HCDebugContributor
{
    protected HCXAILive m_Live;
    protected int m_Page;

    void HCXAILiveDebug(HCXAILive live, int page)
    {
        m_Live = live;
        m_Page = page;
    }

    override void HCDescribe(HCDebugSnapshot snapshot)
    {
        if (m_Live) { m_Live.Describe(snapshot, m_Page); }
    }
}

// Always started (the RPT line must work with the map off); contributors exist
// only with EnableDebugSnapshot, the same switch as every other contributor.
class HCXAILiveModule : HCModule
{
    protected ref HCXAILive m_Live;
    protected ref array<ref HCXAILiveDebug> m_Pages;

    protected ref HCOperationalStatus m_Operational = new HCOperationalStatus;

    override string GetName() { return "hcxai-live-map"; }

    // Wave 16: started = the live reporter exists (created in OnStart, dropped in OnStop).
    override HCOperationalStatus HCGetOperationalStatus()
    {
        bool started = false;
        if (m_Live) { started = true; }
        HCModuleReadiness.HCDerive(m_Operational, started, "", "", "live_map_reporter_started");
        return m_Operational;
    }
    override bool IsEnabled(HCSettings settings) { return true; }

    override void OnStart(HCSettings settings)
    {
        if (!GetGame() || !GetGame().IsServer()) { return; }
        m_Live = new HCXAILive();
        if (!settings || !settings.EnableDebugSnapshot) { return; }
        m_Pages = new array<ref HCXAILiveDebug>;
        for (int page = 0; page < HCXAILive.PAGES; page++)
        {
            HCXAILiveDebug contributor = new HCXAILiveDebug(m_Live, page);
            m_Pages.Insert(contributor);
            HCDebugSnapshot.HCRegister(contributor);
        }
        Print("[HC XAI] live map contributors registered layer=ai-units max=128 units per capture");
    }

    override void OnTick(float deltaTime)
    {
        if (!m_Live) { return; }
        string line = m_Live.Report(deltaTime);
        HCReached.Mark("ai_live_map.report_tick");
        if (line != "")
        {
            Print("" + line);
            HCModuleReadiness.HCUse("hcxai-live-map", "report_published");
        }
    }

    override void OnStop()
    {
        if (m_Pages)
        {
            for (int index = 0; index < m_Pages.Count(); index++)
            {
                HCDebugSnapshot.HCUnregister(m_Pages[index]);
            }
        }
        m_Pages = null;
        m_Live = null;
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCXAILiveModule());
    }
}
