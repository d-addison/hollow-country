// All native citations below are relative to scripts-1.30.164289.
// Lifecycle and counters use HCModule/HCModuleReadiness, with no polling controller.
class HCTinCanLanternModule extends HCModule
{
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    protected bool m_Started;
    protected static bool s_Enabled;

    override string GetName() { return "TinCanLantern"; }
    override bool IsEnabled(HCSettings settings) { return settings.EnableTinCanLantern; }
    override bool RequiresSharedSaves() { return false; }
    override void RegisterUses() { HCModuleReadiness.HCRegisterUse("TinCanLantern", "lantern_lit"); }

    override void OnStart(HCSettings settings)
    {
        // 3_Game/InventoryItemType.c:316: ConfigIsExisting guards installed config.
        m_Started = GetGame().ConfigIsExisting("CfgVehicles HC_TinCanLantern EnergyManager");
        s_Enabled = settings.EnableTinCanLantern && m_Started;
        if (m_Started) { m_Status.HCPublish("ready", "item_config_registered"); }
        else { m_Status.HCPublish("refused", "assets_addon_missing"); }
    }

    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    static bool HCEnabled() { return s_Enabled; }
    override void OnStop() { s_Enabled = false; m_Started = false; m_Status.HCStop(); }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTinCanLanternModule);
    }
}

// PointLightBase.c:1-5 selects point type in the base constructor.
// PointLightBase/ChemlightLight.c:3-13: brightness 1.5, radius 7.5.
// PointLightBase/PortableGasLampLight.c:8-17: warm colour and native flicker.
// Below-chemlight provisional candle target: brightness 0.7, radius 3 m.
// No native candle class was found. Tune against the actual one-client smoke.
class HCTinCanLanternLight extends PointLightBase
{
    void HCTinCanLanternLight()
    {
        SetVisibleDuringDaylight(false);
        SetRadiusTo(3.0);
        SetBrightnessTo(0.7);
        SetDiffuseColor(1.0, 0.65, 0.28);
        SetAmbientColor(1.0, 0.65, 0.28);
        SetCastShadow(true);
        SetFlareVisible(false);
        SetFadeOutTime(0.3);
        SetFlickerAmplitude(0.08);
        SetFlickerSpeed(0.75);
    }
}

class HC_TinCanLantern extends ItemBase
{
    protected HCTinCanLanternLight m_HCLight;
    static const int HC_FLAME_SELECTION = 3; // config: can, handle, candle, flame.
    static const string HC_FLAME_ON = "HollowCountryAssets\\lantern\\flame_on.rvmat";
    static const string HC_FLAME_OFF = "HollowCountryAssets\\lantern\\flame.rvmat";

    // 4_World/Classes/ContaminatedArea/SpookyArea.c:8: native EEInit override.
    // EntityAI.c:2876-2878: simple selection false=hidden (no model animation).
    // Actions/Continuous/ActionViewBinoculars.c:37,58: native false/true usage.
    override void EEInit()
    {
        super.EEInit();
        SetSimpleHiddenSelectionState(0, false);
    }

    // ItemBase/PortableGasLamp.c:34-55; Flashlight.c:13-22,43-59.
    // ScriptedLightBase.c:165,227: one-point attachment and client-only creation.
    override void OnWorkStart()
    {
        super.OnWorkStart();
        if (!GetGame().IsServer() || !GetGame().IsMultiplayer())
        {
            if (!m_HCLight)
            {
                m_HCLight = HCTinCanLanternLight.Cast(ScriptedLightBase.CreateLight(HCTinCanLanternLight, "0 0 0", 0.1));
                if (m_HCLight) { m_HCLight.AttachOnMemoryPoint(this, "light"); }
            }
            SetSimpleHiddenSelectionState(0, true);
            SetObjectMaterial(HC_FLAME_SELECTION, HC_FLAME_ON);
        }
        // Count only an observed native server work transition, never boot/registration.
        // ItemBase/Torch.c:141-144: IsWorking is the ignition observation.
        if (GetGame().IsServer() && HasEnergyManager() && GetCompEM().IsWorking())
        {
            HCModuleReadiness.HCUseGuarded("TinCanLantern", "lantern_lit", this);
        }
    }

    // ScriptedLightBase.c:350; Roadflare.c:94-108: fade immediately on deletion.
    override void EEDelete(EntityAI parent)
    {
        if (m_HCLight) { m_HCLight.FadeOut(0); m_HCLight = null; }
        super.EEDelete(parent);
    }

    override void OnWorkStop()
    {
        super.OnWorkStop();
        if (m_HCLight) { m_HCLight.FadeOut(); m_HCLight = null; }
        if (!GetGame().IsServer() || !GetGame().IsMultiplayer())
        {
            SetSimpleHiddenSelectionState(0, false);
            SetObjectMaterial(HC_FLAME_SELECTION, HC_FLAME_OFF);
        }
    }

    // ItemBase/Torch.c:141-185,204-211: native ignition hooks; no custom action/RPC.
    override bool IsIgnited() { return HasEnergyManager() && GetCompEM().IsWorking(); }

    override bool CanBeIgnitedBy(EntityAI igniter = NULL)
    {
        if (GetGame().IsServer() && !HCTinCanLanternModule.HCEnabled()) { return false; }
        return HasEnergyManager() && !IsIgnited() && GetCompEM().CanWork() && GetCompEM().CheckWetness();
    }

    override void OnIgnitedThis(EntityAI fire_source)
    {
        if (GetGame().IsServer() && CanBeIgnitedBy(fire_source)) { GetCompEM().SwitchOn(); }
    }

    // ItemBase/Torch.c:761-765; PortableGasLamp.c:84-91.
    // ActionLightItemOnFire.c:70-129 routes match/torch ignition to OnIgnitedThis.
    // ActionTurnOffWhileInHands.c:47-52 delegates extinguishing to the energy manager.
    override void SetActions()
    {
        super.SetActions();
        AddAction(ActionLightItemOnFire);
        AddAction(ActionTurnOffWhileInHands);
        AddAction(ActionTurnOffWhileOnGround);
    }
}
