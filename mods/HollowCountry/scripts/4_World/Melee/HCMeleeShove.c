// MEL-14 guard shove: attack while blocking plays the vanilla light swing in place
// and lands as a no-damage knock-back on infected (the vanilla kick/push ammo path).
// Native evidence, scripts-1.30.164289 (paths relative to the scripts root), file
// 4_World/Entities/ManBase/DayZPlayer/DayZPlayerMeleeFightLogic_LightHeavy.c (FL):
// - FL:137-200 HandleFightLogic; FL:155-157 vanilla drops attack input while
//   m_IsInBlock, so block + attack was a dead input; FL:254-270 block = raised
//   erect with the move input beyond +-130 degrees (walking back).
// - FL:386-449 HandleInitialMeleeErc start sequence mirrored here (Update,
//   GetTargetData, StartCommand_Melee2, stamina, broken-leg shock, DisableControls).
// - FL:282-334 HandleHitEvent -> FL:577-702 EvaluateHit/EvaluateHit_Common: when
//   DummyHitSelector (FL:768-782) returns true the server applies its ammo through
//   DamageSystem.CloseCombatDamage (FL:692-701). Vanilla already routes KICK
//   ("kick on back or push from erc", FL:772) to Dummy_Heavy this way.
// - FL:451-479 prone kick costs EStaminaModifiers.MELEE_HEAVY; mirrored.
// - FL:504-530 HandleComboHit; held while the shove hit is pending.
// - Dummy_Heavy (vanilla CfgAmmo: hitAnimation=1, zero Health/Blood/Shock) makes
//   ZombieBase.EvaluateDamageHitAnimation choose a heavy hit (ZombieBase.c:900-905)
//   and HandleDamageHit start it (ZombieBase.c:867-897).
// - 4_World/Entities/DayZPlayerImplement.c:494 GetDeltaT (the CommandHandler pDt set
//   at :2290, the replayed simulation step) times the cooldown on both peers;
//   :2676-2678 HandleFightLogic call site; :1491 StartCommand_Melee2 (3_Game/human.c).
// - 3_Game/human.c:495 SetMeleeBlock; :561 HIT_TYPE_LIGHT.
// The start is predicted: every gate below reads state both peers share (input,
// stance, hands, stamina, sim-time cooldown), and the values are compiled-in literals.
// The effect is server-only (CloseCombatDamage). Players and AI characters hit by a
// shove get Dummy_Light (no damage, no fullbody stagger): no PvP change.
class HCMeleeShove
{
    static bool Enabled = true;
    static float CooldownSeconds = 1.2;
    static float StartGraceSeconds = 0.5;
    static const string HC_AMMO = "HCMeleeShove";
    static const string VANILLA_AMMO = "Dummy_Heavy";
    protected static int s_AmmoState;
    protected static int s_Logged;

    // HCMeleeShove (lead-owned CfgAmmo, inherits Dummy_Heavy) when installed, so the
    // HC melee rules skip it via HCMeleeAmmo.IsHC; otherwise the vanilla push ammo.
    static string HCAmmo()
    {
        if (s_AmmoState == 0)
        {
            s_AmmoState = 2;
            if (GetGame().ConfigIsExisting("CfgAmmo " + HCMeleeShove.HC_AMMO)) { s_AmmoState = 1; }
        }
        if (s_AmmoState == 1) { return HCMeleeShove.HC_AMMO; }
        return HCMeleeShove.VANILLA_AMMO;
    }

    static void HCLog(string kind, string ammo)
    {
        if (!GetGame().IsServer() || !HCMeleeModule.Active()) { return; }
        if (s_Logged >= HCMeleeConfig.HCGet().LogLimit) { return; }
        s_Logged++;
        Print("[HC Melee] shove count=" + s_Logged.ToString() + " target=" + kind + " ammo=" + ammo);
    }
}

modded class DayZPlayerMeleeFightLogic_LightHeavy
{
    protected bool m_HCShove;
    protected bool m_HCShoveSeen;
    protected float m_HCShoveAge;
    protected float m_HCShoveCooldown;
    protected string m_HCShoveKind;
    protected string m_HCShoveAmmo;

    bool HCIsShoving() { return m_HCShove; }

    protected void HCShoveClear()
    {
        m_HCShove = false;
        m_HCShoveSeen = false;
        m_HCShoveAge = 0;
        m_HCShoveKind = "";
        m_HCShoveAmmo = "";
    }

    // Sim-time bookkeeping; clears a shove whose Melee2 ended or never started
    // (for example cancelled by a hit) so it can never leak onto a later swing.
    protected void HCShoveTick(int pCurrentCommandID)
    {
        float dt = m_Player.GetDeltaT();
        if (m_HCShoveCooldown > 0) { m_HCShoveCooldown -= dt; }
        if (!m_HCShove) { return; }
        if (pCurrentCommandID == DayZPlayerConstants.COMMANDID_MELEE2)
        {
            m_HCShoveSeen = true;
            return;
        }
        m_HCShoveAge += dt;
        if (m_HCShoveSeen || m_HCShoveAge > HCMeleeShove.StartGraceSeconds) { HCShoveClear(); }
    }

    protected bool HCShoveStart(int pCurrentCommandID, HumanInputController pInputs, EntityAI pEntityInHands, HumanMovementState pMovementState)
    {
        if (!HCMeleeShove.Enabled || m_HCShove || m_HCShoveCooldown > 0) { return false; }
        if (pCurrentCommandID != DayZPlayerConstants.COMMANDID_MOVE) { return false; }
        if (!m_IsInBlock || m_IsEvading || !pInputs.IsAttackButtonDown()) { return false; }
        if (pMovementState.m_iStanceIdx != DayZPlayerConstants.STANCEIDX_RAISEDERECT) { return false; }

        InventoryItem itemInHands = InventoryItem.Cast(pEntityInHands);
        // Fists or melee weapons only; the firearm bash already knocks back (hitAnimation=1).
        if (itemInHands && (itemInHands.IsWeapon() || !itemInHands.IsMeleeWeapon())) { return false; }

        HumanInventoryWithFSM invFSM = HumanInventoryWithFSM.Cast(m_Player.GetHumanInventory());
        if (invFSM && !invFSM.IsIdle()) { return false; }
        HumanCommandMove hcm = m_Player.GetCommand_Move();
        if (!hcm) { return false; }
        // Real players only (owner client: controlled; server: identity). AI keeps vanilla.
        if (!m_Player.GetIdentity() && !m_Player.IsControlledPlayer()) { return false; }
        if (!m_Player.CanConsumeStamina(EStaminaConsumers.MELEE_HEAVY)) { return false; }

        m_HitType = EMeleeHitType.LIGHT;
        m_MeleeCombat.Update(itemInHands, m_HitType);
        // A stealth finisher keeps its vanilla meaning; no shove over it (FL:400-418).
        if (m_MeleeCombat.GetFinisherType() != -1) { return false; }

        EntityAI target;
        EMeleeTargetType targetType;
        GetTargetData(target, targetType);

        hcm.SetMeleeBlock(false);
        SetBlock(false);
        // 1.0 = in place: a shove never lunges (FL:120-135 semantics).
        m_Player.StartCommand_Melee2(target, HumanCommandMelee2.HIT_TYPE_LIGHT, 1.0, m_MeleeCombat.GetHitPos());
        m_Player.DepleteStamina(EStaminaModifiers.MELEE_HEAVY);
        if (m_Player.GetBrokenLegs() == eBrokenLegs.BROKEN_LEGS)
        {
            m_Player.m_ShockHandler.SetShock(PlayerConstants.BROKEN_LEGS_LIGHT_MELEE_SHOCK);
            m_Player.m_ShockHandler.CheckValue(true);
        }

        HCShoveClear();
        m_HCShove = true;
        m_HCShoveCooldown = HCMeleeShove.CooldownSeconds;
        m_WasPreviousHitProcessed = false;
        DisableControls();
        return true;
    }

    override bool HandleFightLogic(int pCurrentCommandID, HumanInputController pInputs, EntityAI pEntityInHands, HumanMovementState pMovementState, out bool pContinueAttack)
    {
        HCShoveTick(pCurrentCommandID);
        if (HCShoveStart(pCurrentCommandID, pInputs, pEntityInHands, pMovementState)) { return true; }
        return super.HandleFightLogic(pCurrentCommandID, pInputs, pEntityInHands, pMovementState, pContinueAttack);
    }

    override protected bool HandleHitEvent(int pCurrentCommandID, HumanInputController pInputs, InventoryItem itemInHands, HumanMovementState pMovementState, out bool pContinueAttack)
    {
        if (!m_HCShove) { return super.HandleHitEvent(pCurrentCommandID, pInputs, itemInHands, pMovementState, pContinueAttack); }
        bool hit = super.HandleHitEvent(pCurrentCommandID, pInputs, itemInHands, pMovementState, pContinueAttack);
        if (hit)
        {
            if (m_HCShoveKind != "") { HCMeleeShove.HCLog(m_HCShoveKind, m_HCShoveAmmo); }
            HCShoveClear();
        }
        return hit;
    }

    // Hold follow-up combos until the shove's own hit event has been evaluated, so
    // the next swing can never turn the pending shove into a damaging hit.
    override protected bool HandleComboHit(int pCurrentCommandID, HumanInputController pInputs, InventoryItem itemInHands, HumanMovementState pMovementState, out bool pContinueAttack)
    {
        if (m_HCShove) { return false; }
        return super.HandleComboHit(pCurrentCommandID, pInputs, itemInHands, pMovementState, pContinueAttack);
    }

    override protected bool DummyHitSelector(EMeleeHitType hitType, out string ammoType)
    {
        if (!m_HCShove) { return super.DummyHitSelector(hitType, ammoType); }
        EntityAI target = m_MeleeCombat.GetTargetEntity();
        if (target && target.IsInherited(DayZPlayer))
        {
            ammoType = DUMMY_LIGHT_AMMO;
            m_HCShoveKind = "player";
        }
        else
        {
            ammoType = HCMeleeShove.HCAmmo();
            m_HCShoveKind = "other";
            if (target && target.IsInherited(DayZInfected)) { m_HCShoveKind = "infected"; }
        }
        m_HCShoveAmmo = ammoType;
        return true;
    }
}
