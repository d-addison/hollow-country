// Finite AI adjuncts share existing profile weights but need independent first-item
// fairness. Keep these nine subconsumers on the SAME core pool; no private pool,
// new module, settings or unbounded grants. Reset with the owning core tick.
// Worst case adds one forced item per active subconsumer, once per tick.
modded class HCUnitBudget
{
    static const int HC_AI_RING = 0;
    static const int HC_AI_PICKER_PARTY = 1;
    static const int HC_AI_PICKER_WALK = 2;
    static const int HC_AI_PICKER_CACHE = 3;
    static const int HC_AI_PICKER_BIND = 4;
    static const int HC_AI_CARAVAN = 5;
    static const int HC_AI_ANCHOR = 6;
    static const int HC_AI_THEFT = 7;
    static const int HC_AI_CUES = 8;
    protected bool m_HCAIServed[9];

    override void HCReset(int limit)
    {
        super.HCReset(limit);
        for (int index = 0; index < 9; index++) { m_HCAIServed[index] = false; }
    }

    bool HCTakeAISlice(int consumer, int profileSlot, int cost)
    {
        if (consumer < 0 || consumer >= 9 || profileSlot < 0 || profileSlot >= HC_WORK_CONSUMERS) { return false; }
        HCCloseSpan();
        int units = Math.Max(1, cost);
        if (m_Profile) { units = m_Profile.HCWeightedUnits(profileSlot, units); }
        bool admitted = HCTryTake(units);
        bool forced = false;
        if (!admitted)
        {
            if (m_HCAIServed[consumer])
            {
                if (m_Profile) { m_Profile.HCRefused(profileSlot); }
                return false;
            }
            forced = true;
            m_Starved++;
            m_Used += units;
            m_Items++;
        }
        m_HCAIServed[consumer] = true;
        if (m_Profile) { m_Profile.HCItem(profileSlot, units, forced); }
        return true;
    }
}

// Runtime cursor only; legacy camp journals remain unchanged. Native attribute:
// scripts-1.30.164289/3_Game/Client/SyncPlayer.c:7 NonSerialized.
modded class HCCampRecord
{
    [NonSerialized()]
    int HCTheftCrateCursor;
}

// LC-T415 / EXP-L9, EXP-L4. EnableCamps admits via HCCampModule.OnStart;
// verdict is diagnostic only. Native acceptance/compile remain PENDING.
// Installed scripts-1.30.164289 evidence:
// 3_Game/Global/Game.c:546 ConfigGetType, :558 ConfigGetTextArray,
// :612 ConfigIsExisting; Plugins/PluginBase/PluginConfigViewer.c:186 CT_ARRAY;
// 3_Game/Entities/Object.c:287 GetPosition, :467 GetType, :630/636
// IsWeapon/IsMeleeWeapon, :1219 IsRuined; EntityAI.c:882/885 hierarchy,
// :1884 GetInventory; Systems/Inventory/Inventory.c:138 GetCargo, :205
// AttachmentCount; Cargo.c:28/32 count/item; Inventory.c:276 FindFreeLocationFor,
// :1057 TakeToDst (InventoryMode.SERVER), via HCSearchSupplyRegistry.Transfer.
// 1_Core/proto/EnConvert.c:210 DistanceSq, :30 int.ToString; EnDebug.c:96 Print.
// Installed gear_camping.pbo config.bin CfgVehicles/WoodenCrate (RAP body
// 0x1f397): parent Container_Base, no declared attachments; camping.c:17
// WoodenCrate inherits DeployableContainer_Base. Effective config is checked
// again in-game. Any attachment or configured attachment slot is ineligible;
// no assumptions about locks supplied by other mods and no third-party assets.
class HCCampTheft
{
    static bool Due(int now, int last)
    {
        return now > 0 && (last == 0 || (now >= last && now - last >= 259200));
    }

    static bool Unlocked(ItemBase container)
    {
        if (!container || container.GetType() != "WoodenCrate" || !container.GetInventory()) return false;
        if (!GetGame().ConfigIsExisting("CfgVehicles WoodenCrate")) return false;
        if (GetGame().ConfigIsExisting("CfgVehicles WoodenCrate attachments") && GetGame().ConfigGetType("CfgVehicles WoodenCrate attachments") != CT_ARRAY) return false;
        TStringArray slots = new TStringArray;
        GetGame().ConfigGetTextArray("CfgVehicles WoodenCrate attachments", slots);
        // Vanilla has no lock slots. Any changed layout is unknown, including
        // an empty slot that might be controlled by an optional lock provider.
        return slots.Count() == 0 && container.GetInventory().AttachmentCount() == 0;
    }

    static bool Candidate(ItemBase container, HCCampRecord camp, int now, bool unattended, bool observerClear)
    {
        if (!container || !camp || !unattended || !observerClear || !Due(now, camp.LastTheft)) return false;
        if (!HCLockTable.CampUnlocked(container) || container.IsRuined()) { return false; }
        if (container.GetHierarchyParent() || container.GetHierarchyRootPlayer()) return false;
        vector containerPosition = container.GetPosition();
        return vector.DistanceSq(containerPosition, camp.Position) <= 144;
    }

    static bool SafeItem(EntityAI item)
    {
        return item && !item.IsRuined() && !item.IsWeapon() && !item.IsMeleeWeapon() && item.GetInventory() && !item.GetInventory().GetCargo() && !item.GetHierarchyRootPlayer();
    }

    // Existing, real persistent caches only. No cache/item creation or replay.
    static EntityAI Destination(vector position, out string cacheId)
    {
        cacheId = "";
        HCDeadDrops drops = HCDeadDrops.Get();
        if (drops)
        {
            for (int dropIndex = 0; dropIndex < drops.Count(); dropIndex++)
            {
                EntityAI dropCache = drops.Cache(dropIndex);
                if (!dropCache) continue;
                vector dropCachePosition = dropCache.GetPosition();
                if (vector.DistanceSq(dropCachePosition, position) <= 144) continue;
                if (!HCObserverTransitionGate.CanTransition(dropCachePosition, 500)) continue;
                if (!HCLockTable.CampUnlocked(ItemBase.Cast(dropCache))) { continue; }
                cacheId = drops.CacheId(dropIndex);
                return dropCache;
            }
        }
        HCHoldouts holdouts = HCHoldouts.Get();
        if (!holdouts) return null;
        for (int homeIndex = 0; homeIndex < holdouts.Count(); homeIndex++)
        {
            EntityAI homeCache = holdouts.Cache(homeIndex);
            if (!homeCache) continue;
            vector homeCachePosition = homeCache.GetPosition();
            if (vector.DistanceSq(homeCachePosition, position) <= 144) continue;
            if (!HCObserverTransitionGate.CanTransition(homeCachePosition, 500)) continue;
            if (!HCLockTable.CampUnlocked(ItemBase.Cast(homeCache))) { continue; }
            cacheId = holdouts.CacheId(homeIndex);
            return homeCache;
        }
        return null;
    }

    protected static string s_Refusal;
    protected static bool s_Admission;
    protected static bool s_Enabled;
    protected static ref HCTheftConfig s_Config;
    protected static ref HCEncounterStore<HCTheftConfig> s_ConfigStore;
    protected static ref HCOperationalStatus s_Status;

    // Native EnSystem.c:397 FileExist; Game.c:945 GetPlayers, :1120 IsServer;
    // Object.c:517 IsAlive; Man.c:21 GetIdentity. Other evidence above.
    // Profile opt-out sampled once, like other camp admission preferences.
    static bool HCEnabled()
    {
        if (s_Admission) { return s_Enabled && s_Config != null; }
        s_Admission = true;
        s_Status = new HCOperationalStatus;
        s_Enabled = !FileExist("$profile:HollowCountry/acceptance/camp_theft.disable");
        Print(HCV2Admission.Line("CampTheft", s_Enabled, "EXP-L9", false) + " runtime=PENDING");
        if (!s_Enabled) { s_Status.HCPublish("off", "operator_disabled"); return false; }
        s_ConfigStore = new HCEncounterStore<HCTheftConfig>("camp-theft-config");
        HCTheftConfig fresh = new HCTheftConfig;
        s_Config = s_ConfigStore.Load(fresh, "MaxAttemptsPerDay");
        string text = s_ConfigStore.HCTakeLoadedText();
        if (text != "" && (!HCJsonFields.Has(text, "AttendanceRangeMeters") || !HCJsonFields.Has(text, "ObserverRangeMeters") || !HCJsonFields.Has(text, "MaxAttendancePlayers"))) { s_Config = null; }
        if (!s_Config || !s_Config.HCValid())
        {
            s_Config = null;
            s_Status.HCPublish("refused", "THEFT_CONFIG_INVALID");
            HCRefuse("THEFT_CONFIG_INVALID");
            return false;
        }
        return true;
    }

    // Detached status derived from the real picker owner, never a fixed ready.
    // Lead may capture this non-module contributor from the shared status owner.
    static HCOperationalStatus HCGetOperationalStatus()
    {
        if (!s_Status) { s_Status = new HCOperationalStatus; }
        if (!s_Admission) { s_Status.HCPublish("off", "camp_theft_not_started"); return s_Status; }
        if (!s_Enabled || !s_Config) { return s_Status; }
        if (!HCCampModule.Get()) { s_Status.HCPublish("degraded", "THEFT_CAMP_OWNER_UNAVAILABLE"); return s_Status; }
        HCPickers pickers = HCPickers.Get();
        if (!pickers) { s_Status.HCPublish("degraded", "THEFT_PICKER_UNAVAILABLE"); return s_Status; }
        HCOperationalStatus observed = pickers.HCGetOperationalStatus();
        s_Status.HCPublish(observed.HCState(), observed.HCReason());
        if (observed.HCState() != "ready") { return s_Status; }
        HCScavengeTrip trip = pickers.HCTrip();
        if (!trip || !trip.m_IO || !trip.m_State || !trip.m_Ready) { s_Status.HCPublish("degraded", "THEFT_PICKER_TRIP_UNAVAILABLE"); return s_Status; }
        string walkRefusal = trip.m_IO.HCWalkRefusal();
        if (walkRefusal != "") { s_Status.HCPublish("degraded", walkRefusal); return s_Status; }
        // Capability is bound even when proximity admission has materialised no
        // party. Do not turn normal idle into a missing-provider diagnosis.
        if (trip.m_State.Phase == "idle") { s_Status.HCPublish("ready", "THEFT_WAITING_FOR_TRAVELLING_PARTY"); }
        return s_Status;
    }

    static void HCRefuse(string reason)
    {
        if (s_Refusal == reason) { return; }
        s_Refusal = reason;
        if (reason == "") { return; }
        Print("[HC CampTheft] reason=" + reason + " runtime=PENDING");
    }

    // Refresh group attendance now instead of trusting the camp's cached roster.
    // Observer gate adds its existing conservative all-player proximity veto.
    static bool HCAllowed(HCCampModule owner, HCCampRecord camp, ItemBase crate)
    {
        if (!HCEnabled() || !GetGame() || !GetGame().IsServer()) { return false; }
        if (!owner || HCCampModule.Get() != owner || !camp || !crate) { return false; }
        array<Man> people = new array<Man>();
        GetGame().GetPlayers(people);
        if (people.Count() > s_Config.MaxAttendancePlayers) { return false; }
        map<string, PlayerBase> attendancePlayers = HCGroupService.HCPlayersFromRoster(people);
        for (int personIndex = 0; personIndex < people.Count(); personIndex++)
        {
            PlayerBase player = PlayerBase.Cast(people[personIndex]);
            if (!player || !player.IsAlive() || !player.GetIdentity()) { continue; }
            if (owner.HCGroupIdWithPlayers(player, attendancePlayers) == camp.GroupId && vector.DistanceSq(player.GetPosition(), camp.Position) <= s_Config.AttendanceRangeMeters * s_Config.AttendanceRangeMeters) { return false; }
        }
        return HCObserverTransitionGate.CanTransition(crate.GetPosition(), s_Config.ObserverRangeMeters);
    }

    // Expansion's HCAccessible override calls this again after the native
    // transfer preflight's inventory callbacks (party identity stays separate).
    static bool HCGuard(HCScavengeInventory port, HCScavengeState row)
    {
        if (!port || !row) { return false; }
        if (!port.HCTheftCamp) { return true; }
        if (!HCEnabled()) { return false; }
        if (row.Phase == "leaving" || row.Phase == "acquiring")
        {
            return HCAllowed(port.HCTheftOwner, port.HCTheftCamp, ItemBase.Cast(port.Source));
        }
        if (!port.Home) { return false; }
        return HCObserverTransitionGate.CanTransition(port.Home.GetPosition(), s_Config.ObserverRangeMeters);
    }

    static void Step(HCCampModule module, HCCampRecord camp, HCCampScan scan, int now)
    {
        if (!HCEnabled() || !module || !camp || !scan || !Due(now, camp.LastTheft)) { return; }
        HCPickers pickers = HCPickers.Get();
        if (!pickers) { HCRefuse("THEFT_PICKER_UNAVAILABLE"); return; }
        HCScavengeTrip trip = pickers.HCTrip();
        if (!trip || !trip.m_IO || !trip.m_State || !trip.m_Ready) { HCRefuse("THEFT_PICKER_UNAVAILABLE"); return; }
        if (trip.m_State.Phase != "leaving" || trip.m_IO.HCTheftCamp) { HCRefuse("THEFT_NO_EMPTY_TRAVELLING_PARTY"); return; }
        // The camp scan bounds real crates; each candidate consumes shared work. A party
        // is never dispatched to camp coordinates or told that stock exists.
        if (scan.Crates.Count() < 1) { HCRefuse("THEFT_CAMP_CRATE_ABSENT"); return; }
        // #209: a refusal specific to one crate moves on to the next bounded
        // candidate; success and global faults still stop the scan at once.
        string lastRefusal = "THEFT_NO_PARTY_NEAR_CAMP";
        // Exactly one candidate per camp visit, with a retained cursor. A
        // spent pool cannot pin the scan on an ineligible first crate, or add
        // eight attendance/observer checks to one tick.
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_THEFT, HCUnitBudget.HC_WORK_BASES, 1)) { HCRefuse("THEFT_WORK_BUDGET"); return; }
        {
            if (camp.HCTheftCrateCursor >= scan.Crates.Count()) { camp.HCTheftCrateCursor = 0; }
            ItemBase crate = scan.Crates[camp.HCTheftCrateCursor];
            camp.HCTheftCrateCursor++;
            if (!trip.m_IO.HCTheftNear(crate)) { HCRefuse(lastRefusal); return; }
            bool clear = HCAllowed(module, camp, crate);
            if (!Candidate(crate, camp, now, clear, clear))
            {
                HCRefuse("THEFT_CAMP_INELIGIBLE");
                return;
            }
            string refusal = trip.HCTheftPickup(module, camp, crate, now, s_Config.MaxAttemptsPerDay);
            if (!HCCandidateRefusal(refusal))
            {
                HCRefuse(refusal);
                return;
            }
            lastRefusal = refusal;
        }
        HCRefuse(lastRefusal);
    }

    // Pickup refusals that depend only on the crate being examined.
    static bool HCCandidateRefusal(string reason)
    {
        if (reason == "THEFT_ATTENDED_OR_OBSERVED" || reason == "THEFT_SOURCE_IS_HOME") { return true; }
        return reason == "THEFT_SAFE_STOCK_ABSENT" || reason == "THEFT_PERSISTENT_ID_ABSENT";
    }
}

// Operator config generated by the verified shared JSON store, no mission file.
// One carried item per trip remains the existing custody ledger ceiling.
class HCTheftConfig
{
    int Version = 1;
    int MaxAttemptsPerDay = 1;
    int MaxAttendancePlayers = 32;
    float AttendanceRangeMeters = 500;
    float ObserverRangeMeters = 500;

    // Literal fallbacks mirror the shared registry rows (owner HCTheftConfig);
    // the registry check applies whenever the compiled mirror is present.
    bool HCValid()
    {
        HCTheftConfig config = this;
        if (config.Version != 1 || config.MaxAttemptsPerDay < 1 || config.MaxAttemptsPerDay > 6) { return false; }
        if (config.MaxAttendancePlayers < 1 || config.MaxAttendancePlayers > 32) { return false; }
        if (config.AttendanceRangeMeters != config.AttendanceRangeMeters || config.ObserverRangeMeters != config.ObserverRangeMeters) { return false; }
        if (config.AttendanceRangeMeters < 500 || config.AttendanceRangeMeters > 1000 || config.ObserverRangeMeters < 500 || config.ObserverRangeMeters > 1000) { return false; }
        if (!HCOperatorSettingsRegistry.HCFind("CampTheft.Version")) { return true; }
        if (!HCOperatorSettingsRegistry.HCValid("CampTheft.Version", config.Version) || !HCOperatorSettingsRegistry.HCValid("CampTheft.MaxAttemptsPerDay", config.MaxAttemptsPerDay)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("CampTheft.MaxAttendancePlayers", config.MaxAttendancePlayers)) { return false; }
        if (!HCOperatorSettingsRegistry.HCValid("CampTheft.AttendanceRangeMeters", config.AttendanceRangeMeters)) { return false; }
        return HCOperatorSettingsRegistry.HCValid("CampTheft.ObserverRangeMeters", config.ObserverRangeMeters);
    }
}
