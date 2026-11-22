// Sole COT call boundary, enforced by HC-E027.
// #228/#289. Public API evidence from installed COT item 1564026768, addons/scripts.pbo:
// config.bin: CfgPatches/JM_COT_Scripts. HCX must require JM_COT_Scripts
// alongside JM_CF_Scripts so COT's World classes load before this binding.
// 3_Game/CommunityOnlineTools/StaticFunctions.c:2 defines JM_COT_LOADED.
// COT is a declared HCX dependency in tools/setup/workshop_mods.json.
// Bind unconditionally: a missing dependency must fail compilation instead of
// silently removing the provider behind a preprocessor guard (#289).
// 4_World/CommunityOnlineTools/Classes/Permissions/JMPermissionManager.c:
// :27-34 constructor initializes service collections/root; :14 m_MissionLoaded;
// :363-365 SetMissionLoaded; :659-677 RegisterPermission (INHERIT default,
// registration before mission load only); :940-945 GetPermissionsManager;
// :121-124 GetPlayer. JMPlayerInstance.c:300-338 HasPermission checks live roles.
// Native scripts-1.30.164289/3_Game/gameplay.c:636 GetGame, :368 GetId;
// 3_Game/Global/Game.c:1120 IsServer. No Expansion calls or vendor code copied.
// Constant work per check, no tick controller, no identity logging/profile reads.
modded class JMPermissionManager
{
    protected bool m_HCXCotRegistered;

    void JMPermissionManager()
    {
        if (!RootPermission || m_MissionLoaded) { return; }
        RegisterPermission(HCAdminPermissionAdapter.PERMISSION);
        m_HCXCotRegistered = true;
    }

    bool HCXCotReady()
    {
        return m_HCXCotRegistered && m_MissionLoaded && RootPermission && Players && Roles;
    }
}

class HCXCotPermissionPort : HCAdminPermissionPort
{
    protected string m_HCReason;

    string HCProblem() { return m_HCReason; }

    override bool HCReady()
    {
        m_HCReason = "SERVER_REQUIRED";
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        JMPermissionManager manager = GetPermissionsManager();
        m_HCReason = "COT_NOT_READY";
        if (!manager || !manager.HCXCotReady()) { return false; }
        m_HCReason = "";
        return true;
    }

    override bool HCAllowed(PlayerIdentity sender, string permission)
    {
        m_HCReason = "IDENTITY_REQUIRED";
        if (!sender) { return false; }
        m_HCReason = "PERMISSION_UNSUPPORTED";
        if (permission != HCAdminPermissionAdapter.PERMISSION || !HCReady()) { return false; }
        JMPermissionManager manager = GetPermissionsManager();
        m_HCReason = "COT_MANAGER_MISSING";
        if (!manager) { return false; }
        // Query only the authenticated server GUID. Missing players deny quietly;
        // the manager HasPermission overload logs their identity on a miss and
        // has an offline grant shortcut. Neither belongs in HC authorization.
        JMPlayerInstance instance = manager.GetPlayer(sender.GetId());
        m_HCReason = "COT_PLAYER_MISSING";
        if (!instance) { return false; }
        m_HCReason = "COT_PERMISSION_DENIED";
        if (!instance.HasPermission(permission)) { return false; }
        m_HCReason = "";
        return true;
    }
}

modded class HCAdminPermissionAdapter
{
    override HCAdminPermissionPort HCDefaultPort()
    {
        HCXCotPermissionPort port = new HCXCotPermissionPort;
        return port;
    }
}
