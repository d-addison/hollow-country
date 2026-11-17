// #56 W1.3: local acceptance adapter, never production qualification.
// API declarations and exact installed evidence are indexed in
// tests/unit/test_taped_light_v1_evidence.py. No client profile IO.
class HCTapedLightAdmission
{
    protected static bool s_Checked;
    protected static bool s_OptIn;

    static bool Qualified()
    {
        return false;
    }

    static bool LocalAcceptanceOptIn()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        return FileExist("$profile:HollowCountry/acceptance/taped_light.enable");
    }

    static bool Admitted()
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (Qualified()) { return true; }
        if (!s_Checked)
        {
            s_Checked = true;
            s_OptIn = LocalAcceptanceOptIn();
            if (s_OptIn)
            {
                Print("[HollowCountry] Taped light EXPERIMENTAL local acceptance opt-in active; runtime acceptance PENDING");
            }
            else
            {
                Print("[HollowCountry] Taped light not admitted; runtime acceptance PENDING");
            }
        }
        return s_OptIn;
    }
}

class HCTapedLightV1Qualification extends HCTapedLightQualification
{
    override bool Ready()
    {
        return HCTapedLightAdmission.Admitted();
    }

    // Exact evidence cohort only. Live config and native attachment checks can
    // narrow this set; they never enlarge it to a descendant or a candidate.
    static HCTapedLightHostRow Row(EntityAI host, ItemBase light)
    {
        if (!host || !light) { return null; }
        ref array<ref HCTapedLightHostRow> rows = HCTapedLightCatalog.Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (HCTapedLightCatalog.Matches(row, host.GetType(), light.GetType(), row.SlotName)) { return row; }
        }
        return null;
    }

    override HCTapedLightBinding Resolve(EntityAI host, ItemBase light)
    {
        if (!Ready()) { return null; }
        HCTapedLightHostRow row = Row(host, light);
        if (!row) { return null; }
        ref HCTapedLightJournal buildReader = new HCTapedLightJournal;
        string build = buildReader.Build();
        if (!HCBuildIdentity.Matches(build)) { return null; }
        TStringArray hostSlots = new TStringArray;
        TStringArray lightSlots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgWeapons " + row.HostClass + " attachments", hostSlots);
        GetGame().ConfigGetTextArray("CfgVehicles " + row.LightClass + " inventorySlot", lightSlots);
        if (hostSlots.Find(row.SlotName) < 0 || lightSlots.Find(row.SlotName) < 0) { return null; }
        if (row.PrerequisiteSlot != "")
        {
            EntityAI rail = host.FindAttachmentBySlotName(row.PrerequisiteSlot);
            if (!rail || rail.GetType() != row.PrerequisiteClass || rail.IsDamageDestroyed()) { return null; }
            if (!rail.ConfigIsExisting("hasRailFunctionality") || !rail.ConfigGetBool("hasRailFunctionality")) { return null; }
        }
        HCTapedLightBinding binding = new HCTapedLightBinding;
        binding.ManifestDigest = HCTapedLightCatalog.MANIFEST;
        binding.MeasurementDigest = HCTapedLightCatalog.OBSERVATIONS;
        binding.GameBuild = HCBuildIdentity.Canonical();
        binding.HostConfigRoot = "CfgWeapons";
        binding.HostClass = row.HostClass;
        binding.LightClass = row.LightClass;
        binding.SlotName = row.SlotName;
        binding.BatterySlotName = "BatteryD";
        binding.TapeUnits = 1;
        binding.MaxDistance = 2;
        binding.ReturnToCargo = true;
        return binding;
    }

    override bool HasLOS(PlayerBase actor, EntityAI host, HCTapedLightBinding binding)
    {
        if (!Ready() || !actor || !host || !binding) { return false; }
        // This action addresses only the actor's held weapon. There is no
        // world target behind a wall and no remote/ground inventory access.
        return actor.GetItemInHands() == host && host.GetHierarchyRootPlayer() == actor;
    }
}

class HCTapedLightV1Custody extends HCTapedLightCustody
{
    protected ref array<EntityAI> mHCReserved = new array<EntityAI>;
    protected ref InventoryLocation mHCDestination;
    protected ItemBase mHCLight;
    protected ref HCTapedLightBinding mHCBinding;

    void HCTapedLightV1Custody(HCTapedLightBinding binding)
    {
        mHCBinding = binding;
    }

    override bool Ready()
    {
        return HCTapedLightAdmission.Admitted() && mHCBinding != null;
    }

    override InventoryLocation Destination()
    {
        return mHCDestination;
    }

    protected bool Reserve(EntityAI candidate, InventoryLocation destination)
    {
        if (!GetGame() || !GetGame().IsServer()) { return false; }
        if (!candidate || mHCReserved.Find(candidate) >= 0) { return false; }
        if (GameInventory.HasInventoryReservation(candidate, null)) { return false; }
        if (destination && GameInventory.HasInventoryReservation(null, destination)) { return false; }
        if (!GameInventory.AddInventoryReservation(candidate, destination, GameInventory.c_InventoryReservationTimeoutMS)) { return false; }
        mHCReserved.Insert(candidate);
        return true;
    }

    override bool Acquire(PlayerBase actor, EntityAI host, ItemBase light, ItemBase tape, bool mounting)
    {
        if (!Ready() || !actor || !host || !light || mHCReserved.Count() != 0) { return false; }
        if (actor.GetItemInHands() != host || host.GetHierarchyRootPlayer() != actor) { return false; }
        if (light.GetHierarchyRootPlayer() != actor) { return false; }
        mHCLight = light;
        mHCDestination = new InventoryLocation;
        if (mounting)
        {
            mHCDestination.SetAttachment(host, light, InventorySlots.GetSlotIdFromString(mHCBinding.SlotName));
        }
        else
        {
            if (!actor.GetInventory().FindFreeLocationFor(light, FindInventoryLocationType.CARGO, mHCDestination)) { return false; }
        }
        // Reserve the actual destination plus every item whose state the
        // transaction preserves. Run is synchronous; it never yields custody
        // across callbacks. A failed acquisition is journaled nonterminal.
        if (!Reserve(light, mHCDestination) || !Reserve(host, null)) { return false; }
        if (mounting)
        {
            if (!tape || tape.GetHierarchyRootPlayer() != actor || !Reserve(tape, null)) { return false; }
        }
        EntityAI battery = light.FindAttachmentBySlotName(mHCBinding.BatterySlotName);
        if (battery && !Reserve(battery, null)) { return false; }
        return true;
    }

    override bool Release()
    {
        if (!GetGame().IsServer()) { return false; }
        bool released = true;
        foreach (EntityAI reserved : mHCReserved)
        {
            InventoryLocation destination = null;
            if (reserved == mHCLight) { destination = mHCDestination; }
            if (!GameInventory.ClearInventoryReservation(reserved, destination)) { released = false; }
            if (GameInventory.HasInventoryReservation(reserved, destination)) { released = false; }
        }
        if (released) { mHCReserved.Clear(); }
        return released;
    }
}

class HCTapedLightRuntime
{
    protected static bool s_Busy;
    protected static bool s_Stopped;

    static bool Held(PlayerBase actor, ItemBase host)
    {
        if (!actor || !host || !actor.IsAlive() || actor.IsUnconscious() || actor.IsInVehicle()) { return false; }
        return actor.GetItemInHands() == host && host.GetHierarchyRootPlayer() == actor && !host.IsDamageDestroyed();
    }

    // Fresh server selection at completion; clients can only preview candidates.
    // A loose light must be in cargo, never on another host or in another owner.
    static ItemBase LooseLight(PlayerBase actor, ItemBase host)
    {
        array<EntityAI> items = new array<EntityAI>;
        if (!actor.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items)) { return null; }
        if (items.Count() > 256) { return null; }
        foreach (EntityAI entry : items)
        {
            ItemBase candidate = ItemBase.Cast(entry);
            if (!candidate || candidate.IsDamageDestroyed() || !HCTapedLightV1Qualification.Row(host, candidate)) { continue; }
            InventoryLocation location = new InventoryLocation;
            if (!candidate.GetInventory().GetCurrentInventoryLocation(location)) { continue; }
            if (location.GetType() != InventoryLocationType.CARGO || candidate.GetHierarchyRootPlayer() != actor) { continue; }
            if (!candidate.GetCompEM() || candidate.GetCompEM().IsSwitchedOn()) { continue; }
            return candidate;
        }
        return null;
    }

    static ItemBase Tape(PlayerBase actor)
    {
        array<EntityAI> items = new array<EntityAI>;
        if (!actor.GetInventory().EnumerateInventory(InventoryTraversalType.PREORDER, items)) { return null; }
        if (items.Count() > 256) { return null; }
        foreach (EntityAI entry : items)
        {
            ItemBase candidate = ItemBase.Cast(entry);
            if (!candidate || candidate.GetType() != "DuctTape" || candidate.IsDamageDestroyed()) { continue; }
            if (candidate.GetHierarchyRootPlayer() != actor || candidate.GetQuantity() < 1) { continue; }
            return candidate;
        }
        return null;
    }

    static ItemBase MountedLight(ItemBase host)
    {
        ref array<ref HCTapedLightHostRow> rows = HCTapedLightCatalog.Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (row.HostClass != host.GetType()) { continue; }
            ItemBase candidate = ItemBase.Cast(host.FindAttachmentBySlotName(row.SlotName));
            if (candidate && HCTapedLightCatalog.Matches(row, host.GetType(), candidate.GetType(), row.SlotName)) { return candidate; }
        }
        return null;
    }

    static bool Preview(PlayerBase actor, ItemBase host, bool mounting)
    {
        if (!Held(actor, host)) { return false; }
        ItemBase mounted = MountedLight(host);
        if (mounting) { return !mounted && LooseLight(actor, host) && Tape(actor); }
        if (!mounted || !mounted.GetCompEM() || mounted.GetCompEM().IsSwitchedOn()) { return false; }
        InventoryLocation destination = new InventoryLocation;
        return actor.GetInventory().FindFreeLocationFor(mounted, FindInventoryLocationType.CARGO, destination);
    }

    static bool CanExecute(PlayerBase actor, ItemBase host, bool mounting)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCTapedLightAdmission.Admitted()) { return false; }
        return !s_Busy && !s_Stopped && Preview(actor, host, mounting);
    }

    static int Execute(PlayerBase actor, ItemBase host, bool mounting)
    {
        if (!CanExecute(actor, host, mounting)) { return HCTapedLightCode.DENIED; }
        s_Busy = true;
        int result = ExecuteOwned(actor, host, mounting);
        s_Busy = false;
        Print("[HollowCountry] Taped light result=" + result.ToString() + " runtime acceptance PENDING");
        return result;
    }

    protected static int ExecuteOwned(PlayerBase actor, ItemBase host, bool mounting)
    {
        ItemBase light = MountedLight(host);
        ItemBase tape = null;
        if (mounting)
        {
            light = LooseLight(actor, host);
            tape = Tape(actor);
        }
        ref HCTapedLightV1Qualification qualification = new HCTapedLightV1Qualification;
        HCTapedLightBinding binding = qualification.Resolve(host, light);
        if (!binding) { return HCTapedLightCode.BLOCKED; }
        ref HCTapedLightV1Custody custody = new HCTapedLightV1Custody(binding);
        ref HCTapedLightPort port = new HCTapedLightPort;
        if (!port.Configure(actor, host, light, tape, qualification, custody, "v1")) { return HCTapedLightCode.BLOCKED; }
        ref HCTapedLightState state = new HCTapedLightState;
        int opened = HCTapedLightService.Open(state, port);
        if (opened != HCTapedLightCode.OK)
        {
            s_Stopped = true;
            return opened;
        }
        // One server journal serializes all actors, preventing independent
        // caches from overwriting history. Never compact or fall back on faults.
        string key = "op_" + state.Records.Count().ToString();
        int result = HCTapedLightService.Run(state, port, key, mounting);
        if (result == HCTapedLightCode.QUARANTINED) { s_Stopped = true; }
        return result;
    }
}
