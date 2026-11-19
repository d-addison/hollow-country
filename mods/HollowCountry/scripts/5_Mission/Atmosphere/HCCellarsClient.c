// HC-31: the W5 depth heuristic is retained but disabled by shared admission.
// No measured/qualified cellar receipt exists; native underground remains owner.
// Native scripts-1.30.164289: 3_Game/Global/Game.c:287 GetProfileString,
// :931 GetWorld, :944 GetPlayer, :1125 IsDedicatedServer, :1176 SurfaceY;
// Entities/Object.c:287 GetPosition, :517 IsAlive; Entities/Man.c:37
// IsSoundInsideBuilding (native Environment/Environment.c:511-513 reuses it).
// 4_World/Entities/ManBase/PlayerBase.c:2848 GetUndergroundPresence;
// Classes/UndergroundHandlerClient.c:18 native lighting path, :39 LoadUserLightingCfg,
// :314-341 native eye/lighting path, :378-404 NV exposure handling.
// 3_Game/Global/World.c:105 LoadUserLightingCfg, :110 SetUserLightingLerp;
// PPEManager/PPERequesterBank.c:78 GetRequester(typename), :236 IsRequesterRunning;
// PPEManager/Requesters/PPERUndergroundAcco.c:3 SetEyeAccommodation;
// PPEManager/Requesters/PPERequestPlatformsBase.c:38-56 Start/Stop;
// 1_Core/proto/EnMath.c:540 Clamp, :608 Lerp; EnScript.c:94 Cast;
// 5_Mission/mission/missionGameplay.c:102 OnInit, :266 OnMissionFinish,
// :287 OnUpdate(float timeslice); EnDebug.c:96 Print.
// At most four samples/s: one controlled player, one SurfaceY, one cached native
// inside-building query. No allocations while off, no world/player enumeration.
// Only renderer writes; no local underground presence, sounds, locks or inventory
// changes. Stock underground and NV requesters take priority; native compile and
// two-client visual/torch/NVG/exit/death/rejoin checks remain PENDING.
class HCCellarsClient
{
    protected static bool s_VisualActive;
    protected ref HCCellarRequester m_Requester;
    protected float m_Elapsed;
    protected float m_Accommodation = 1;
    protected bool m_LoggedInside;

    static bool HCVisualActive() { return s_VisualActive; }

    static bool HCPreferenceEnabled()
    {
        string preference;
        GetGame().GetProfileString("HollowCountryDarkCellars", preference);
        return preference != "0";
    }

    protected bool HCNativeVisualsActive(PlayerBase player)
    {
        if (player.GetUndergroundPresence() != EUndergroundPresence.NONE) { return true; }
        if (PPERequesterBank.IsRequesterRunning(PPERequesterBank.REQ_UNDERGROUND)) { return true; }
        return false;
    }

    void HCClear(bool nativeVisuals = false)
    {
        if (s_VisualActive && m_Requester) { m_Requester.Stop(); }
        // A native area may already have taken the single user-lighting slot.
        if (s_VisualActive && !nativeVisuals)
        {
            if (GetGame() && GetGame().GetWorld()) { GetGame().GetWorld().SetUserLightingLerp(0); }
        }
        s_VisualActive = false;
        m_Accommodation = 1;
        if (m_LoggedInside)
        {
            Print("[HollowCountry] V2 client cellars visual=off");
            m_LoggedInside = false;
        }
    }

    void HCSample(float timeslice)
    {
        if (!HCCellarAdmission.HCAdmitted()) { return; }
        m_Elapsed = m_Elapsed + timeslice;
        if (m_Elapsed < 0.25) { return; }
        m_Elapsed = 0;
        PlayerBase player = PlayerBase.Cast(GetGame().GetPlayer());
        if (!player || !player.IsAlive()) { HCClear(); return; }
        if (HCNativeVisualsActive(player)) { HCClear(true); return; }
        if (PPERequesterBank.IsRequesterRunning(PPERequesterBank.REQ_CAMERANV)) { HCClear(); return; }
        vector position = player.GetPosition();
        float surface = GetGame().SurfaceY(position[0], position[2]);
        bool inside = false;
        if (surface - position[1] > 2.0) { inside = player.IsSoundInsideBuilding(); }
        float target = 1;
        if (inside) { target = 0.2; }
        if (!inside && !s_VisualActive) { return; }
        if (!m_Requester)
        {
            m_Requester = HCCellarRequester.Cast(PPERequesterBank.GetRequester(HCCellarRequester));
            if (!m_Requester) { return; }
        }
        if (!s_VisualActive)
        {
            GetGame().GetWorld().LoadUserLightingCfg("dz\\data\\lighting\\lighting_underground.txt", "Underground");
            m_Requester.Start();
            s_VisualActive = true;
        }
        m_Accommodation = Math.Lerp(m_Accommodation, target, 0.5);
        if (!inside && m_Accommodation > 0.99) { HCClear(); return; }
        m_Requester.SetEyeAccommodation(m_Accommodation);
        float weight = Math.Clamp((1 - m_Accommodation) / 0.8, 0, 1);
        GetGame().GetWorld().SetUserLightingLerp(weight);
        if (inside && !m_LoggedInside)
        {
            Print("[HollowCountry] V2 client cellars visual=below_terrain_inside_building");
            m_LoggedInside = true;
        }
    }
}

modded class MissionGameplay
{
    protected ref HCCellarsClient m_HCCellars;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsDedicatedServer()) { return; }
        if (!HCCellarsClient.HCPreferenceEnabled()) { return; }
        if (!HCCellarAdmission.HCAdmitted())
        {
            Print("[HC Plan] HC-31 client state=refused refused=" + HCCellarAdmission.HCReason() + " runtime=PENDING");
            return;
        }
        m_HCCellars = new HCCellarsClient;
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (m_HCCellars) { m_HCCellars.HCSample(timeslice); }
    }

    override void OnMissionFinish()
    {
        if (m_HCCellars) { m_HCCellars.HCClear(); }
        m_HCCellars = null;
        super.OnMissionFinish();
    }
}
