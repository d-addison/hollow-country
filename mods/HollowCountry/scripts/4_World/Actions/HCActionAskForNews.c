// LC-T406 / EXP-L6. Installed native scripts-1.30.164289:
// 4_World/Classes/UserActionsComponent/Actions/ActionInteractBase.c:42-96;
// TargetConditionsComponents/CCTMan.c:6-24; ActionConstructor.c:27 RegisterActions;
// 4_World/Entities/ManBase/PlayerBase.c:1695,1751 SetActions/SetActionsRemoteTarget;
// :2219 IsRestrained, :3925 IsUnconscious;
// 4_World/Entities/DayZPlayerImplement.c:4005 IsRaised;
// Actions/Interact/ActionCloseBarrel.c:27 OnExecuteServer;
// 3_Game/Entities/Object.c:287 GetPosition, :517 IsAlive;
// 3_Game/Entities/Man.c:21 GetIdentity; 3_Game/gameplay.c:368 GetId;
// 3_Game/Client/Notifications/NotificationSystem.c:125 SendNotificationToPlayerExtended;
// 3_Game/Global/Game.c:1119,1120 IsClient/IsServer, :1535 GetTime;
// 3_Game/tools/JsonFileLoader.c:85 MakeData;
// 1_Core/proto/EnSystem.c:397 FileExist, :525 MakeDirectory, :528,531 DeleteFile/CopyFile.
// No native rename exists in this dump: pending guard + backup + verified copy,
// as HCXAIStore does. Interrupted publication refuses further talk until recovery.
class HCAskForNewsTarget
{
    bool Eligible(PlayerBase player, Object target) { return false; }
    string NPCKey(Object target) { return ""; }
    void Greet(Object target) {}
}
class HCNewsReceipt
{
    string NPC;
    string Group;
    int At;
}
class HCNewsJournal
{
    int SchemaVersion = 1;
    int LastUtc;
    ref array<ref HCNewsReceipt> Rows = new array<ref HCNewsReceipt>();
}
class HCNewsNotice
{
    string Recipient;
    int At;
}
class HCAskForNews
{
    protected static ref HCAskForNewsTarget s_Target = new HCAskForNewsTarget();
    protected static ref HCNewsJournal s_Journal;
    protected static ref array<ref HCNewsNotice> s_Notices = new array<ref HCNewsNotice>();
    protected static bool s_Enabled;
    protected static bool s_Healthy;
    static const string PATH = "$profile:HollowCountry/ask-for-news.json";
    static const string PENDING = "$profile:HollowCountry/ask-for-news.pending.json";

    // Ledger-wave port. Never synthesize an event or disclose a live position.
    static string Rumour(vector pos) { return ""; }

    static void Configure(bool enabled)
    {
        s_Enabled = enabled;
        s_Healthy = false;
        s_Journal = null;
        if (!enabled || !GetGame() || !GetGame().IsServer()) { return; }
        int now = HCGroupClock.Utc();
        if (now < 1 || FileExist(PENDING)) { Print("[HollowCountry] AskForNews refused: clock or pending journal"); return; }
        if (!FileExist(PATH)) { s_Journal = new HCNewsJournal(); }
        else if (!HCGroupJson<HCNewsJournal>.Load(PATH, 65536, s_Journal)) { Print("[HollowCountry] AskForNews refused: unreadable journal"); return; }
        if (!s_Journal || s_Journal.SchemaVersion != 1 || !s_Journal.Rows || s_Journal.Rows.Count() > 256 || s_Journal.LastUtc < 0 || s_Journal.LastUtc > now) { Print("[HollowCountry] AskForNews refused: invalid journal or clock rollback"); return; }
        foreach (HCNewsReceipt row : s_Journal.Rows)
        {
            if (!row || row.NPC == "" || row.NPC.Length() > 128 || row.Group == "" || row.Group.Length() > 128 || row.At < 1 || row.At > now) { Print("[HollowCountry] AskForNews refused: invalid receipt"); return; }
        }
        s_Healthy = true;
        Print("[HollowCountry] AskForNews ready: server validation; one per NPC/group/86400s; rumour hook empty");
    }
    static bool NoticeAllowed(PlayerBase player)
    {
        if (!GetGame() || !GetGame().IsServer() || !player || !player.GetIdentity()) { return false; }
        int nowMs = GetGame().GetTime();
        if (nowMs < 0) { return false; }
        string recipient = player.GetIdentity().GetId();
        foreach (HCNewsNotice notice : s_Notices)
        {
            if (nowMs < notice.At) { return false; }
            if (notice.Recipient == recipient && nowMs - notice.At < 30000) { return false; }
        }
        return true;
    }
    // Shared with stance: no more than one news/warning notification per player
    // in 30 seconds across all NPCs. At capacity refuse, never evict a live limit.
    static bool Notify(PlayerBase player, string title, string line)
    {
        if (!HCAskForNews.NoticeAllowed(player)) { return false; }
        int nowMs = GetGame().GetTime();
        int prune = s_Notices.Count() - 1;
        while (prune >= 0)
        {
            if (nowMs - s_Notices[prune].At >= 30000) { s_Notices.Remove(prune); }
            prune--;
        }
        if (s_Notices.Count() >= 128) { return false; }
        HCNewsNotice notice = new HCNewsNotice();
        notice.Recipient = player.GetIdentity().GetId();
        notice.At = nowMs;
        s_Notices.Insert(notice);
        NotificationSystem.SendNotificationToPlayerExtended(player, 5, title, line);
        return true;
    }
    static bool Eligible(PlayerBase player, Object target)
    {
        if (!GetGame() || !player || !player.IsAlive() || player.IsUnconscious() || player.IsRestrained() || player.IsRaised() || !target || !target.IsAlive()) { return false; }
        if (vector.Distance(player.GetPosition(), target.GetPosition()) > 4) { return false; }
        if (GetGame().IsServer() && (!s_Enabled || !s_Healthy || !player.GetIdentity())) { return false; }
        return s_Target.Eligible(player, target);
    }
    protected static bool Save()
    {
        if (FileExist(PENDING)) { return false; }
        string expected;
        string error;
        string staged;
        string published;
        if (!JsonFileLoader<HCNewsJournal>.MakeData(s_Journal, expected, error) || expected.Length() > 65536) { return false; }
        MakeDirectory("$profile:HollowCountry");
        if (!HCGroupIO.WriteNew(PENDING, expected, 65536) || !HCGroupIO.Read(PENDING, 65536, staged) || staged != expected) { return false; }
        if (FileExist(PATH) && !CopyFile(PATH, PATH + ".bak")) { return false; }
        if (!CopyFile(PENDING, PATH) || !HCGroupIO.Read(PATH, 65536, published) || published != expected) { return false; }
        return DeleteFile(PENDING) && !FileExist(PENDING);
    }
    static void Talk(PlayerBase player, Object target)
    {
        // Called again at execution, never trust client action visibility.
        if (!GetGame() || !GetGame().IsServer() || !HCAskForNews.Eligible(player, target) || !HCAskForNews.NoticeAllowed(player)) { return; }
        HCGroupService groups = HCGroupService.Get();
        if (!groups) { return; }
        string groupKey = groups.HCNewsGroup(player);
        string npc = s_Target.NPCKey(target);
        int now = HCGroupClock.Utc();
        if (groupKey == "" || npc == "" || npc.Length() > 128 || now < 1 || now < s_Journal.LastUtc) { return; }
        foreach (HCNewsReceipt prior : s_Journal.Rows)
        {
            if (prior.NPC == npc && prior.Group == groupKey && now - prior.At < 86400)
            {
                HCAskForNews.Notify(player, "News", "We have already talked today.");
                return;
            }
        }
        int prune = s_Journal.Rows.Count() - 1;
        while (prune >= 0)
        {
            if (now - s_Journal.Rows[prune].At >= 86400) { s_Journal.Rows.Remove(prune); }
            prune--;
        }
        if (s_Journal.Rows.Count() >= 256) { return; }
        HCNewsReceipt receipt = new HCNewsReceipt();
        receipt.NPC = npc;
        receipt.Group = groupKey;
        receipt.At = now;
        s_Journal.Rows.Insert(receipt);
        s_Journal.LastUtc = now;
        // Durable consumption before any response, never replay an uncertain IO.
        if (!HCAskForNews.Save())
        {
            s_Healthy = false;
            Print("[HollowCountry] AskForNews refused: journal publication uncertain; preserve pending file");
            return;
        }
        string rumour = HCAskForNews.Rumour(target.GetPosition());
        if (rumour == "") { rumour = "Nothing new to tell you."; }
        if (rumour.Length() > 160) { rumour = rumour.Substring(0, 160); }
        s_Target.Greet(target);
        HCAskForNews.Notify(player, "News", rumour);
        Print("[HollowCountry] AskForNews answered: npc=" + npc + "; daily group receipt saved");
    }
}
// Reuse the existing server-owned group ledger without exposing it to clients.
// Identity here keys only the talk quota, never stance or faction standing.
modded class HCGroupService
{
    string HCNewsGroup(PlayerBase player)
    {
        if (!m_Healthy || !m_State || !player || !player.GetIdentity()) { return ""; }
        string uid = player.GetIdentity().GetId();
        HCGroupRecord group = HCGroupRules.FindGroup(m_State, uid);
        if (group) { return "group:" + group.Id.ToString(); }
        return "solo:" + uid;
    }
}
class HCActionAskForNews : ActionInteractBase
{
    protected static bool s_ClientLogged;
    void HCActionAskForNews()
    {
        m_Text = "Ask for news";
        m_StanceMask = DayZPlayerConstants.STANCEMASK_ERECT | DayZPlayerConstants.STANCEMASK_CROUCH;
        if (GetGame() && GetGame().IsClient() && !s_ClientLogged)
        {
            s_ClientLogged = true;
            Print("[HollowCountry] V2 client AskForNews action registered; optional HCX target binding required");
        }
    }
    override void CreateConditionComponents()
    {
        m_ConditionItem = new CCINone;
        m_ConditionTarget = new CCTMan(4, true);
    }
    override bool ActionCondition(PlayerBase player, ActionTarget target, ItemBase item)
    {
        return target && HCAskForNews.Eligible(player, target.GetObject());
    }
    override void OnExecuteServer(ActionData action_data)
    {
        if (!action_data || !action_data.m_Target) { return; }
        HCAskForNews.Talk(action_data.m_Player, action_data.m_Target.GetObject());
    }
}
modded class ActionConstructor
{
    override void RegisterActions(TTypenameArray actions)
    {
        super.RegisterActions(actions);
        actions.Insert(HCActionAskForNews);
    }
}
modded class PlayerBase
{
    override void SetActions(out TInputActionMap InputActionMap)
    {
        super.SetActions(InputActionMap);
        AddAction(HCActionAskForNews, InputActionMap);
    }
    override void SetActionsRemoteTarget(out TInputActionMap InputActionMap)
    {
        super.SetActionsRemoteTarget(InputActionMap);
        AddAction(HCActionAskForNews, InputActionMap);
    }
}
