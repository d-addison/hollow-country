// s2-tactics: real-item throw, drop, smoke activation and thrown-noise helpers
// plus the bounded inventory scan the tactics service uses. Original code;
// Expansion is read, never copied. Nothing here creates an item: the thrown
// object is the one the AI already carries, so it is consumed, never spawned.
//
// Capability register (installed vanilla scripts-1.30.164289 unless marked
// Expansion; "verified" = the call and its parameters exist in the installed
// script source, NOT that the behaviour was observed in DayZ; behaviour stays
// runtime=PENDING until a server session is watched):
//  V  Server-capable throw: MiscGameplayFunctions.ThrowEntityFromInventory
//     (4_World/Static/MiscGameplayFunctions.c:1305): InventoryMode.SERVER,
//     InventoryLocation.SetGroundEx (3_Game/Systems/Inventory/InventoryLocation.c:123),
//     GameInventory.TakeToDst, then ItemBase.ThrowPhysically(null, force, false)
//     (3_Game/Entities/InventoryItem.c:26). Quaternion from Math3D.YawPitchRollMatrix
//     (1_Core/proto/EnMath3D.c:133) and Math3D.MatrixToQuat (:360), the same way
//     ThrowAllItemsInInventoryEx builds it (MiscGameplayFunctions.c:1257-1303).
//     The function returns void, so success is observed afterwards (the item no
//     longer has a hierarchy parent), never assumed.
//  U  Force units and the flight distance for a given force are unobserved.
//     Player throws use HumanInventory.ThrowEntity (3_Game/Systems/Inventory/
//     HumanInventory.c:164), which returns false when g_Game.IsServer() and
//     IsMultiplayer(), so it is NOT usable for server-side AI and is not called.
//  V  Drop fallback: Man.ServerDropEntity (3_Game/Entities/Man.c:147, DropEntityImpl
//     with InventoryMode.SERVER). Expansion has its own drop
//     (eAIBase.c:10264 eAI_DropItemImpl) but the vanilla call is enough and the
//     existing HCW38 smoke flow already uses it.
//  V  Smoke activation: HCSituationSignals.HCSmoke (Events/HCSituationSignals.c)
//     guards SmokeGrenadeBase, no parent, IsPinned and CompEM.CanWork, then calls
//     Unpin (4_World/Entities/Grenade_Base/SmokeGrenadeBase.c:158 -> Activate;
//     Grenade_Base.c:51 Unpin, :74 IsPinned). Unpinning a smoke grenade does not
//     mark Expansion aggression (Expansion ActionUnpin.c:5-8 only flags non-smoke).
//     The smoke makes its own native noise on work start (SmokeGrenadeBase.c:186
//     AddNoisePos with NoiseSmokeGrenade), so smoke also draws infected; the
//     decision to accept that is the operator's (SmokeDisabled opt-out).
//  V  M18SmokeGrenade_Red_Contaminated spawns a ContaminatedArea_Dynamic when it
//     stops, so the SmokeExclude config substring filters it out.
//  V  Thrown noise: NoiseSystem.AddNoisePos (3_Game/Noise.c:7) and
//     NoiseParams.LoadFromPath (:25) through GetGame().GetNoiseSystem()
//     (Global/Game.c:738), the pattern HCSearchNoise.EmitAt already uses (copied
//     from vanilla ActionOpenDoors.c:78-90). Items make no native impact noise
//     (no script emits one for a landing can), so we emit exactly one noise at
//     the landed item after the configured delay, never AddNoiseTarget
//     (Noise.c:10), which is a timed alert.
//  U  Whether the configured vanilla noise path wakes and draws infected in the
//     way a landing can should: config.bin was not inspected, reaction unobserved.
//  U  Lit flare lure: Roadflare lights through the energy manager (Roadflare.c
//     SwitchOn) but no script emits flare noise (m_NoisePar is declared only), so
//     a lit flare drawing infected is unverified; flare_lure_unverified refusal.
//  V  AI inventory traversal: HCXTradeInventoryScan (HCXAITradeAdapter.c) over
//     Inventory.c:138 GetCargo, :205 AttachmentCount, :220 GetAttachmentFromIndex,
//     Cargo.c:28/32, HumanInventory.c:16 GetEntityInHands.
class HCXTacticsScan : HCXTradeInventoryScan
{
    int Mode;
    string Exclude;
    string Types;
    bool AllowFull;

    // Mode 1: a pinned SmokeGrenadeBase whose type is not excluded.
    // Mode 2: a listed noisy item that is empty (or any listed item when allowed).
    protected bool HCMatches(EntityAI entity)
    {
        ItemBase candidate = ItemBase.Cast(entity);
        eAIBase actor = this.HCActor();
        if (!actor || !candidate || candidate.IsRuined() || candidate.GetHierarchyRootPlayer() != actor) { return false; }
        if (Mode == 1)
        {
            SmokeGrenadeBase smoke = SmokeGrenadeBase.Cast(entity);
            if (!smoke || !smoke.IsPinned()) { return false; }
            return HCXAITacticsPolicy.SmokeTypeOk(smoke.GetType(), Exclude);
        }
        return HCXAITacticsPolicy.NoisyItemOk(Types, candidate.GetType(), candidate.HasQuantity(), candidate.GetQuantity(), AllowFull);
    }

    override ItemBase HCStep(int limit)
    {
        eAIBase actor = this.HCActor();
        if (!actor || !HCXExpansionBridge.HCBaseIsAlive(actor)) { HCRetire(); return null; }
        if (Found && Found.GetHierarchyRootPlayer() == actor && !Found.IsRuined()) { return Found; }
        Found = null;
        if (Complete) { return null; }
        while (Frames.Count() > 0 && Visited < limit)
        {
            if (!HCServer.HCTickWork().HCTakeFor(HCUnitBudget.HC_WORK_TACTICS_SCAN, 1)) { return null; }
            HCXTradeInventoryFrame frame = Frames[Frames.Count() - 1];
            EntityAI entity = frame.NodeEntity;
            if (!entity) { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            if (!frame.Checked)
            {
                frame.Checked = true;
                Visited++;
                if (HCMatches(entity)) { Found = ItemBase.Cast(entity); return Found; }
                continue;
            }
            EntityAI child;
            if (frame.Attachment < entity.GetInventory().AttachmentCount())
            {
                child = entity.GetInventory().GetAttachmentFromIndex(frame.Attachment);
                frame.Attachment++;
            }
            else
            {
                CargoBase cargo = entity.GetInventory().GetCargo();
                if (cargo && frame.CargoIndex < cargo.GetItemCount())
                {
                    child = cargo.GetItem(frame.CargoIndex);
                    frame.CargoIndex++;
                }
                else { Frames.RemoveOrdered(Frames.Count() - 1); continue; }
            }
            if (child && Frames.Count() < limit)
            {
                HCXTradeInventoryFrame nextFrame = new HCXTradeInventoryFrame;
                nextFrame.NodeEntity = child;
                Frames.Insert(nextFrame);
            }
        }
        Complete = true;
        return null;
    }
}

class HCXAIThrowables
{
    // Hand release point geometry, not gameplay tunables: just in front of and
    // at chest height of the thrower so the item does not start inside the body.
    static const float HAND_FORWARD = 0.6;
    static const float HAND_HEIGHT = 1.4;

    // Throws the carried item toward target. "" on success of the call (the
    // landing is observed later), else a named refusal. The engine call returns
    // void, so only the preconditions can be checked here.
    static string Throw(eAIBase actor, ItemBase item, vector target, float force, int liftPct)
    {
        if (!actor || !item || !GetGame() || !GetGame().IsServer()) { return "throw_refused"; }
        if (item.GetHierarchyRootPlayer() != actor || item.IsRuined()) { return "throw_refused"; }
        vector origin = HCXExpansionBridge.HCBaseGetPosition(actor);
        vector flat = target - origin;
        flat[1] = 0;
        if (flat.Length() < 0.5) { return "throw_refused"; }
        vector heading = flat.Normalized();
        vector placed = origin + heading * HCXAIThrowables.HAND_FORWARD;
        placed[1] = origin[1] + HCXAIThrowables.HAND_HEIGHT;
        vector angles = heading.VectorToAngles();
        vector orientation = Vector(angles[0], 0, 0);
        vector matrix[3];
        float direction[4];
        Math3D.YawPitchRollMatrix(orientation, matrix);
        Math3D.MatrixToQuat(matrix, direction);
        vector impulse = heading * force;
        impulse[1] = force * liftPct / 100.0;
        MiscGameplayFunctions.ThrowEntityFromInventory(item, placed, direction, impulse, ThrowEntityFlags.NONE);
        return "";
    }

    // Named fallback when the throw preconditions fail: the real item is put on
    // the ground at the thrower's feet (Man.c:147), still consumed from inventory.
    static bool Drop(eAIBase actor, ItemBase item)
    {
        if (!actor || !item || !GetGame() || !GetGame().IsServer()) { return false; }
        if (item.GetHierarchyRootPlayer() != actor) { return false; }
        return HCXExpansionBridge.HCBaseServerDropEntity(actor, item);
    }

    static bool Held(ItemBase item)
    {
        if (!item) { return false; }
        return item.GetHierarchyParent() != null;
    }

    static bool Pinned(ItemBase item)
    {
        SmokeGrenadeBase smoke = SmokeGrenadeBase.Cast(item);
        if (!smoke) { return false; }
        return smoke.IsPinned();
    }

    static bool ActivateSmoke(ItemBase item)
    {
        return HCSituationSignals.HCSmoke(item);
    }

    // One bounded native noise at the landed item (never a timed target).
    static bool Noise(EntityAI source, string noisePath, int multPct)
    {
        if (!GetGame() || !GetGame().IsServer() || !source || noisePath == "") { return false; }
        NoiseSystem worldNoise = GetGame().GetNoiseSystem();
        if (!worldNoise) { return false; }
        NoiseParams noiseParams = new NoiseParams();
        noiseParams.LoadFromPath(noisePath);
        worldNoise.AddNoisePos(source, source.GetPosition(), noiseParams, multPct / 100.0);
        return true;
    }
}
