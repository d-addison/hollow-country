// #137 infected anti-cheese per-infected hook. Uses ONLY the vanilla mod hook
// ModCommandHandlerBefore (ZombieBase.c:203, called first in CommandHandler
// :198-277), so it composes with HCInfectedNative.c's FightLogic contact guard
// regardless of the unproven modded-class link order: our reach/batter swing is
// started and its WasHit frame resolved and consumed here, before FightLogic.
// Vanilla attack precedence is kept: we only swing where vanilla refused.
// Per frame, server only: O(1) arithmetic for admitted infected (<=16), one
// CanAttackToPosition per admitted MOVE frame (vanilla calls it every attack
// frame), a once-per-second admission probe otherwise; native rays only once
// per landed swing. No position writes, teleports or synthetic noise.
// Native evidence, installed scripts-1.30.164289:
// 4_World/Entities/Creatures/Infected/ZombieBase.c:14 m_KnuckleLand, :609-611
// m_ActualTarget/m_AttackCooldownTime/m_ActualAttackType, :631-674 WasHit branch
// (NONALIGNABLE :635, block stance :646/:652, Dummy_Light :664), :689 vehicle
// hotfix, :768 GetAttackPitch, :858 m_DamageHitToProcess, :1090 IsCrawling,
// :1060 IsBeingBackstabbed, :427-438 HandleVault (m_KnuckleLand reset);
// 3_Game/Entities/DayZInfected.c:51 WasHit, :106 GetDayZInfectedType, :107
// GetInputController, :109 StartCommand_Vault, :112 StartCommand_Attack, :115
// CanAttackToPosition, :119 GetCommand_Attack; DayZInfectedType.c:1-11 attack
// fields, :13-17 groups, :80-81 FIGHT up attacks (pitch 1), :96 ChooseAttack;
// DayZCreatureAIInputController.c:3 OverrideMovementSpeed, :9 OverrideHeading
// (absolute yaw in radians as DayZAnimal.c:466/:550 uses it);
// 3_Game/dayzplayer.c:481-482 dmgZone_leftLeg/dmgZone_rightLeg AI hit components;
// 3_Game/DamageSystem.c:22 CloseCombatDamage, :23 CloseCombatDamageName;
// 3_Game/Entities/EntityAI.c:3850 GetMeleeTargetType; 3_Game/human.c:1528
// GetCommand_Vehicle; DayZPlayerImplement.c:252 GetMeleeFightLogic;
// DayZPlayerMeleeFightLogic_LightHeavy.c:53 IsInBlock; MiscGameplayFunctions.c:791
// GetHeadingVector; 1_Core/proto/EnMath3D.c:484 AngleFromPosition, :18 Vector;
// 3_Game/constants.c:1127 AI_MAX_BLOCKABLE_ANGLE, :33 ObjIntersectFire;
// 1_Core/proto/EnConvert.c:353 VectorToAngles, :196 Distance;
// 3_Game/Global/DayZPhysics.c:199 RaycastRV; 3_Game/Entities/Object.c:287
// GetPosition, :314 GetDirection, :517 IsAlive. Runtime acceptance PENDING.
modded class ZombieBase
{
    protected int m_HCReachSlot = -1;
    protected float m_HCReachNextAdmit;
    protected bool m_HCReachSteering;
    protected int m_HCReachArmed;
    protected float m_HCReachArmedAt;
    protected Transport m_HCReachVehicle;
    protected PlayerBase m_HCReachPlayer;
    protected DayZInfectedAttackType m_HCReachAttack;

    override bool ModCommandHandlerBefore(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        bool consumed = super.ModCommandHandlerBefore(pDt, pCurrentCommandID, pCurrentCommandFinished);
        if (!GetGame().IsServer()) { return consumed; }
        // An armed swing resolves its own WasHit frame even if the slot expired.
        if (pCurrentCommandID == DayZInfectedConstants.COMMANDID_ATTACK)
        {
            if (m_HCReachArmed > 0 && HCReachResolve()) { return true; }
        }
        else if (m_HCReachArmed > 0 && GetGame().GetTickTime() - m_HCReachArmedAt > 0.5)
        {
            // The swing ended or was interrupted without a hit frame.
            m_HCReachArmed = 0;
            m_HCReachPlayer = null;
            m_HCReachAttack = null;
            m_HCReachVehicle = null;
        }
        HCInfectedReachModule reach = HCInfectedReachModule.Active();
        HCInfectedReachState state = null;
        if (reach) { state = reach.StateFor(this, m_HCReachSlot); }
        if (!state)
        {
            m_HCReachSlot = -1;
            HCReachReleaseSteering();
            if (reach && !consumed && !pCurrentCommandFinished && pCurrentCommandID == DayZInfectedConstants.COMMANDID_MOVE)
            {
                HCReachProbe(reach);
            }
            return consumed;
        }
        if (consumed || pCurrentCommandFinished || pCurrentCommandID != DayZInfectedConstants.COMMANDID_MOVE)
        {
            return consumed;
        }
        return HCReachMove(reach, state);
    }

    // Once per second while unslotted: CHASE/FIGHT infected whose own native
    // target is a player standing 0.8 m+ above it, or seated in a vehicle,
    // within 4 m horizontal. Never chooses or changes the native target.
    protected void HCReachProbe(HCInfectedReachModule reach)
    {
        float now = GetGame().GetTickTime();
        if (now < m_HCReachNextAdmit) { return; }
        m_HCReachNextAdmit = now + 1;
        if (!IsAlive() || IsCrawling() || IsBeingBackstabbed()) { return; }
        DayZInfectedInputController controller = GetInputController();
        if (!controller) { return; }
        int mind = controller.GetMindState();
        if (mind != DayZInfectedConstants.MINDSTATE_CHASE && mind != DayZInfectedConstants.MINDSTATE_FIGHT) { return; }
        PlayerBase target = PlayerBase.Cast(controller.GetTargetEntity());
        if (!target || !target.IsAlive()) { return; }
        vector delta = target.GetPosition() - GetPosition();
        float horizontal = Math.Sqrt(delta[0] * delta[0] + delta[2] * delta[2]);
        if (horizontal > 4) { return; }
        if (delta[1] < 0.8 && !target.GetCommand_Vehicle()) { return; }
        m_HCReachSlot = reach.Admit(this, target, now);
    }

    protected bool HCReachMove(HCInfectedReachModule reach, HCInfectedReachState state)
    {
        DayZInfectedInputController controller = GetInputController();
        PlayerBase target = state.Target;
        if (!controller || !target || !IsAlive() || IsCrawling() || IsBeingBackstabbed())
        {
            HCReachReleaseSteering();
            return false;
        }
        // Re-check the native target every frame: the slot's target is only
        // refreshed on the module tick, and a retargeted infected must never
        // strike or steer toward its previous player.
        int moveMind = controller.GetMindState();
        if (controller.GetTargetEntity() != target || (moveMind != DayZInfectedConstants.MINDSTATE_CHASE && moveMind != DayZInfectedConstants.MINDSTATE_FIGHT))
        {
            HCReachReleaseSteering();
            return false;
        }
        float now = GetGame().GetTickTime();
        vector own = GetPosition();
        vector aim = target.GetPosition();
        float vertical = aim[1] - own[1];
        float dx = aim[0] - own[0];
        float dz = aim[2] - own[2];
        float horizontal = Math.Sqrt(dx * dx + dz * dz);

        // HC-47: no forced locomotion/vault without native traversal receipts.
        // Clearing transient intent leaves native movement/audio intact.
        if (!HCInfectedReachPolicy.HCForcedMovementSupported())
        {
            state.Phase = HCInfectedReachPolicy.PhaseNone();
            state.VaultType = -1;
        }
        // Unreachable back-off: native locomotion steered by controller
        // overrides, re-applied each frame, released the moment it ends.
        if (state.Phase != HCInfectedReachPolicy.PhaseNone())
        {
            int next = HCInfectedReachPolicy.NextPhase(state.Phase, now - state.PhaseSince, horizontal);
            if (vertical < 0.5) { next = HCInfectedReachPolicy.PhaseNone(); }
            if (next != state.Phase)
            {
                state.Phase = next;
                state.PhaseSince = now;
                if (next == HCInfectedReachPolicy.PhaseNone()) { state.BackoffAfter = now + 4; }
            }
        }
        if (state.Phase != HCInfectedReachPolicy.PhaseNone())
        {
            float toward = Vector(dx, 0, dz).VectorToAngles()[0];
            float yaw = HCInfectedReachPolicy.PhaseYaw(state.Phase, toward, state.Side);
            controller.OverrideMovementSpeed(true, HCInfectedReachPolicy.PhaseSpeed(state.Phase));
            controller.OverrideHeading(true, yaw * Math.DEG2RAD);
            m_HCReachSteering = true;
            return false;
        }
        HCReachReleaseSteering();
        if (m_DamageHitToProcess) { return false; }

        // Vault experiment: native command only, never a position write.
        if (state.VaultType >= 0)
        {
            int vaultType = state.VaultType;
            state.VaultType = -1;
            if (!reach.VaultRetired() && vertical >= 0.8 && horizontal <= 1.6)
            {
                reach.VaultStarted(state, own[1], now, vaultType);
                m_KnuckleLand = false;
                StartCommand_Vault(vaultType);
                return true;
            }
        }

        if (now < state.NextStrike) { return false; }
        DayZInfectedType infectedType = GetDayZInfectedType();
        if (!infectedType) { return false; }
        bool fresh = now - state.LineAt <= 2.5;
        bool facing = HCInfectedReachModule.FacingDegrees(this, dx, dz, horizontal) <= 35;
        bool vanillaCan = CanAttackToPosition(aim) && vector.Distance(aim, own) <= 1.7;
        // Leg strikes remain explicitly refused by HC-47 qualification. Their
        // disabled flag (or a ray miss) cannot negate native player reach.
        bool legs = HCInfectedReachPolicy.HCExtendedReachSupported() && HCInfectedReachPolicy.MayStrike(vertical, horizontal, 1.7, state.LineClear, fresh, true, vanillaCan);
        bool reachPossible = vanillaCan || (legs && facing);
        DayZInfectedAttackType attack = null;

        if (state.Vehicle && now - state.VehicleAt <= 2.5)
        {
            bool seated = state.InVehicle && target.GetCommand_Vehicle() != null;
            if (HCInfectedReachPolicy.MayBatter(seated, state.OnVehicle, reachPossible, state.VehicleContact, now, reach.VehicleNextHit(state.Vehicle)))
            {
                attack = infectedType.ChooseAttack(DayZInfectedAttackGroupType.FIGHT, 1.0, 0);
                if (attack && reach.ReserveVehicleHit(state.Vehicle, now))
                {
                    // The swing targets the vehicle, never the occupant, so even a
                    // vanilla fallback hit frame cannot reach a seated player.
                    m_ActualTarget = state.Vehicle;
                    m_ActualAttackType = attack;
                    m_HCReachAttack = attack;
                    m_HCReachVehicle = state.Vehicle;
                    m_HCReachPlayer = target;
                    m_HCReachArmed = 2;
                    m_HCReachArmedAt = now;
                    StartCommand_Attack(state.Vehicle, attack.m_Type, attack.m_Subtype);
                    m_AttackCooldownTime = attack.m_Cooldown;
                    state.NextStrike = now + 2;
                    return true;
                }
            }
        }

        if (!legs || !facing || target.GetCommand_Vehicle()) { return false; }
        attack = infectedType.ChooseAttack(DayZInfectedAttackGroupType.FIGHT, horizontal, 1);
        if (!attack) { return false; }
        m_ActualTarget = target;
        m_ActualAttackType = attack;
        m_HCReachAttack = attack;
        m_HCReachVehicle = null;
        m_HCReachPlayer = target;
        m_HCReachArmed = 1;
        m_HCReachArmedAt = now;
        StartCommand_Attack(target, attack.m_Type, attack.m_Subtype);
        m_AttackCooldownTime = attack.m_Cooldown;
        state.NextStrike = now + 1.5;
        return true;
    }

    // Returns true only on the WasHit frame of our own swing; that frame is
    // consumed so vanilla FightLogic cannot apply a second (or an occupant) hit.
    protected bool HCReachResolve()
    {
        DayZInfectedCommandAttack command = GetCommand_Attack();
        if (!command || !command.WasHit()) { return false; }
        int kind = m_HCReachArmed;
        m_HCReachArmed = 0;
        HCInfectedReachModule reach = HCInfectedReachModule.Active();
        if (kind == 2)
        {
            HCReachHitVehicle(reach);
        }
        else
        {
            HCReachHitLegs(reach);
        }
        m_HCReachPlayer = null;
        m_HCReachAttack = null;
        return true;
    }

    // HC-47 native source facts, re-read at WasHit rather than trusting the
    // admission slot or cached LOS. DayZInfectedInputController.c:9-10;
    // ZombieBase.c:609-674 native attack/hit lifecycle; :1060/:1090 exclusions.
    protected bool HCReachCurrentTarget(PlayerBase target)
    {
        if (!target || !target.IsAlive() || !IsAlive() || IsCrawling() || IsBeingBackstabbed()) { return false; }
        DayZInfectedInputController controller = GetInputController();
        if (!controller || controller.GetTargetEntity() != target) { return false; }
        int mind = controller.GetMindState();
        return mind == DayZInfectedConstants.MINDSTATE_CHASE || mind == DayZInfectedConstants.MINDSTATE_FIGHT;
    }

    // One sorted first-contact ray; every non-target obstruction refuses. A
    // surface near the shin may be a closed door/wall, never a reach receipt.
    // Same endpoints as the existing ReachModule.LineCheck (no added range).
    // DayZPhysics.c:199 RaycastRV, EntityAI.c:879 GetHierarchyRoot;
    // Object.c:287 GetPosition, EnScript.c:743/:750 set Count/Get.
    protected bool HCReachContactLine(PlayerBase target)
    {
        if (!HCInfectedReachPolicy.HCThreatTakeContact()) { return false; }
        vector origin = GetPosition() + HCInfectedReachPolicy.HC_CONTACT_ORIGIN_OFFSET;
        vector finish = target.GetPosition() + HCInfectedReachPolicy.HC_CONTACT_TARGET_OFFSET;
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, hits, null, this, true, false, ObjIntersectFire);
        if (!hit) { return true; }
        if (hits.Count() == 0) { return false; }
        Object first = hits.Get(0);
        EntityAI entity = EntityAI.Cast(first);
        return first == target || (entity && entity.GetHierarchyRoot() == target);
    }

    protected void HCReachHitLegs(HCInfectedReachModule reach)
    {
        PlayerBase target = PlayerBase.Cast(m_ActualTarget);
        if (!reach || !target || !target.IsAlive() || !m_HCReachAttack) { return; }
        if (target.GetMeleeTargetType() == EMeleeTargetType.NONALIGNABLE || target.GetCommand_Vehicle()) { return; }
        if (target != m_HCReachPlayer || !HCReachCurrentTarget(target)) { return; }
        vector own = GetPosition();
        vector aim = target.GetPosition();
        // Native permission AND native selected attack's full 3D distance.
        // DayZInfected.c:115 CanAttackToPosition; ZombieBase.c:649 distance.
        // No horizontal extension, contact epsilon or remembered LOS bypass.
        if (!CanAttackToPosition(aim) || vector.Distance(own, aim) > m_HCReachAttack.m_Distance) { return; }
        if (!HCReachContactLine(target))
        {
            reach.CountStrike(false);
            return;
        }
        string ammo = m_HCReachAttack.m_AmmoType;
        DayZPlayerMeleeFightLogic_LightHeavy melee = target.GetMeleeFightLogic();
        if (melee && melee.IsInBlock())
        {
            float angle = Math.RAD2DEG * Math.AbsFloat(Math3D.AngleFromPosition(aim, MiscGameplayFunctions.GetHeadingVector(target), own));
            // Vanilla parity: a blocked light attack plays without damage.
            if (angle <= GameConstants.AI_MAX_BLOCKABLE_ANGLE) { ammo = "Dummy_Light"; }
        }
        string zone = "dmgZone_leftLeg";
        if (Math.RandomInt(0, 2) == 1) { zone = "dmgZone_rightLeg"; }
        DamageSystem.CloseCombatDamageName(this, target, zone, ammo, aim + "0 0.5 0");
        reach.CountStrike(true);
        reach.Landed(reach.StateFor(this, m_HCReachSlot), GetGame().GetTickTime());
    }

    protected void HCReachHitVehicle(HCInfectedReachModule reach)
    {
        Transport vehicle = m_HCReachVehicle;
        m_HCReachVehicle = null;
        if (!reach || !vehicle || !m_HCReachAttack) { return; }
        if (!HCReachCurrentTarget(m_HCReachPlayer)) { return; }
        vector origin = GetPosition() + "0 1.0 0";
        vector toward = vehicle.GetPosition() - GetPosition();
        vector finish = origin + Vector(toward[0], 0, toward[2]).Normalized() * 1.9;
        vector contact;
        vector normal;
        int component;
        set<Object> hits = new set<Object>;
        bool hit = DayZPhysics.RaycastRV(origin, finish, contact, normal, component, hits, null, this, true, false, ObjIntersectFire);
        if (!hit || hits.Count() == 0) { return; }
        Object struck = hits.Get(0);
        if (HCInfectedReachModule.HCRootVehicle(struck) != vehicle) { return; }
        // Native close-combat damage to the struck vehicle component; the
        // occupant is never damaged by this path (vanilla hotfix :689 kept).
        DamageSystem.CloseCombatDamage(this, struck, component, m_HCReachAttack.m_AmmoType, contact);
        reach.CountBatter();
    }

    protected void HCReachReleaseSteering()
    {
        if (!m_HCReachSteering) { return; }
        m_HCReachSteering = false;
        DayZInfectedInputController controller = GetInputController();
        if (!controller) { return; }
        controller.OverrideMovementSpeed(false, 0);
        controller.OverrideHeading(false, 0);
    }
}
