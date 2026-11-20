// #56 W1.3: local acceptance adapter, never production qualification.
// Additional wearable API evidence (installed scripts-1.30.164289):
// 3_Game/Entities/Object.c:467 GetType,517 IsAlive,981 IsDamageDestroyed;
// 3_Game/Entities/Man.c:63 IsUnconscious; 4_World/Entities/DayZPlayerImplement.c:468
// IsInVehicle; 4_World/Entities/ManBase/PlayerBase.c:6733 GetItemInHands;
// 3_Game/Entities/EntityAI.c:802 GetHierarchyRootPlayer (native use).
// API declarations and exact installed evidence are indexed in
// tests/unit/test_taped_light_v1_evidence.py. No client profile IO.
// Native 3_Game/Global/Game.c:1120 IsServer. Installed gear_tools.pbo
// CfgVehicles/Flashlight has no inventorySlot (parent Inventory_Base);
// Flashlight.c:1 is the hand torch, not a weapon/pistol light-slot item.
// Keep the audited UniversalLight/TLRLight pairs; no invented mount slot.
// 1_Core/proto/EnDebug.c:96 Print for startup admission.
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
        return !FileExist("$profile:HollowCountry/acceptance/taped_light.disable");
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

// Wave 16: honest owner status. The local-acceptance opt-in is on by default and
// the operator file taped_light.disable is the named opt-out, so the module
// publishes ready/admitted_unverified, or off/operator_disable_file. HC-7 has no
// recorded native or two-client verdict (Qualified stays false): runtime=PENDING.
class HCTapedLightStartup : HCModule
{
    protected bool m_Printed;
    protected ref HCOperationalStatus m_Status = new HCOperationalStatus;
    override string GetName() { return "TapedLight"; }
    override bool IsEnabled(HCSettings settings) { return settings != null; }
    override HCOperationalStatus HCGetOperationalStatus() { return m_Status; }
    override void OnStop()
    {
        m_Printed = false;
        m_Status.HCStop();
    }
    override void OnStart(HCSettings settings)
    {
        if (m_Printed) { return; }
        m_Printed = true;
        bool admitted = HCTapedLightAdmission.Admitted();
        if (admitted) { m_Status.HCPublish("ready", "admitted_unverified"); }
        else { m_Status.HCPublish("off", "operator_disable_file"); }
        Print(HCV2Admission.Line("TapedLight", admitted, "TAPED-LIGHT-V1", HCTapedLightAdmission.Qualified()));
        int weaponPairs = HCTapedLightCatalog.Rows().Count();
        HCReached.Mark("taped_light.catalog_read");
        Print("[HC Plan] HC-7 weapon_pairs=" + weaponPairs.ToString() + " client_accepted=0 state=" + HCV2Admission.OnOff(admitted) + " r12=pending_proxy_client runtime=PENDING");
    }
}

modded class HCModuleRegistry
{
    override void RegisterModules()
    {
        super.RegisterModules();
        Register(new HCTapedLightStartup);
    }
}

class HCTapedLightV1Qualification extends HCTapedLightQualification
{
    override bool Ready()
    {
        return HCTapedLightAdmission.Admitted();
    }

    // Exact native-slot wearable adapters, admitted unverified. Native geometry
    // and two-client verdicts stay pending; no transform/controller is introduced.
    static HCTapedLightHostRow HCWearableRow(string hostType, string lightType, bool crossSlot = false)
    {
        if (lightType != "UniversalLight") { return null; }
        HCTapedLightHostRow wearable = new HCTapedLightHostRow;
        wearable.HostClass = hostType;
        wearable.LightClass = lightType;
        wearable.SlotName = "helmetFlashlight";
        if (hostType == "Mich2001Helmet")
        {
            if (GetGame().IsServer() && !HCTapedWearableCatalog.Admitted()) { return null; }
            return wearable;
        }
        if (hostType != "TortillaBag") { return null; }
        wearable.PairId = "tortilla_universal_mount";
        if (crossSlot) { wearable.PairId = "tortilla_universal_cross"; }
        if (GetGame().IsServer() && !HCTapedPackMounts.PairQualified(wearable.PairId))
        {
            return null;
        }
        if (wearable.PairId == "tortilla_universal_cross") { wearable.SlotName = "Chemlight"; }
        return wearable;
    }

    // Exact evidence cohort only. Live config and native attachment checks can
    // narrow this set; they never enlarge it to a descendant or a candidate.
    static HCTapedLightHostRow Row(EntityAI host, ItemBase light)
    {
        if (!host || !light) { return null; }
        string hostType = host.GetType();
        string lightType = light.GetType();
        ref array<ref HCTapedLightHostRow> rows = HCTapedLightCatalog.Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (HCTapedLightCatalog.Matches(row, hostType, lightType, row.SlotName)) { return row; }
        }
        if (hostType == "Mich2001Helmet" || hostType == "TortillaBag")
        {
            // Mounted identity is fixed by the actual slot; an opted-out pair
            // cannot be relabelled as another admitted pair for remove/toggle.
            if (host.FindAttachmentBySlotName("helmetFlashlight") == light) { return HCWearableRow(hostType, lightType, false); }
            if (host.FindAttachmentBySlotName("Chemlight") == light) { return HCWearableRow(hostType, lightType, true); }
            HCTapedLightHostRow looseRow = HCWearableRow(hostType, lightType, false);
            if (looseRow || hostType != "TortillaBag") { return looseRow; }
            // Fallback is for a loose cargo light only. Native evidence:
            // Inventory.c:268 GetCurrentInventoryLocation; InventoryLocation.c:43 GetType.
            InventoryLocation looseLocation = new InventoryLocation;
            if (!light.GetInventory().GetCurrentInventoryLocation(looseLocation)) { return null; }
            if (looseLocation.GetType() != InventoryLocationType.CARGO) { return null; }
            return HCWearableRow(hostType, lightType, true);
        }
        return CrossRow(hostType, lightType);
    }

    // Clients display exact catalogue candidates, excluding any known opt-out.
    // Admission is server-owned and is never inferred from this display hint.
    // Resolve still requires server readiness and validates the live slot arrays.
    static HCTapedLightHostRow CrossRow(string hostType, string lightType)
    {
        HCTapedLightHostRow row = HCTapedLightCatalog.CrossRowMatch(hostType, lightType);
        if (!row) { return null; }
        if (!GetGame()) { return null; }
        if (GetGame().IsServer())
        {
            if (!HCTapedPackMounts.WeaponPairAdmitted(row.PairId)) { return null; }
        }
        if (!GetGame().IsServer() && HCTapedPackMounts.ReceiptDisabled(row.PairId)) { return null; }
        return row;
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
        string configRoot = "CfgWeapons";
        if (row.HostClass == "Mich2001Helmet" || row.HostClass == "TortillaBag") { configRoot = "CfgVehicles"; }
        GetGame().ConfigGetTextArray(configRoot + " " + row.HostClass + " attachments", hostSlots);
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
        // Authoring provenance is separate from missing native measurements.
        if (configRoot == "CfgVehicles")
        {
            binding.ManifestDigest = HCTapedWearableCatalog.MANIFEST;
            if (row.HostClass == "TortillaBag") { binding.ManifestDigest = HCTapedPackCatalog.MANIFEST; }
            binding.MeasurementDigest = "";
        }
        binding.HostConfigRoot = configRoot;
        binding.HostClass = row.HostClass;
        binding.LightClass = row.LightClass;
        binding.SlotName = row.SlotName;
        binding.PairId = row.PairId;
        binding.CrossSlot = row.PairId != "";
        if (row.PairId == "tortilla_universal_mount") { binding.CrossSlot = false; }
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
        // Native 3_Game/Systems/Inventory/Inventory.c:717/763/787:
        // release only reservations we acquired.
        // No inventory has moved and no tape has been debited at this point.
        // Failed cleanup still leaves the journal intent quarantined by Run.
        if (!Reserve(light, mHCDestination) || !Reserve(host, null))
        {
            Release();
            return false;
        }
        if (mounting)
        {
            if (!tape || tape.GetHierarchyRootPlayer() != actor || !Reserve(tape, null))
            {
                Release();
                return false;
            }
        }
        EntityAI battery = light.FindAttachmentBySlotName(mHCBinding.BatterySlotName);
        if (battery && !Reserve(battery, null))
        {
            Release();
            return false;
        }
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
    // Host types in the evidence catalog, built once. Used only to stop the
    // per-frame client scan early; the server still validates in full.
    protected static ref map<string, bool> s_HostTypes;
    // Client-only preview hint (~0.3 s). Never read by CanExecute or Execute.
    protected static ItemBase s_HintHost;
    protected static int s_HintTime;
    protected static bool s_HintMount;
    protected static bool s_HintRemove;
    static const int HINT_WINDOW_MS = 300;

    static bool KnownHost(ItemBase host)
    {
        if (!host) { return false; }
        if (host.GetType() == "Mich2001Helmet" || host.GetType() == "TortillaBag") { return true; }
        if (!s_HostTypes)
        {
            s_HostTypes = new map<string, bool>;
            ref array<ref HCTapedLightHostRow> rows = HCTapedLightCatalog.Rows();
            foreach (HCTapedLightHostRow row : rows)
            {
                s_HostTypes.Set(row.HostClass, true);
            }
        }
        return s_HostTypes.Contains(host.GetType());
    }

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
            if (!candidate || candidate.IsDamageDestroyed()) { continue; }
            // Cheap energy filter first: a light always has a switchable
            // component, and most inventory items do not.
            ComponentEnergyManager energy = candidate.GetCompEM();
            if (!energy || energy.IsSwitchedOn()) { continue; }
            if (!HCTapedLightV1Qualification.Row(host, candidate)) { continue; }
            InventoryLocation location = new InventoryLocation;
            if (!candidate.GetInventory().GetCurrentInventoryLocation(location)) { continue; }
            if (location.GetType() != InventoryLocationType.CARGO || candidate.GetHierarchyRootPlayer() != actor) { continue; }
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
        string hostType = host.GetType();
        if (hostType == "Mich2001Helmet" || hostType == "TortillaBag")
        {
            ItemBase wearableLight = ItemBase.Cast(host.FindAttachmentBySlotName("helmetFlashlight"));
            if (!wearableLight && hostType == "TortillaBag") { wearableLight = ItemBase.Cast(host.FindAttachmentBySlotName("Chemlight")); }
            if (!wearableLight || !HCTapedLightV1Qualification.Row(host, wearableLight)) { return null; }
            return wearableLight;
        }
        ref array<ref HCTapedLightHostRow> rows = HCTapedLightCatalog.Rows();
        foreach (HCTapedLightHostRow row : rows)
        {
            if (row.HostClass != hostType) { continue; }
            ItemBase candidate = ItemBase.Cast(host.FindAttachmentBySlotName(row.SlotName));
            if (!candidate) { continue; }
            string candidateType = candidate.GetType();
            if (HCTapedLightCatalog.Matches(row, hostType, candidateType, row.SlotName)) { return candidate; }
            // Wave 16: an admitted weapon cross-slot light mounted in the same slot.
            if (HCTapedLightV1Qualification.CrossRow(hostType, candidateType)) { return candidate; }
        }
        return null;
    }

    // Native evidence: 3_Game/Entities/EntityAI.c:1897 FindAttachmentBySlotName,
    // :3409 GetCompEM; 3_Game/tools/Component/ComponentEnergyManager.c:
    // 371 SwitchOn,402 SwitchOff,752 CanSwitchOn,768 CanWork,884 IsSwitchedOn.
    // The native UniversalLight owns its battery, beam and replication.
    static ItemBase HCToggleCandidate(PlayerBase actor, ItemBase host)
    {
        if (!actor || !host || !actor.IsAlive() || actor.IsUnconscious() || actor.IsInVehicle()) { return null; }
        if (host.GetHierarchyRootPlayer() != actor || host.IsDamageDestroyed()) { return null; }
        if (host.GetType() != "Mich2001Helmet" && host.GetType() != "TortillaBag") { return null; }
        bool accessible = actor.GetItemInHands() == host;
        if (actor.FindAttachmentBySlotName("Back") == host || actor.FindAttachmentBySlotName("Headgear") == host) { accessible = true; }
        if (!accessible) { return null; }
        ItemBase mounted = MountedLight(host);
        if (!mounted || mounted.IsDamageDestroyed() || !mounted.GetCompEM()) { return null; }
        return mounted;
    }

    static bool HCToggle(PlayerBase actor, ItemBase host)
    {
        if (!GetGame() || !GetGame().IsServer() || !HCTapedLightAdmission.Admitted()) { return false; }
        ItemBase mounted = HCToggleCandidate(actor, host);
        if (!mounted) { return false; }
        ComponentEnergyManager energy = mounted.GetCompEM();
        if (energy.IsSwitchedOn())
        {
            energy.SwitchOff();
            return true;
        }
        if (!energy.CanSwitchOn() || !energy.CanWork()) { return false; }
        energy.SwitchOn();
        return true;
    }

    static bool Preview(PlayerBase actor, ItemBase host, bool mounting)
    {
        if (!Held(actor, host)) { return false; }
        // Not in the evidence catalog (any other weapon mod): no row can
        // match, so no scan can succeed. Same answer as before, without the cost.
        if (!KnownHost(host)) { return false; }
        ItemBase mounted = MountedLight(host);
        if (mounting) { return !mounted && Tape(actor) != null && LooseLight(actor, host) != null; }
        if (!mounted || !mounted.GetCompEM() || mounted.GetCompEM().IsSwitchedOn()) { return false; }
        InventoryLocation destination = new InventoryLocation;
        return actor.GetInventory().FindFreeLocationFor(mounted, FindInventoryLocationType.CARGO, destination);
    }

    // Client hint for the per-frame ActionCondition. Both actions share one
    // preview pass per window, keyed by the held host. Display only: the server
    // path calls CanExecute and Execute, which never read this cache.
    static bool PreviewHint(PlayerBase actor, ItemBase host, bool mounting)
    {
        if (!Held(actor, host)) { return false; }
        int now = GetGame().GetTime();
        bool fresh = s_HintHost == host && now >= s_HintTime && now - s_HintTime < HINT_WINDOW_MS;
        if (!fresh)
        {
            s_HintMount = Preview(actor, host, true);
            s_HintRemove = Preview(actor, host, false);
            s_HintHost = host;
            s_HintTime = now;
        }
        if (mounting) { return s_HintMount; }
        return s_HintRemove;
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
        HCTapedLightPermit.End();
        s_Busy = false;
        Print("[HollowCountry] Taped light result=" + result.ToString() + " runtime acceptance PENDING");
        return result;
    }

    // EEItemDetached is physical evidence, including native inventory moves.
    // No tape refund and no move/recreation: record the ended custody only.
    static void Detached(EntityAI host, EntityAI light, string slotName)
    {
        if (!GetGame() || !GetGame().IsServer() || !host || !light || s_Busy || s_Stopped) { return; }
        if (light.GetType() != "TLRLight" && light.GetType() != "UniversalLight") { return; }
        if (slotName != "weaponFlashlight" && slotName != "pistolFlashlight" && slotName != "helmetFlashlight" && slotName != "Chemlight") { return; }
        if (!FileExist("$profile:HollowCountry/TapedLights/v1/build.txt")) { return; }
        s_Busy = true;
        if (!RecordDetach(host, light, slotName)) { s_Stopped = true; }
        s_Busy = false;
    }
    protected static bool RecordDetach(EntityAI host, EntityAI light, string slotName)
    {
        HCTapedLightJournal journal = new HCTapedLightJournal;
        if (!journal.Configure("v1")) { return false; }
        HCTapedLightState state = new HCTapedLightState;
        if (!journal.Load(state) || state.Quarantined) { return false; }
        HCTapedLightPort keys = new HCTapedLightPort;
        string lightKey = keys.PersistentKey(light);
        string hostKey = keys.PersistentKey(host);
        HCTapedLightRecord latest;
        foreach (HCTapedLightRecord old : state.Records)
        {
            if (old.Phase != HCTapedLightPhase.MOUNTED && old.Phase != HCTapedLightPhase.REMOVED) { return false; }
            if (old.LightId == lightKey) { latest = old; }
        }
        if (!latest || latest.Phase != HCTapedLightPhase.MOUNTED) { return true; }
        if (latest.HostId != hostKey || latest.BindingData.SlotName != slotName) { return true; }
        HCTapedLightService.Compact(state);
        if (!HCTapedLightService.HasCapacity(state, false)) { return false; }
        HCTapedLightRecord receipt = new HCTapedLightRecord;
        receipt.RecordKey = journal.NextKey();
        receipt.ActorId = latest.ActorId;
        receipt.HostId = latest.HostId;
        receipt.LightId = latest.LightId;
        receipt.Mounting = false;
        receipt.Phase = HCTapedLightPhase.REMOVED;
        receipt.BindingData = HCTapedLightService.CopyBinding(latest.BindingData);
        // A historical custody receipt, not a claim about current health or
        // actor ownership. Preserve the prior snapshot and adjust only place.
        HCTapedLightSnapshot before = new HCTapedLightSnapshot;
        before.ActorId = latest.BeforeData.ActorId;
        before.HostId = latest.BeforeData.HostId;
        before.LightId = latest.BeforeData.LightId;
        before.BatteryId = latest.BeforeData.BatteryId;
        before.HostHealth = latest.BeforeData.HostHealth;
        before.LightHealth = latest.BeforeData.LightHealth;
        before.BatteryHealth = latest.BeforeData.BatteryHealth;
        before.BatteryEnergy = latest.BeforeData.BatteryEnergy;
        before.LightEnergy = latest.BeforeData.LightEnergy;
        before.Place = 1;
        receipt.BeforeData = before;
        state.Records.Insert(receipt);
        if (!HCTapedLightService.StateValid(state)) { return false; }
        return journal.Checkpoint();
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
        if (!HCTapedLightPermit.Begin(host, light, binding)) { return HCTapedLightCode.BLOCKED; }
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
        // caches from overwriting history. Sequence keys survive compaction.
        string key = port.NextKey();
        int result = HCTapedLightService.Run(state, port, key, mounting);
        if (result == HCTapedLightCode.QUARANTINED) { s_Stopped = true; }
        return result;
    }
}
