// HC-27: sole owner of the four HC presentation clients. Lead mission lifecycle
// calls HCStart / HCUpdate / HCStop; no parallel scheduler or gameplay RPC.
// Native evidence, scripts-1.30.164289 (relative paths):
// 3_Game/Global/Game.c:287,301,306 Get/SetProfileString, SaveProfile;
// :944,1120 GetPlayer, IsServer; 3_Game/DayZGame.c:991,3144 Event_OnRPC;
// 2_GameLib/tools.c:120,122 ScriptInvoker.Insert/Remove;
// 1_Core/proto/Serializer.c:58 Read; 1_Core/proto/EnDebug.c:96 Print;
// 1_Core/proto/EnConvert.c:30 int.ToString;
// 3_Game/Entities/Object.c:517 IsAlive; PlayerBase.c:3925 IsUnconscious
// (under 4_World/Entities/ManBase). Cleanup APIs remain with their existing owners.
// Integration contract (lead-owned shared files, intentionally not edited here):
// * Existing MissionGameplay: keep one ref HCClientPresentation; construct and
//   HCStart after super.OnInit on clients; HCUpdate(timeslice, inputAllowed) on
//   update; HCStop then null before super.OnMissionFinish. inputAllowed uses
//   !IsControlDisabled() and !GetGame().GetUIManager().GetMenu() as before.
// * HCServer after HC-1 admission: compute effective supported mask once from
//   cached owner admission plus operator ClientPresentationMask (default ALL,
//   reject unknown bits). Never rerun IsEnabled/config IO from a send/getter.
//   Send ScriptRPC.Write(VERSION), Write(revision), Write(mask), then
//   Send(null, RPC_SETTINGS, true, identity) on new/ready/reconnect and changes;
//   each change, including stop/off, advances revision within this mission.
// * Shared HCSettings owner adds int ClientPresentationMask = 15; validation
//   rejects !HCClientPresentationSettings.HCValidMask(ClientPresentationMask).
//   Existing EnableGrade/EnableSignsOfLife/EnableAmbientLife remain vetoes.
// * HCLightingClient is outside this package. Its separate mission/CallLater
//   owner must consume HCGetEffectiveMask's GRADE bit and Stop/release while
//   clear (including before first settings), if lighting is included in the
//   integrated grade-off promise. Do not reset native underground/cellar slots.
//   Radio/cellar presentation remains under its respective owner, never purged.
// No new distances. Fixed four-slot retained cursor uses HCUnitBudget and
// HCWorkBudget. Mandatory off/death cleanup never waits for a budget slice.
// No peer/player enumeration: one local viewer guard per active frame; existing
// bounded signs-of-life query remains its owner's responsibility. Runtime=PENDING.
class HCClientPresentation
{
    static const string PROFILE_KEY = "HollowCountryPresentationMaskV1";
    protected static ref HCClientPresentation s_Current;
    protected ref HCClientPresentationSettings m_Settings = new HCClientPresentationSettings;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected ref HCUnitBudget m_Units = new HCUnitBudget;
    protected ref HCWorkBudget m_Work = new HCWorkBudget;
    // Settings and holdout RPCs are bounded control traffic, not idle feature
    // callbacks. The latter has no effect handles and no update method.
    protected ref HCSignsOfLifeSnapshotClient m_Holdouts;
    protected ref HCHints m_Hints;
    protected ref HCGradeSettingsClient m_Grade;
    protected ref HCSignsOfLifeClient m_Signs;
    protected ref HCEnvSound m_Sound;
    protected int m_LocalMask = HCClientPresentationSettings.ALL;
    protected int m_EffectiveMask;
    protected int m_Next;
    protected float m_HintElapsed;
    protected float m_GradeElapsed;
    protected float m_SignsElapsed;
    protected float m_SoundElapsed;
    protected bool m_Stopped = true;
    protected bool m_Alive;
    protected string m_LastRefusal;

    // Local callers may use HCGet().HCSetPreference(key, enabled). No menu is
    // required; exact profile mask 0..15 is also supported between sessions.
    static HCClientPresentation HCGet() { return s_Current; }
    HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    int HCGetEffectiveMask() { return m_EffectiveMask; }

    void HCStart()
    {
        if (!m_Stopped || !GetGame() || GetGame().IsServer()) { return; }
        m_Stopped = false;
        s_Current = this;
        m_Settings = new HCClientPresentationSettings;
        m_LocalMask = HCClientPresentationSettings.ALL;
        string saved;
        if (GetGame().GetProfileString(PROFILE_KEY, saved))
        {
            // Exact decimal mask only; malformed profile data fails closed.
            m_LocalMask = 0;
            bool found = false;
            int candidate = 0;
            while (candidate <= HCClientPresentationSettings.ALL)
            {
                if (saved == candidate.ToString()) { m_LocalMask = candidate; found = true; }
                candidate = candidate + 1;
            }
            if (!found) { HCRefuse("invalid_local_mask"); }
        }
        m_Holdouts = new HCSignsOfLifeSnapshotClient;
        DayZGame.Event_OnRPC.Insert(HCReceive);
        Print(HCV2Admission.Line("ClientPresentation", true, "HC-27", false));
        HCReport("off", "awaiting_server_settings");
    }

    void HCReceive(PlayerIdentity sender, Object target, int rpcType, ParamsReadContext ctx)
    {
        if (m_Stopped || GetGame().IsServer() || sender || target) { return; }
        if (rpcType != HCClientPresentationSettings.RPC_SETTINGS) { return; }
        int version;
        int revision;
        int mask;
        if (!ctx || !ctx.Read(version) || !ctx.Read(revision) || !ctx.Read(mask))
        {
            m_Settings.HCInvalidate();
            HCReconcile();
            HCRefuse("malformed_settings_rpc");
            return;
        }
        HCApplyServer(version, revision, mask);
    }

    void HCApplyServer(int version, int revision, int mask)
    {
        if (m_Stopped) { return; }
        int result = m_Settings.HCAccept(version, revision, mask);
        if (result == 0) { return; }
        if (result > 0) { m_LastRefusal = ""; }
        HCReconcile();
        if (result < 0) { HCRefuse("unknown_or_conflicting_settings"); }
    }

    bool HCSetPreference(string key, bool enabled)
    {
        if (m_Stopped) { return false; }
        int bit = HCClientPresentationSettings.HCBit(key);
        if (bit < 0) { HCRefuse("unknown_setting"); return false; }
        m_LastRefusal = "";
        int previous = m_LocalMask;
        m_LocalMask = m_LocalMask & (HCClientPresentationSettings.ALL - bit);
        if (enabled) { m_LocalMask = m_LocalMask | bit; }
        if (m_LocalMask == previous) { return true; }
        // Disable effects before synchronous native profile persistence.
        HCReconcile();
        GetGame().SetProfileString(PROFILE_KEY, m_LocalMask.ToString());
        GetGame().SaveProfile();
        return true;
    }

    protected void HCReconcile()
    {
        int desired = m_Settings.HCEffective(m_LocalMask);
        if (m_Stopped) { desired = 0; }
        // Four fixed lanes, no world scan. Stop before releasing every owner.
        if ((desired & HCClientPresentationSettings.HINTS) == 0)
        {
            if (m_Hints) { m_Hints.Stop(); m_Hints = null; }
        }
        else if (!m_Hints) { m_Hints = new HCHints; }
        if ((desired & HCClientPresentationSettings.GRADE) == 0)
        {
            if (m_Grade) { m_Grade.Stop(); m_Grade = null; }
        }
        else if (!m_Grade) { m_Grade = new HCGradeSettingsClient; m_Grade.Start(); }
        if ((desired & HCClientPresentationSettings.SIGNS) == 0)
        {
            if (m_Signs) { m_Signs.Stop(); m_Signs = null; }
        }
        else if (!m_Signs) { m_Signs = new HCSignsOfLifeClient; }
        if ((desired & HCClientPresentationSettings.AMBIENT) == 0)
        {
            if (m_Sound) { m_Sound.Stop(); m_Sound = null; }
        }
        else if (!m_Sound) { m_Sound = new HCEnvSound; }
        m_EffectiveMask = desired;
        m_Next = 0;
        m_HintElapsed = 0;
        m_GradeElapsed = 0;
        m_SignsElapsed = 0;
        m_SoundElapsed = 0;
        string state = "off";
        if (desired != 0) { state = "on"; }
        HCReport(state, "effective_settings");
    }

    void HCUpdate(float timeslice, bool allowInput)
    {
        // No owner callbacks, native queries, clock reads, saves or scans off.
        if (m_Stopped || m_EffectiveMask == 0) { return; }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer || !viewer.IsAlive() || viewer.IsUnconscious())
        {
            if (m_Alive)
            {
                if (m_Grade) { m_Grade.Stop(); }
                if (m_Signs) { m_Signs.Clear(); }
                if (m_Sound) { m_Sound.StopSound(); }
            }
            m_Alive = false;
            m_HintElapsed = 0;
            m_GradeElapsed = 0;
            m_SignsElapsed = 0;
            m_SoundElapsed = 0;
            return;
        }
        m_Alive = true;
        // Preserve each active owner's elapsed time when its lane yields.
        if (m_Hints) { m_HintElapsed = m_HintElapsed + timeslice; }
        if (m_Grade) { m_GradeElapsed = m_GradeElapsed + timeslice; }
        if (m_Signs) { m_SignsElapsed = m_SignsElapsed + timeslice; }
        if (m_Sound) { m_SoundElapsed = m_SoundElapsed + timeslice; }
        m_Units.HCReset(4);
        m_Work.HCReset(4, 4);
        int examined = 0;
        while (examined < 4 && m_Units.HCTake(1) && m_Work.HCContinue())
        {
            int lane = m_Next;
            m_Next = m_Next + 1;
            if (m_Next >= 4) { m_Next = 0; }
            examined = examined + 1;
            if (lane == 0 && m_Hints) { m_Hints.Update(m_HintElapsed); m_HintElapsed = 0; }
            if (lane == 1 && m_Grade) { m_Grade.Update(m_GradeElapsed, allowInput); m_GradeElapsed = 0; }
            if (lane == 2 && m_Signs) { m_Signs.HCTickEffects(m_SignsElapsed); m_SignsElapsed = 0; }
            if (lane == 3 && m_Sound) { m_Sound.Update(m_SoundElapsed); m_SoundElapsed = 0; }
        }
    }

    int HCHandleCount()
    {
        int count = 0;
        if (m_Grade) { count = count + m_Grade.HCHandleCount(); }
        if (m_Signs) { count = count + m_Signs.HCHandleCount(); }
        if (m_Sound) { count = count + m_Sound.HCHandleCount(); }
        return count;
    }

    protected void HCReport(string state, string reason)
    {
        string health = state;
        if (state == "on") { health = "ready"; }
        m_Status.HCPublish(health, reason);
        int handles = HCHandleCount();
        string line = "[HC Plan] HC-27 presentation=" + state + " handles=" + handles.ToString() + " off_callbacks=0";
        Print(line + " reason=" + reason + " runtime=PENDING");
    }

    protected void HCRefuse(string reason)
    {
        m_Status.HCPublish("refused", reason);
        if (reason == m_LastRefusal) { return; }
        m_LastRefusal = reason;
        HCReport("refused", reason);
    }

    void HCStop()
    {
        if (m_Stopped) { return; }
        m_Stopped = true;
        DayZGame.Event_OnRPC.Remove(HCReceive);
        HCReconcile();
        if (m_Holdouts) { m_Holdouts.Stop(); m_Holdouts = null; }
        m_Alive = false;
        m_Settings = new HCClientPresentationSettings;
        if (s_Current == this) { s_Current = null; }
    }
}
