// Dev-only test addon (never shipped). Second set of setup-only admin fixtures for the soak
// reach map: each creates a starting state with vanilla APIs or runs the real server entry point
// a player action would, logs fixture=1, and the real HC code then counts on its own. No counter
// is bumped, faked or credited here; no player is moved. Server side only, honours
// EnableSmokeFixtures (HCAdminFixtures.HCEnabled); one object set per fixture (a repeat call
// deletes only the objects this provider created, held weakly).
// Commands: fx_animal (OptionalPacks/animal_seen), fx_food (FoodCompat/food_compat_guard),
// fx_cooking (CookingCompat/cooking_dish_cooked), fx_kit_place and fx_kit_refuse
// (Fortify/fortify_placed and fortify_refused), fx_barricade (Fortify/barricade_breached),
// fx_melee (Melee/hit_processed, wall_veto, parity_probe, zombie-hit-bonuses), fx_shoot
// (InfectedMemory/heat_recorded via Weapon_Base.EEFired, AITactics/fire-events via a weapon hit
// on a tracked AI; one native Weapon.Fire discharge exactly as HCXWarningShot does).
// Native scripts-1.30.164289: 3_Game/Global/Game.c:594/611/612 ConfigGetChildName/
// ConfigGetChildrenCount/ConfigIsExisting, :703 CreateObjectEx, :705 ObjectDelete, :1437 IsKindOf;
// 3_Game/dayzplayer.c:1293 ProcessMeleeHitName (the engine melee hit entry the client melee logic
// reaches at DayZPlayerMeleeFightLogic_LightHeavy.c:687/716, here driven by the server);
// 4_World/Classes/UserActionsComponent/Actions/Continuous/DeployActions/ActionDeployBase.c:70
// OnFinishProgressServer (PlaceObjectActionData, no hologram on the base action), :206 basebuilding
// kits stay where they are and OnPlacementComplete builds them; BaseBuildingBase.c:1230 FullyBuild;
// 3_Game/Entities/Building.c:31/73 GetDoorCount/GetDoorSoundPos; Cooking.c:117 CookWithEquipment
// returns 1 for every pass over a non-ruined pot; FireplaceBase.c:1760 StartFire.
class HCTestReachMeleeHit
{
    PlayerBase m_Player;
    ItemBase m_Weapon;
    ZombieBase m_Target;
    string m_Zone;
    int m_Mode;

    void Run()
    {
        if (!m_Player || !m_Weapon || !m_Target || m_Player.IsPendingDeletion() || m_Target.IsPendingDeletion()) { return; }
        if (!m_Target.IsAlive()) { return; }
        vector hitPos = m_Target.GetPosition() + Vector(0, 1.5, 0);
        m_Player.ProcessMeleeHitName(m_Weapon, m_Mode, m_Target, m_Zone, hitPos);
    }
}

class HCTestReachFixtures : HCAdminFixtureProvider
{
    protected static ref HCTestReachFixtures s_Provider;
    protected static const int CONFIG_SCAN_LIMIT = 20000;
    protected static const int INVENTORY_SCAN_LIMIT = 256;
    protected Object m_Animal;
    protected Object m_Food;
    protected Object m_Fire;
    protected Object m_Kit;
    protected Object m_Barricade;
    protected Object m_Gun;
    protected ref array<Object> m_Zombies = new array<Object>;

    static void HCRegisterOnce()
    {
        if (s_Provider) { return; }
        HCTestReachFixtures provider = new HCTestReachFixtures;
        if (HCAdminFixtures.HCRegister(provider)) { s_Provider = provider; }
    }

    static bool HCOwns(string command)
    {
        if (command == "fx_animal" || command == "fx_food" || command == "fx_cooking") { return true; }
        if (command == "fx_kit_place" || command == "fx_kit_refuse") { return true; }
        return command == "fx_barricade" || command == "fx_melee" || command == "fx_shoot";
    }

    override bool HCFixture(string command, vector pos, out string reason)
    {
        if (!HCOwns(command)) { return false; }
        string created = "none";
        bool done = false;
        reason = "EnableSmokeFixtures-off";
        if (HCAdminFixtures.HCEnabled())
        {
            reason = "server-only";
            if (GetGame() && GetGame().IsServer())
            {
                reason = "position-invalid";
                if (HCDebugSnapshot.HCPositionValid(pos) && pos[1] == pos[1])
                {
                    if (command == "fx_animal") { done = HCAnimal(pos, reason, created); }
                    if (command == "fx_food") { done = HCFood(pos, reason, created); }
                    if (command == "fx_cooking") { done = HCCooking(pos, reason, created); }
                    if (command == "fx_kit_place") { done = HCKit(pos, true, reason, created); }
                    if (command == "fx_kit_refuse") { done = HCKit(pos, false, reason, created); }
                    if (command == "fx_barricade") { done = HCBarricade(pos, reason, created); }
                    if (command == "fx_melee") { done = HCMelee(pos, reason, created); }
                    if (command == "fx_shoot") { done = HCShoot(pos, reason, created); }
                }
            }
        }
        string result = "refused";
        if (done) { result = "ok"; }
        Print("[HC Fixture] cmd=" + command + " fixture=1 result=" + result + " reason=" + reason + " class=" + created);
        return done;
    }

    override void HCFixtureKit(array<string> lines)
    {
        array<string> commands = {"fx_animal", "fx_food", "fx_cooking", "fx_kit_place", "fx_kit_refuse", "fx_barricade", "fx_melee", "fx_shoot"};
        string value = "0";
        string why = "EnableSmokeFixtures-off";
        if (HCAdminFixtures.HCEnabled())
        {
            value = "1";
            why = "setup-only-test-addon";
        }
        foreach (string command : commands)
        {
            lines.Insert(command + " available=" + value + " reason=" + why + " fixture=1");
        }
    }

    // ---- shared helpers ---------------------------------------------------------------

    protected void HCDelete(Object item)
    {
        if (item && !item.IsPendingDeletion()) { GetGame().ObjectDelete(item); }
    }

    protected void HCClearZombies()
    {
        foreach (Object zombie : m_Zombies) { HCDelete(zombie); }
        m_Zombies.Clear();
    }

    // The admin stands at pos: the nearest player within 4 m is the actor.
    protected PlayerBase HCActor(vector pos)
    {
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        PlayerBase best;
        float bestSq = 16;
        int count = Math.Min(players.Count(), 64);
        for (int index = 0; index < count; index++)
        {
            PlayerBase candidate = PlayerBase.Cast(players[index]);
            if (!candidate || !candidate.IsAlive()) { continue; }
            float distanceSq = vector.DistanceSq(candidate.GetPosition(), pos);
            if (distanceSq < bestSq)
            {
                bestSq = distanceSq;
                best = candidate;
            }
        }
        return best;
    }

    // First CfgVehicles class whose name has the prefix (or contains the tag when prefix is empty)
    // and derives from the parent, skipping names with the excluded tag. Bounded config scan,
    // one admin command at a time.
    protected string HCFindClass(string prefix, string tag, string parent, string excluded)
    {
        int total = Math.Min(GetGame().ConfigGetChildrenCount("CfgVehicles"), CONFIG_SCAN_LIMIT);
        for (int index = 0; index < total; index++)
        {
            string name;
            if (!GetGame().ConfigGetChildName("CfgVehicles", index, name)) { continue; }
            if (prefix != "" && name.IndexOf(prefix) != 0) { continue; }
            if (tag != "" && name.IndexOf(tag) < 0) { continue; }
            if (excluded != "" && name.IndexOf(excluded) >= 0) { continue; }
            if (!GetGame().ConfigIsExisting("CfgVehicles " + name + " scope")) { continue; }
            if (GetGame().ConfigGetInt("CfgVehicles " + name + " scope") != 2) { continue; }
            if (parent != "" && !GetGame().IsKindOf(name, parent)) { continue; }
            return name;
        }
        return "";
    }

    protected bool HCSpot(vector origin, float minRadius, float maxRadius, out vector spot)
    {
        for (int attempt = 0; attempt < 12; attempt++)
        {
            int ring = attempt % 4;
            float radius = minRadius + (maxRadius - minRadius) * ring / 3.0;
            float angle = attempt * 2.399963;
            vector candidate = origin + Vector(Math.Cos(angle) * radius, 0, Math.Sin(angle) * radius);
            candidate[1] = GetGame().SurfaceY(candidate[0], candidate[2]);
            if (!HCDebugSnapshot.HCPositionValid(candidate)) { continue; }
            if (GetGame().SurfaceIsSea(candidate[0], candidate[2]) || GetGame().SurfaceIsPond(candidate[0], candidate[2])) { continue; }
            spot = candidate;
            return true;
        }
        return false;
    }

    // ---- fx_animal ----------------------------------------------------------------------
    // HCOptionalPackUse counts animal_seen on the server AnimalBase.EEInit of an Animal_Otter
    // (the animal pack's otter). One otter, AI started so the normal animal init runs.

    protected bool HCAnimal(vector pos, out string reason, out string created)
    {
        HCDelete(m_Animal);
        m_Animal = null;
        created = "Animal_Otter";
        reason = "animal-pack-absent";
        if (!GetGame().ConfigIsExisting("CfgVehicles Animal_Otter")) { return false; }
        vector spot;
        reason = "no-spot-8-15m";
        if (!HCSpot(pos, 8, 15, spot)) { return false; }
        m_Animal = GetGame().CreateObjectEx("Animal_Otter", spot, ECE_PLACE_ON_SURFACE | ECE_INITAI | ECE_NOPERSISTENCY_WORLD);
        reason = "animal-create-refused";
        if (!m_Animal) { return false; }
        reason = "animal-set;eeinit-counts-animal_seen";
        return true;
    }

    // ---- fx_food ------------------------------------------------------------------------
    // One food-pack Edible_Base item (type tag _DON) on the ground in play: ItemBase.InitTemperature
    // runs the HC guard and HCUseGuarded counts food_compat_guard (an item created with a player
    // present, after the first summary).

    protected bool HCFood(vector pos, out string reason, out string created)
    {
        HCDelete(m_Food);
        m_Food = null;
        reason = "food-pack-absent";
        if (!GetGame().ConfigIsExisting("CfgVehicles Foodbox_DON_Cans")) { return false; }
        string foodClass = HCFindClass("", "_DON", "Edible_Base", "");
        created = foodClass;
        reason = "no-pack-edible-class";
        if (foodClass == "") { return false; }
        vector spot;
        reason = "no-spot-3-8m";
        if (!HCSpot(pos, 3, 8, spot)) { return false; }
        m_Food = GetGame().CreateObjectEx(foodClass, spot, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD);
        reason = "food-create-refused";
        if (!m_Food) { return false; }
        reason = "food-set;init-temperature-guard-runs";
        return true;
    }

    // ---- fx_cooking ---------------------------------------------------------------------
    // A lit Fireplace with a Tripod and a Pot, and a finished pack dish in the pot cargo: the
    // fireplace cooking tick runs Cooking.CookWithEquipment and HC counts the dish.

    protected bool HCCooking(vector pos, out string reason, out string created)
    {
        HCDelete(m_Fire);
        m_Fire = null;
        reason = "cooking-pack-absent";
        if (!GetGame().ConfigIsExisting("CfgVehicles CookZ_EmptyCan")) { return false; }
        string dishClass = HCFindClass("CookZ_", "", "Edible_Base", "_Opened");
        created = dishClass;
        reason = "no-pack-dish-class";
        if (dishClass == "") { return false; }
        vector spot;
        reason = "no-spot-6-12m";
        if (!HCSpot(pos, 6, 12, spot)) { return false; }
        FireplaceBase fire = FireplaceBase.Cast(GetGame().CreateObjectEx("Fireplace", spot, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        m_Fire = fire;
        reason = "fireplace-create-refused";
        if (!fire) { return false; }
        ItemBase wood = ItemBase.Cast(fire.GetInventory().CreateAttachment("Firewood"));
        ItemBase sticks = ItemBase.Cast(fire.GetInventory().CreateAttachment("WoodenStick"));
        if (wood) { wood.SetQuantityMax(); }
        if (sticks) { sticks.SetQuantityMax(); }
        EntityAI tripod = fire.GetInventory().CreateAttachment("Tripod");
        EntityAI pot = fire.GetInventory().CreateAttachment("Pot");
        reason = "tripod-or-pot-attach-refused";
        ItemBase potItem = ItemBase.Cast(pot);
        if (!tripod || !potItem)
        {
            HCDelete(m_Fire);
            m_Fire = null;
            return false;
        }
        EntityAI dish = potItem.GetInventory().CreateEntityInCargo(dishClass);
        reason = "dish-cargo-refused";
        if (!dish)
        {
            HCDelete(m_Fire);
            m_Fire = null;
            return false;
        }
        fire.StartFire();
        reason = "fire-not-lit-wind-or-wet";
        if (!fire.IsBurning()) { return false; }
        reason = "cooking-set;fire-lit,pot-with-dish,cooking-tick-counts";
        return true;
    }

    // ---- fx_kit_place / fx_kit_refuse -----------------------------------------------------
    // A pack kit on the ground at the actor, then the real ActionDeployBase server finish runs
    // with a PlaceObjectActionData (the modded OnFinishProgressServer in HCNoConstruction is the
    // gate): a shelter-scale RaG kit (or the barricade kit) is placed (fortify_placed), a
    // non-shelter RaG kit is refused (fortify_refused, rag_scale_excluded).

    protected string HCKitClass(bool place)
    {
        if (place)
        {
            array<string> shelterKits = {"RaG_BB_Single_DoorKit", "RaG_BB_Window_SmallKit", "RaG_BB_Low_WallKit", "RaG_BB_WoodStorageKit", "RaG_BB_Floor_HatchKit"};
            foreach (string kitClass : shelterKits)
            {
                if (GetGame().ConfigIsExisting("CfgVehicles " + kitClass)) { return kitClass; }
            }
            if (GetGame().ConfigIsExisting("CfgVehicles BF_DoorBarricadeKit")) { return "BF_DoorBarricadeKit"; }
            return "";
        }
        int total = Math.Min(GetGame().ConfigGetChildrenCount("CfgVehicles"), CONFIG_SCAN_LIMIT);
        for (int index = 0; index < total; index++)
        {
            string name;
            if (!GetGame().ConfigGetChildName("CfgVehicles", index, name)) { continue; }
            if (name.IndexOf("RaG_BB_") != 0 || name.IndexOf("Kit") < 0) { continue; }
            if (!GetGame().ConfigIsExisting("CfgVehicles " + name + " scope")) { continue; }
            if (GetGame().ConfigGetInt("CfgVehicles " + name + " scope") != 2) { continue; }
            if (!GetGame().IsKindOf(name, "RaG_BB_BaseKit")) { continue; }
            if (name == "RaG_BB_Single_DoorKit" || name == "RaG_BB_Window_SmallKit" || name == "RaG_BB_Low_WallKit") { continue; }
            if (name == "RaG_BB_WoodStorageKit" || name == "RaG_BB_Floor_HatchKit") { continue; }
            return name;
        }
        return "";
    }

    protected bool HCKit(vector pos, bool place, out string reason, out string created)
    {
        HCDelete(m_Kit);
        m_Kit = null;
        reason = "fortify-pack-absent";
        if (!HCFortifyBridge.HCPackPresent()) { return false; }
        reason = "fortify-module-not-active";
        if (!HCFortifyBridge.HCActive()) { return false; }
        string kitClass = HCKitClass(place);
        created = kitClass;
        reason = "no-kit-class-for-this-pack";
        if (kitClass == "") { return false; }
        PlayerBase player = HCActor(pos);
        reason = "no-actor-within-4m";
        if (!player) { return false; }
        vector spot;
        reason = "no-spot-3-8m";
        if (!HCSpot(pos, 3, 8, spot)) { return false; }
        ItemBase kit = ItemBase.Cast(GetGame().CreateObjectEx(kitClass, spot, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        m_Kit = kit;
        reason = "kit-create-refused";
        if (!kit) { return false; }
        ActionDeployBase action = new ActionDeployBase;
        PlaceObjectActionData data = PlaceObjectActionData.Cast(action.CreateActionData());
        reason = "action-data-refused";
        if (!data)
        {
            HCDelete(m_Kit);
            m_Kit = null;
            return false;
        }
        data.m_Player = player;
        data.m_MainItem = kit;
        data.m_Position = spot;
        data.m_Orientation = player.GetOrientation();
        action.OnFinishProgressServer(data);
        reason = "kit-finish-ran;placed-or-refused-by-the-real-gate";
        return true;
    }

    // ---- fx_barricade -------------------------------------------------------------------
    // A built door barricade bound to the nearest building door, and infected standing at the
    // doorway: HCInfectedDoors.HCPressBarricade then runs the real HCFortifyBridge.HCBreach, which
    // counts barricade_breached when the last part falls (FortifyBreachSeconds is the soak setting).

    protected Building HCNearestDoorBuilding(vector pos, out vector doorPos)
    {
        array<Object> objects = new array<Object>;
        array<CargoBase> proxies = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(pos, 40, objects, proxies);
        int count = Math.Min(objects.Count(), 512);
        Building best;
        float bestSq = 1600;
        for (int index = 0; index < count; index++)
        {
            Building building = Building.Cast(objects[index]);
            if (!building || building.GetDoorCount() <= 0) { continue; }
            vector door = building.GetDoorSoundPos(0);
            float distanceSq = vector.DistanceSq(door, pos);
            if (distanceSq < 36 || distanceSq >= bestSq) { continue; }
            bestSq = distanceSq;
            best = building;
            doorPos = door;
        }
        return best;
    }

    protected bool HCBarricade(vector pos, out string reason, out string created)
    {
        HCDelete(m_Barricade);
        m_Barricade = null;
        HCClearZombies();
        created = "BF_DoorBarricade";
        reason = "barricade-pack-absent";
        if (!HCFortifyBridge.HCBarricadePackPresent()) { return false; }
        reason = "fortify-module-not-active";
        if (!HCFortifyBridge.HCActive()) { return false; }
        vector doorPos;
        reason = "no-building-door-6-40m";
        Building building = HCNearestDoorBuilding(pos, doorPos);
        if (!building) { return false; }
        vector at = doorPos;
        at[1] = GetGame().SurfaceY(at[0], at[2]);
        BaseBuildingBase barricade = BaseBuildingBase.Cast(GetGame().CreateObjectEx("BF_DoorBarricade", at, ECE_PLACE_ON_SURFACE | ECE_NOPERSISTENCY_WORLD));
        m_Barricade = barricade;
        reason = "barricade-create-refused";
        if (!barricade) { return false; }
        barricade.FullyBuild();
        vector outward = vector.Direction(building.GetPosition(), at);
        outward[1] = 0;
        outward.Normalize();
        for (int index = 0; index < 2; index++)
        {
            vector zombiePos = at + outward * (1.4 + index * 0.9);
            zombiePos[1] = GetGame().SurfaceY(zombiePos[0], zombiePos[2]);
            Object zombie = GetGame().CreateObjectEx("ZmbM_CitizenASkinny_Blue", zombiePos, ECE_PLACE_ON_SURFACE | ECE_INITAI | ECE_NOPERSISTENCY_WORLD);
            if (zombie) { m_Zombies.Insert(zombie); }
        }
        reason = "barricade-set;infected-at-door,real-breach-path-runs-with-a-player-nearby";
        return true;
    }

    // ---- fx_melee -----------------------------------------------------------------------
    // The melee weapon in the actor's inventory strikes infected through the engine entry the
    // client melee logic uses (DayZPlayer.ProcessMeleeHitName), so HC melee code runs on a real
    // PlayerBase attacker and a real ZombieBase victim: light head (head_light), heavy head
    // (head_execute or head_armored), heavy leg (cripple), arm (arm_weak), and one infected inside
    // the nearest building so the head-to-zone ray crosses a wall (wall_veto, parity_probe).

    protected ItemBase HCMeleeWeapon(PlayerBase player)
    {
        ItemBase held = player.GetItemInHands();
        if (held && held.IsMeleeWeapon()) { return held; }
        array<EntityAI> items = new array<EntityAI>;
        player.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items);
        int count = Math.Min(items.Count(), INVENTORY_SCAN_LIMIT);
        for (int index = 0; index < count; index++)
        {
            ItemBase item = ItemBase.Cast(items[index]);
            if (item && item.GetType() == "KitchenKnife") { return item; }
        }
        return null;
    }

    protected void HCQueueHit(PlayerBase player, ItemBase weapon, vector at, vector side, int slot, string zone, int mode)
    {
        vector point = at + side * (slot * 0.9);
        point[1] = GetGame().SurfaceY(point[0], point[2]);
        ZombieBase zombie = ZombieBase.Cast(GetGame().CreateObjectEx("ZmbM_CitizenASkinny_Blue", point, ECE_PLACE_ON_SURFACE | ECE_INITAI | ECE_NOPERSISTENCY_WORLD));
        if (!zombie) { return; }
        m_Zombies.Insert(zombie);
        HCTestReachMeleeHit hit = new HCTestReachMeleeHit;
        hit.m_Player = player;
        hit.m_Weapon = weapon;
        hit.m_Target = zombie;
        hit.m_Zone = zone;
        hit.m_Mode = mode;
        GetGame().GetCallQueue(CALL_CATEGORY_GAMEPLAY).CallLater(hit.Run, 1500 + slot * 1200, false);
    }

    protected bool HCMelee(vector pos, out string reason, out string created)
    {
        HCClearZombies();
        created = "ZmbM_CitizenASkinny_Blue";
        PlayerBase player = HCActor(pos);
        reason = "no-actor-within-4m";
        if (!player) { return false; }
        ItemBase weapon = HCMeleeWeapon(player);
        reason = "no-melee-weapon-in-inventory";
        if (!weapon) { return false; }
        vector forward = player.GetDirection();
        forward[1] = 0;
        forward.Normalize();
        vector side = Vector(forward[2], 0, -forward[0]);
        vector at = player.GetPosition() + forward * 2.0;
        HCQueueHit(player, weapon, at, side, 0, "Head", 0);
        HCQueueHit(player, weapon, at, side, 1, "Head", 1);
        HCQueueHit(player, weapon, at, side, 2, "LeftLeg", 1);
        HCQueueHit(player, weapon, at, side, 3, "LeftArm", 0);
        vector doorPos;
        Building building = HCNearestDoorBuilding(pos, doorPos);
        if (building)
        {
            vector inside = building.GetPosition();
            inside[1] = GetGame().SurfaceY(inside[0], inside[2]);
            HCQueueHit(player, weapon, inside, side, 0, "Head", 0);
        }
        reason = "melee-queued;hits-1.5s-apart-through-ProcessMeleeHitName";
        return true;
    }

    // Nearest AI (class chain eAIBase, tested by name so this addon does not depend on the
    // provider) within 80 m of the admin, else null.
    protected Object HCNearestAI(vector pos)
    {
        array<Object> found = new array<Object>;
        array<CargoBase> cargo = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(pos, 80, found, cargo);
        Object best;
        float bestSq = float.MAX;
        int count = Math.Min(found.Count(), 256);
        for (int index = 0; index < count; index++)
        {
            Object candidate = found[index];
            if (!candidate || !candidate.IsKindOf("eAIBase") || !candidate.IsAlive()) { continue; }
            float distanceSq = vector.DistanceSq(candidate.GetPosition(), pos);
            if (distanceSq < bestSq)
            {
                bestSq = distanceSq;
                best = candidate;
            }
        }
        return best;
    }

    // One chambered round from a world weapon, discharged by the native Weapon.Fire call (the
    // call HCXWarningShot already makes), aimed at the nearest AI chest or, with none near, a
    // spot 25 m ahead of the admin. Nothing is credited here: Weapon_Base.EEFired and the AI
    // hit handlers count on their own.
    protected bool HCShoot(vector pos, out string reason, out string created)
    {
        HCDelete(m_Gun);
        m_Gun = null;
        created = "Mp133Shotgun";
        reason = "weapon-class-missing";
        if (!GetGame().ConfigIsExisting("CfgVehicles " + created)) { return false; }
        PlayerBase player = HCActor(pos);
        reason = "no-actor-within-4m";
        if (!player) { return false; }
        vector forward = player.GetDirection();
        forward[1] = 0;
        forward.Normalize();
        vector origin = player.GetPosition() + forward * 2.0 + Vector(0, 1.5, 0);
        Weapon_Base gun = Weapon_Base.Cast(GetGame().CreateObjectEx(created, origin, ECE_PLACE_ON_SURFACE));
        reason = "weapon-create-failed";
        if (!gun) { return false; }
        m_Gun = gun;
        string ammo = gun.GetRandomChamberableAmmoTypeName(0);
        reason = "no-chamberable-ammo";
        if (ammo == "" || ammo.IndexOf("Bullet_") != 0) { return false; }
        reason = "chamber-push-refused";
        if (!gun.PushCartridgeToChamber(0, 0, ammo)) { return false; }
        vector target = pos + forward * 25.0;
        target[1] = GetGame().SurfaceY(target[0], target[2]) + 1.2;
        string aimed = "ground-ahead";
        Object ai = HCNearestAI(pos);
        if (ai)
        {
            target = ai.GetPosition() + Vector(0, 1.2, 0);
            aimed = "nearest-ai";
        }
        vector direction = vector.Direction(origin, target).Normalized();
        reason = "native-fire-refused";
        if (!gun.CanFire(0) || gun.IsChamberEmpty(0)) { return false; }
        if (!gun.Fire(0, origin, direction, direction * 400.0)) { return false; }
        reason = "native-fire-ok;aimed=" + aimed;
        return true;
    }
}

modded class HCAdminModule
{
    override void OnStart(HCSettings settings)
    {
        super.OnStart(settings);
        if (GetGame() && GetGame().IsServer()) { HCTestReachFixtures.HCRegisterOnce(); }
    }
}
