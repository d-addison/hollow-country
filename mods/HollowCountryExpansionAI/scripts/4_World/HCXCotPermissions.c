// #228. Public API evidence from installed COT item 1564026768, addons/scripts.pbo:
// 3_Game/CommunityOnlineTools/StaticFunctions.c:2 defines JM_COT_LOADED.
// 4_World/CommunityOnlineTools/Classes/Permissions/JMPermissionManager.c:
// :27-34 constructor initializes service collections/root; :14 m_MissionLoaded;
// :363-365 SetMissionLoaded; :659-677 RegisterPermission (INHERIT default,
// registration before mission load only); :940-945 GetPermissionsManager;
// :121-124 GetPlayer. JMPlayerInstance.c:300-338 HasPermission checks live roles.
// Native scripts-1.30.164289/3_Game/gameplay.c:636 GetGame, :368 GetId;
// 3_Game/Global/Game.c:1120 IsServer. No Expansion calls or vendor code copied.
// Constant work per check, no tick controller, no identity logging/profile reads.
#ifdef JM_COT_LOADED
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
    override bool HCReady()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        JMPermissionManager manager = GetPermissionsManager();
        return manager && manager.HCXCotReady();
    }

    override bool HCAllowed(PlayerIdentity sender, string permission)
    {
        if (!sender || permission != HCAdminPermissionAdapter.PERMISSION || !HCReady()) { return false; }
        JMPermissionManager manager = GetPermissionsManager();
        if (!manager) { return false; }
        // Query only the authenticated server GUID. Missing players deny quietly;
        // the manager HasPermission overload logs their identity on a miss and
        // has an offline grant shortcut. Neither belongs in HC authorization.
        JMPlayerInstance instance = manager.GetPlayer(sender.GetId());
        if (!instance) { return false; }
        return instance.HasPermission(permission);
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
#endif
