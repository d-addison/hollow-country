// Read-only HUD. Native reference: scripts-1.30.164289.
// GetPlayerLoad/GetWeightEx already includes hands; never add them again.
class HCStaminaHUD
{
    protected Widget mHCRoot;
    protected TextWidget mHCLoad;
    protected TextWidget mHCStamina;
    protected TextWidget mHCPenalty;
    protected ProgressBarWidget mHCBar;
    protected ProgressBarWidget mHCWeightBar;
    protected TextWidget mHCWeightScale;
    protected PlayerBase mHCViewer;
    protected float mHCElapsed = 0.25;

    static float Percent(float current, float capacity)
    {
        if (!(current >= 0 && current <= 1000000))
        {
            return 0;
        }
        // Weight references can exceed the bounded measured load.
        if (!(capacity > 0 && capacity <= 1000000000))
        {
            return 0;
        }
        return Math.Clamp(current / capacity * 100, 0, 100);
    }

    void Hide()
    {
        if (mHCRoot)
        {
            mHCRoot.Show(false);
        }
        mHCElapsed = 0.25;
    }

    void Reset()
    {
        if (mHCRoot)
        {
            mHCRoot.Unlink();
        }
        mHCRoot = null;
        mHCLoad = null;
        mHCStamina = null;
        mHCPenalty = null;
        mHCBar = null;
        mHCWeightBar = null;
        mHCWeightScale = null;
        mHCViewer = null;
        mHCElapsed = 0.25;
    }

    bool Prepare()
    {
        if (!mHCRoot)
        {
            mHCRoot = GetGame().GetWorkspace().CreateWidgets("HollowCountry/gui/layouts/hc_stamina.layout");
            if (!mHCRoot)
            {
                return false;
            }
            mHCLoad = TextWidget.Cast(mHCRoot.FindAnyWidget("HCStaminaLoad"));
            mHCStamina = TextWidget.Cast(mHCRoot.FindAnyWidget("HCStaminaValues"));
            mHCPenalty = TextWidget.Cast(mHCRoot.FindAnyWidget("HCStaminaPenalty"));
            mHCBar = ProgressBarWidget.Cast(mHCRoot.FindAnyWidget("HCStaminaBar"));
            mHCWeightBar = ProgressBarWidget.Cast(mHCRoot.FindAnyWidget("HCWeightBar"));
            mHCWeightScale = TextWidget.Cast(mHCRoot.FindAnyWidget("HCWeightScale"));
        }
        if (!mHCLoad || !mHCStamina || !mHCPenalty)
        {
            return false;
        }
        return mHCBar && mHCWeightBar && mHCWeightScale;
    }

    void Update(float timeslice)
    {
        if (GetGame().IsServer())
        {
            Reset();
            return;
        }
        if (!HCStaminaIntegration.Enabled())
        {
            Hide();
            return;
        }
        PlayerBase viewer = PlayerBase.Cast(GetGame().GetPlayer());
        if (!viewer)
        {
            Hide();
            return;
        }
        if (!viewer.IsAlive() || viewer.IsUnconscious())
        {
            Hide();
            return;
        }
        if (GetGame().GetUIManager().GetMenu())
        {
            Hide();
            return;
        }
        // Follow native ContinuousActionProgress: profile and hide-hotkey flags.
        Mission mission = GetGame().GetMission();
        if (!mission)
        {
            Hide();
            return;
        }
        IngameHud hud = IngameHud.Cast(mission.GetHud());
        if (!hud)
        {
            Hide();
            return;
        }
        IngameHudVisibility visibility = hud.GetHudVisibility();
        if (!visibility)
        {
            Hide();
            return;
        }
        if (visibility.IsContextFlagActive(IngameHudVisibility.HUD_HIDE_FLAGS))
        {
            Hide();
            return;
        }
        if (viewer != mHCViewer)
        {
            Reset();
            mHCViewer = viewer;
        }
        if (!(timeslice >= 0 && timeslice <= 60))
        {
            Hide();
            return;
        }
        mHCElapsed = mHCElapsed + timeslice;
        if (mHCElapsed < 0.25)
        {
            return;
        }
        // One sample per eligible update; no catch-up loop or inventory scan.
        mHCElapsed = 0;
        StaminaHandler handler = viewer.GetStaminaHandler();
        if (!handler)
        {
            Hide();
            return;
        }
        float grams = viewer.GetPlayerLoad();
        float current = handler.GetSyncedStamina();
        float capacity = handler.GetSyncedStaminaCap();
        float maximum = handler.GetStaminaMax();
        float minimum = CfgGameplayHandler.GetStaminaMinCap();
        float threshold = CfgGameplayHandler.GetStaminaWeightLimitThreshold();
        float loss = CfgGameplayHandler.GetStaminaKgToStaminaPercentPenalty();
        // Reject unavailable/nonfinite samples; limits are display guards.
        if (!(grams >= 0 && grams <= 1000000))
        {
            Hide();
            return;
        }
        if (!(maximum > 0 && maximum <= 1000000))
        {
            Hide();
            return;
        }
        if (!(minimum >= 0 && minimum <= maximum))
        {
            Hide();
            return;
        }
        if (!(current >= 0 && current <= maximum))
        {
            Hide();
            return;
        }
        if (!(capacity > 0 && capacity <= maximum))
        {
            Hide();
            return;
        }
        if (!(threshold >= 0 && threshold <= 1000000))
        {
            Hide();
            return;
        }
        if (!(loss >= 0 && loss <= 1000000))
        {
            Hide();
            return;
        }
        if (!Prepare())
        {
            Reset();
            return;
        }
        // A capacity-floor reference, never a maximum carrying allowance.
        float referenceGrams = 0;
        if (loss > 0)
        {
            referenceGrams = threshold + (maximum - minimum) / loss * 1000;
        }
        bool floorReference = referenceGrams > 0 && referenceGrams <= 1000000000;
        if (floorReference)
        {
            mHCWeightScale.SetText(string.Format("Weight bar: %1 kg at minimum stamina capacity (%2 units)", Math.Round(referenceGrams / 100) / 10, minimum));
        }
        else
        {
            // Adaptive 10 kg display divisions; no invented gameplay limit.
            referenceGrams = (Math.Floor(grams / 10000) + 1) * 10000;
            string reason = "Weight penalty disabled";
            if (loss > 0)
            {
                reason = "Capacity reference exceeds display range";
                if (maximum == minimum)
                {
                    reason = "Capacity already at minimum";
                }
            }
            mHCWeightScale.SetText(string.Format("%1; display scale 0-%2 kg", reason, referenceGrams / 1000));
        }
        mHCWeightBar.SetCurrent(HCStaminaHUD.Percent(grams, referenceGrams));
        mHCLoad.SetText(string.Format("Load: %1 kg", Math.Round(grams / 100) / 10));
        mHCStamina.SetText(string.Format("Stamina: %1 / %2 units (maximum %3)", Math.Round(current * 10) / 10, Math.Round(capacity * 10) / 10, Math.Round(maximum * 10) / 10));
        mHCPenalty.SetText(string.Format("Weight penalty above %1 kg: %2 units/kg", threshold / 1000, loss));
        mHCBar.SetCurrent(HCStaminaHUD.Percent(current, capacity));
        mHCRoot.Show(true);
    }
}

modded class MissionGameplay
{
    protected ref HCStaminaHUD mHCStaminaDisplay;

    override void OnInit()
    {
        super.OnInit();
        if (GetGame().IsServer())
        {
            return;
        }
        if (!mHCStaminaDisplay)
        {
            mHCStaminaDisplay = new HCStaminaHUD;
        }
    }

    override void OnUpdate(float timeslice)
    {
        super.OnUpdate(timeslice);
        if (mHCStaminaDisplay)
        {
            mHCStaminaDisplay.Update(timeslice);
        }
    }

    override void OnMissionFinish()
    {
        if (mHCStaminaDisplay)
        {
            mHCStaminaDisplay.Reset();
        }
        mHCStaminaDisplay = null;
        super.OnMissionFinish();
    }
}
