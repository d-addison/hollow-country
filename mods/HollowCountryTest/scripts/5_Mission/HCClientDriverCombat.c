// Dev-only test addon (never shipped). Combat and vitals for the scripted client driver (kind combat).
// Plays like a player at the keyboard: it only reads what the client already shows and only uses the
// local player's own input overrides and the vanilla client weapon entries.
// Native scripts-1.30.164289 proofs:
//  aim      3_Game/human.c:259 OverrideAimChangeX, :262 OverrideAimChangeY, :268 OverrideRaise
//           (HumanInputControllerOverrideType :7-12); 3_Game/Global/Game.c:731
//           GetCurrentCameraPosition, :732 GetCurrentCameraDirection (the client's own view).
//  reload   4_World/Entities/ManBase/PlayerBase.c:5140 QuickReloadWeapon (the vanilla reload key:
//           :5147 ReloadWeapon picks Unjam, AttachMagazine, SwapMagazine or the multi-bullet action
//           with the WeaponManager Can* checks, client instance only), :5189 GetMagazineToReload;
//           4_World/Classes/Weapons/WeaponManager.c:874 IsRunning; 4_World/Entities/Core/Inherited/
//           Weapon.c:35 GetCurrentMuzzle, :74 IsChamberEmpty, :240 GetMagazine;
//           4_World/Entities/ItemBase/Magazine/Magazine.c:68 GetAmmoCount; Man.c:178
//           PredictiveTakeEntityToHands (rifle from the shoulder to the hands).
//  targets  3_Game/Global/Game.c:930 GetObjectsAtPosition3D once a second (reused arrays), nearest live
//           3_Game/Entities/DayZInfected.c:104 DayZInfected or identity-less PlayerBase (a server AI),
//           then one 3_Game/Global/DayZPhysics.c:199 RaycastRV line-of-sight check: only what the
//           player could see from their head.
//  vitals   PlayerBase.c:1066 IsBleeding (synced bits), :2987 GetVirtualHud;
//           4_World/Classes/VirtualHud/DisplayStatus.c:96 GetElement, DisplayElementBase.c:55
//           GetValue, DisplayElementTendency.c:3-27 (low 3 bits tendency, 4..6 = falling 1..3, next 3
//           bits the DSLevels seriousness), _constants.c:9 eDisplayElements. The server-only stat
//           getters are never read.
// Fire and melee: no retail client entry (UAInput.SyncedOverride exists only under INPUT_OVERRIDE),
// so the step aims and tracks but never shoots; the detail always says fire=unsupported.
// Bounded: at most MAX_TARGETS engagements of ENGAGE_CAP seconds each inside timeout_s, at most
// MAX_RELOADS reloads; a bleeding player or a falling or critical health tendency retreats on foot.
// Per frame: a few float operations and at most one raycast every LOS_SECONDS; nothing allocated
// after Begin.
class HCDriverVitals
{
    static int Raw(PlayerBase player, eDisplayElements element)
    {
        if (!player) { return 0; }
        VirtualHud hud = player.GetVirtualHud();
        if (!hud) { return 0; }
        DisplayElementBase item = hud.GetElement(element);
        if (!item) { return 0; }
        return item.GetValue();
    }

    // -3..3: negative is falling (the HUD's down arrows).
    static int Tendency(PlayerBase player, eDisplayElements element)
    {
        int value = HCDriverVitals.Raw(player, element);
        int tendency = value & 7;
        if (tendency > 3) { tendency = 3 - tendency; }
        return tendency;
    }

    // DSLevels: 0 normal, 1 warning, 2 critical, 3 blinking.
    static int Seriousness(PlayerBase player, eDisplayElements element)
    {
        int value = HCDriverVitals.Raw(player, element);
        int seriousness = (value >> 3) & 7;
        return seriousness;
    }

    static bool HealthLow(PlayerBase player)
    {
        if (!player) { return false; }
        if (player.IsBleeding()) { return true; }
        if (HCDriverVitals.Tendency(player, eDisplayElements.DELM_TDCY_HEALTH) < 0) { return true; }
        return HCDriverVitals.Seriousness(player, eDisplayElements.DELM_TDCY_HEALTH) >= DSLevels.CRITICAL;
    }
}

class HCDriverCombat
{
    static const int C_ARM = 0;
    static const int C_RELOAD = 1;
    static const int C_HUNT = 2;
    static const int C_RETREAT = 3;
    static const int MAX_TARGETS = 3;
    static const int MAX_RELOADS = 3;
    static const int MAX_DONE = 32;
    static const float ENGAGE_CAP = 20.0;
    static const float LOS_SECONDS = 0.5;
    static const float LOST_SECONDS = 3.0;
    static const float AIMED_SECONDS = 0.5;
    static const float RETREAT_METERS = 40.0;

    protected float m_Range;
    protected float m_Timeout;
    protected float m_Elapsed;
    protected int m_Phase;
    protected float m_PhaseAge;
    protected Weapon_Base m_Weapon;
    protected Magazine m_MagBefore;
    protected bool m_Begun;
    protected EntityAI m_Target;
    protected float m_ScanAge;
    protected float m_LosAge;
    protected float m_Unseen;
    protected float m_EngageAge;
    protected float m_AimedAge;
    protected bool m_Counted;
    protected int m_Engaged;
    protected int m_Lost;
    protected int m_DeadSeen;
    protected int m_Reloads;
    protected int m_Seen;
    protected bool m_Retreated;
    protected bool m_Raised;
    protected float m_SignX = 1.0;
    protected float m_SignY = 1.0;
    protected float m_MarkX;
    protected float m_MarkY;
    protected float m_MarkAge;
    protected ref array<Object> m_Near = new array<Object>;
    protected ref array<CargoBase> m_NearCargo = new array<CargoBase>;
    protected ref set<Object> m_Hits = new set<Object>;
    protected ref array<EntityAI> m_Inventory = new array<EntityAI>;
    protected ref map<EntityAI, bool> m_Done = new map<EntityAI, bool>;
    protected string m_Detail;

    string Detail()
    {
        return m_Detail;
    }

    void Begin(HCDriverStep step)
    {
        m_Range = Math.Clamp(step.range_m, 10.0, 150.0);
        m_Timeout = Math.Max(step.timeout_s, 10.0);
        m_Elapsed = 0;
        m_Phase = HCDriverCombat.C_ARM;
        m_PhaseAge = 0;
        m_Weapon = null;
        m_MagBefore = null;
        m_Begun = false;
        m_Target = null;
        m_ScanAge = 1.0;
        m_LosAge = 0;
        m_Unseen = 0;
        m_EngageAge = 0;
        m_AimedAge = 0;
        m_Counted = false;
        m_Engaged = 0;
        m_Lost = 0;
        m_DeadSeen = 0;
        m_Reloads = 0;
        m_Seen = 0;
        m_Retreated = false;
        m_Raised = false;
        m_MarkAge = 0;
        m_Done.Clear();
        m_Detail = "";
    }

    // Lowers the weapon and gives the aim back to the player; safe at any time.
    void Release(PlayerBase player)
    {
        m_Raised = false;
        if (!player) { return; }
        HumanInputController input = player.GetInputController();
        if (!input) { return; }
        input.OverrideRaise(HumanInputControllerOverrideType.DISABLED, false);
        input.OverrideAimChangeX(HumanInputControllerOverrideType.DISABLED, 0);
        input.OverrideAimChangeY(HumanInputControllerOverrideType.DISABLED, 0);
    }

    protected string Tally()
    {
        int armed = 0;
        if (m_Weapon) { armed = 1; }
        int retreated = 0;
        if (m_Retreated) { retreated = 1; }
        return "engaged=" + m_Engaged.ToString() + " lost=" + m_Lost.ToString() + " dead_seen=" + m_DeadSeen.ToString() + " reloads=" + m_Reloads.ToString() + " armed=" + armed.ToString() + " retreated=" + retreated.ToString() + " fire=unsupported";
    }

    protected int End(PlayerBase player, HCDriverWalker walker, int code, string prefix)
    {
        Release(player);
        walker.Release(player);
        m_Detail = prefix + Tally();
        return code;
    }

    protected Weapon_Base FindWeapon(PlayerBase player)
    {
        Weapon_Base held = Weapon_Base.Cast(player.GetItemInHands());
        if (held) { return held; }
        m_Inventory.Clear();
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, m_Inventory);
        for (int index = 0; index < m_Inventory.Count(); index++)
        {
            Weapon_Base found = Weapon_Base.Cast(m_Inventory[index]);
            if (found && !found.IsPendingDeletion() && !found.IsRuined()) { return found; }
        }
        return null;
    }

    // Empty: no magazine with rounds and nothing in the chamber of the current muzzle.
    protected bool NeedsReload()
    {
        if (!m_Weapon) { return false; }
        int muzzle = m_Weapon.GetCurrentMuzzle();
        if (!m_Weapon.IsChamberEmpty(muzzle)) { return false; }
        Magazine mag = m_Weapon.GetMagazine(muzzle);
        if (!mag) { return true; }
        return mag.GetAmmoCount() <= 0;
    }

    protected bool Hostile(PlayerBase player, Object object)
    {
        if (!object || object == player || !object.IsAlive()) { return false; }
        if (DayZInfected.Cast(object)) { return true; }
        PlayerBase other = PlayerBase.Cast(object);
        if (!other) { return false; }
        if (other.GetIdentity()) { return false; }
        return true;
    }

    protected vector AimPoint(EntityAI target)
    {
        return target.GetPosition() + Vector(0, 1.3, 0);
    }

    // True when the first thing on the line from the head is the target (or nothing at all).
    protected bool InSight(PlayerBase player, EntityAI target)
    {
        vector begin = MiscGameplayFunctions.GetPlayerHeadPosition(player);
        vector end = AimPoint(target);
        vector contactPos;
        vector contactDir;
        int contactComponent;
        m_Hits.Clear();
        if (!DayZPhysics.RaycastRV(begin, end, contactPos, contactDir, contactComponent, m_Hits, null, player, true)) { return true; }
        for (int index = 0; index < m_Hits.Count(); index++)
        {
            if (m_Hits.Get(index) == target) { return true; }
        }
        return vector.Distance(contactPos, end) < 1.0;
    }

    // Nearest live hostile in range that this step has not finished with; null when none.
    protected EntityAI Scan(PlayerBase player)
    {
        m_Near.Clear();
        m_NearCargo.Clear();
        GetGame().GetObjectsAtPosition3D(player.GetPosition(), m_Range, m_Near, m_NearCargo);
        EntityAI best;
        float bestDistance = 1000000;
        int count = Math.Min(m_Near.Count(), 512);
        for (int index = 0; index < count; index++)
        {
            Object candidate = m_Near[index];
            if (!Hostile(player, candidate)) { continue; }
            EntityAI entity = EntityAI.Cast(candidate);
            if (!entity || m_Done.Contains(entity)) { continue; }
            float distance = vector.Distance(player.GetPosition(), entity.GetPosition());
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = entity;
            }
        }
        if (!best || !InSight(player, best)) { return null; }
        return best;
    }

    protected void Finished(EntityAI target)
    {
        if (m_Done.Count() >= HCDriverCombat.MAX_DONE) { m_Done.Clear(); }
        if (target) { m_Done.Set(target, true); }
        m_Target = null;
    }

    // Turns the view toward the target with the aim overrides; true when on target this frame.
    protected bool Aim(PlayerBase player, HumanInputController input, float dt)
    {
        vector from = GetGame().GetCurrentCameraPosition();
        vector look = GetGame().GetCurrentCameraDirection();
        vector want = AimPoint(m_Target) - from;
        float length = want.Length();
        if (length < 0.5) { return true; }
        float wantYaw = Math.Atan2(want[0], want[2]) * Math.RAD2DEG;
        float wantPitch = Math.Asin(Math.Clamp(want[1] / length, -1.0, 1.0)) * Math.RAD2DEG;
        float lookYaw = Math.Atan2(look[0], look[2]) * Math.RAD2DEG;
        float lookPitch = Math.Asin(Math.Clamp(look[1], -1.0, 1.0)) * Math.RAD2DEG;
        float errYaw = HCDriverWalker.Wrap180(wantYaw - lookYaw);
        float errPitch = wantPitch - lookPitch;
        // The override's sign convention is unobserved on retail: an error that does not shrink in a
        // second flips that axis, as the walker does for turning.
        m_MarkAge = m_MarkAge + dt;
        if (m_MarkAge >= 1.0)
        {
            if (Math.AbsFloat(errYaw) > 10.0 && Math.AbsFloat(errYaw) > m_MarkX - 2.0) { m_SignX = -m_SignX; }
            if (Math.AbsFloat(errPitch) > 10.0 && Math.AbsFloat(errPitch) > m_MarkY - 2.0) { m_SignY = -m_SignY; }
            m_MarkX = Math.AbsFloat(errYaw);
            m_MarkY = Math.AbsFloat(errPitch);
            m_MarkAge = 0;
        }
        float aimX = Math.Clamp(errYaw * 0.0026, -0.06, 0.06) * m_SignX;
        float aimY = Math.Clamp(errPitch * 0.0026, -0.04, 0.04) * m_SignY;
        input.OverrideAimChangeX(HumanInputControllerOverrideType.ENABLED, aimX);
        input.OverrideAimChangeY(HumanInputControllerOverrideType.ENABLED, aimY);
        return Math.AbsFloat(errYaw) < 3.0 && Math.AbsFloat(errPitch) < 4.0;
    }

    protected void BeginRetreat(PlayerBase player, HCDriverWalker walker)
    {
        Release(player);
        vector pos = player.GetPosition();
        vector away = player.GetDirection() * -1.0;
        if (m_Target)
        {
            away = pos - m_Target.GetPosition();
            away[1] = 0;
        }
        float length = away.Length();
        if (length < 0.1)
        {
            away = Vector(1, 0, 0);
            length = 1.0;
        }
        float tx = Math.Clamp(pos[0] + away[0] / length * HCDriverCombat.RETREAT_METERS, 5.0, 15355.0);
        float tz = Math.Clamp(pos[2] + away[2] / length * HCDriverCombat.RETREAT_METERS, 5.0, 15355.0);
        walker.Begin(tx, tz, "sprint", 3.0, 30.0);
        m_Retreated = true;
        m_Phase = HCDriverCombat.C_RETREAT;
        m_PhaseAge = 0;
    }

    protected void BeginReload(PlayerBase player)
    {
        m_MagBefore = m_Weapon.GetMagazine(m_Weapon.GetCurrentMuzzle());
        player.QuickReloadWeapon(m_Weapon);
        m_Phase = HCDriverCombat.C_RELOAD;
        m_PhaseAge = 0;
    }

    int Tick(PlayerBase player, float dt, HCDriverWalker walker)
    {
        if (!player || !player.IsAlive() || player.IsUnconscious()) { return End(player, walker, HCDriverResult.REFUSED, "player-unavailable "); }
        if (player.IsRestrained()) { return End(player, walker, HCDriverResult.REFUSED, "restrained "); }
        HumanInputController input = player.GetInputController();
        if (!input) { return End(player, walker, HCDriverResult.UNSUPPORTED, "no-input-controller "); }
        m_Elapsed = m_Elapsed + dt;
        m_PhaseAge = m_PhaseAge + dt;
        if (m_Phase == HCDriverCombat.C_RETREAT)
        {
            int walked = walker.Update(player, dt);
            if (walked == HCDriverResult.RUNNING) { return walked; }
            return End(player, walker, HCDriverResult.OK, "retreat-" + walker.Detail() + " ");
        }
        if (m_Elapsed > m_Timeout)
        {
            if (m_Engaged > 0) { return End(player, walker, HCDriverResult.OK, ""); }
            if (m_Seen == 0) { return End(player, walker, HCDriverResult.REFUSED, "no-target-within-" + Math.Round(m_Range).ToString() + "m "); }
            return End(player, walker, HCDriverResult.TIMEOUT, "not-aimed ");
        }
        if (HCDriverVitals.HealthLow(player))
        {
            BeginRetreat(player, walker);
            return HCDriverResult.RUNNING;
        }
        if (m_Phase == HCDriverCombat.C_ARM)
        {
            if (!m_Begun)
            {
                m_Begun = true;
                m_Weapon = FindWeapon(player);
                if (m_Weapon && player.GetItemInHands() != m_Weapon) { player.PredictiveTakeEntityToHands(m_Weapon); }
            }
            if (m_Weapon && player.GetItemInHands() != m_Weapon)
            {
                if (m_PhaseAge < 8.0) { return HCDriverResult.RUNNING; }
                m_Weapon = null;  // could not take it to the hands: fight with what is held (fists)
            }
            // One reload up front when a magazine is carried (the vanilla reload key swaps it in).
            if (m_Weapon && player.GetMagazineToReload(m_Weapon))
            {
                BeginReload(player);
                return HCDriverResult.RUNNING;
            }
            m_Phase = HCDriverCombat.C_HUNT;
            m_PhaseAge = 0;
        }
        if (m_Phase == HCDriverCombat.C_RELOAD)
        {
            WeaponManager manager = player.GetWeaponManager();
            bool running = false;
            if (manager) { running = manager.IsRunning(); }
            if (running && m_PhaseAge < 10.0) { return HCDriverResult.RUNNING; }
            if (m_PhaseAge < 0.5) { return HCDriverResult.RUNNING; }
            if (m_Weapon && m_Weapon.GetMagazine(m_Weapon.GetCurrentMuzzle()) != m_MagBefore) { m_Reloads++; }
            m_Phase = HCDriverCombat.C_HUNT;
            m_PhaseAge = 0;
        }
        // C_HUNT
        if (!m_Target)
        {
            if (m_Raised)
            {
                Release(player);
            }
            if (m_Engaged >= HCDriverCombat.MAX_TARGETS) { return End(player, walker, HCDriverResult.OK, ""); }
            if (NeedsReload() && m_Reloads < HCDriverCombat.MAX_RELOADS && player.GetMagazineToReload(m_Weapon))
            {
                BeginReload(player);
                return HCDriverResult.RUNNING;
            }
            m_ScanAge = m_ScanAge + dt;
            if (m_ScanAge < 1.0) { return HCDriverResult.RUNNING; }
            m_ScanAge = 0;
            m_Target = Scan(player);
            if (!m_Target) { return HCDriverResult.RUNNING; }
            m_Seen++;
            m_EngageAge = 0;
            m_AimedAge = 0;
            m_Unseen = 0;
            m_LosAge = 0;
            m_Counted = false;
        }
        if (!m_Target.IsAlive())
        {
            m_DeadSeen++;
            Finished(m_Target);
            return HCDriverResult.RUNNING;
        }
        m_EngageAge = m_EngageAge + dt;
        m_LosAge = m_LosAge + dt;
        if (m_LosAge >= HCDriverCombat.LOS_SECONDS)
        {
            m_LosAge = 0;
            bool far = vector.Distance(player.GetPosition(), m_Target.GetPosition()) > m_Range * 1.2;
            if (far || !InSight(player, m_Target)) { m_Unseen = m_Unseen + HCDriverCombat.LOS_SECONDS; }
            else { m_Unseen = 0; }
        }
        if (m_Unseen >= HCDriverCombat.LOST_SECONDS)
        {
            m_Lost++;
            Finished(m_Target);
            return HCDriverResult.RUNNING;
        }
        if (m_EngageAge >= HCDriverCombat.ENGAGE_CAP)
        {
            Finished(m_Target);
            return HCDriverResult.RUNNING;
        }
        input.OverrideRaise(HumanInputControllerOverrideType.ENABLED, true);
        m_Raised = true;
        if (Aim(player, input, dt)) { m_AimedAge = m_AimedAge + dt; }
        else { m_AimedAge = 0; }
        if (!m_Counted && m_AimedAge >= HCDriverCombat.AIMED_SECONDS)
        {
            m_Counted = true;
            m_Engaged++;
        }
        return HCDriverResult.RUNNING;
    }
}
