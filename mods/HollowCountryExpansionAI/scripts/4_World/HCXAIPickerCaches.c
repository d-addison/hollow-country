// HC-34 round 4: spec/plan/task — extend HC-18's cache step and cache journal,
// one endpoint per shared-budget visit; never a second spawner/scheduler.
// Native scripts-1.30.164289: 3_Game/gameplay.c:636 GetGame;
// 3_Game/Global/Game.c:1120 IsServer, :930 GetObjectsAtPosition3D,
// :703 CreateObjectEx; 3_Game/Entities/Object.c:287 GetPosition, :467 GetType;
// 3_Game/Entities/Man.c:21 GetIdentity; EntityAI.c:1884 GetInventory,
// :3374 GetPersistentID (through HCSearchSupplyRegistry.PersistentId);
// 3_Game/Systems/Inventory/Inventory.c:138 GetCargo, :143 CreateEntityInCargo;
// Cargo.c:28 GetItemCount; 1_Core/proto/EnConvert.c:210 DistanceSq;
// EnScript.c:380 Count, :407 Insert; EnDebug.c:96 Print.
// UTC epoch via HCXExpansionBridge.HCGetTimestamp (negative on refusal).
// Runtime acceptance PENDING: one server and at most one client.
modded class HCPickerSurvey
{
    string CacheClass;
    int CacheCooldownSeconds;
    int CacheMaxItems;
    int CacheMaxLootRows;
    ref array<ref HCXAISiteLoot> CacheLoot;

    // #205: a zero-filled or malformed cache section names its refusal.
    string HCPickerCacheRefusal()
    {
        if (CacheClass != "WoodenCrate") { return "PICKER_CACHE_CLASS_INVALID"; }
        if (CacheCooldownSeconds <= 0 || CacheMaxItems <= 0 || CacheMaxItems > MaxCargoScan) { return "PICKER_CACHE_LIMITS_INVALID"; }
        if (CacheMaxLootRows <= 0 || CacheMaxLootRows > CacheMaxItems) { return "PICKER_CACHE_LIMITS_INVALID"; }
        if (!CacheLoot || CacheLoot.Count() < 1 || CacheLoot.Count() > CacheMaxLootRows) { return "PICKER_CACHE_LOOT_INVALID"; }
        int total = 0;
        for (int lootIndex = 0; lootIndex < CacheLoot.Count(); lootIndex++)
        {
            HCXAISiteLoot loot = CacheLoot[lootIndex];
            if (!loot || loot.ClassName == "" || loot.Quantity < 1 || loot.Quantity > CacheMaxItems) { return "PICKER_CACHE_LOOT_INVALID"; }
            total = total + loot.Quantity;
            if (total > CacheMaxItems) { return "PICKER_CACHE_LOOT_INVALID"; }
        }
        return "";
    }

    bool HCPickerCacheValid()
    {
        return HCPickerCacheRefusal() == "";
    }
}

// #205: readiness names an invalid cache section instead of reporting ready.
modded class HCPickers
{
    override void HCPublishReadiness()
    {
        super.HCPublishReadiness();
        if (m_Status.HCState() != "ready" || !m_Survey) { return; }
        string reason = m_Survey.HCPickerCacheRefusal();
        if (reason != "") { m_Status.HCPublish("degraded", reason); }
    }
}

modded class HCXAICacheRow
{
    // Stable crate identity in the existing caches.json, separate endpoint keys.
    // Empty on interrupted initial creation: positional adoption, never loot replay.
    string HCPickerCrateId;
}

modded class HCXAISiteDirector
{
    protected int m_HCPickerCacheCursor;
    protected bool m_HCPickerCacheScanBlocked;
    protected string m_HCPickerCacheRefusal;

    // One log line per distinct refusal, never one per step.
    void HCPickerCacheRefused(string reason)
    {
        if (m_HCPickerCacheRefusal == reason) { return; }
        m_HCPickerCacheRefusal = reason;
        Print("[HC Pickers] caches refused reason=" + reason + " runtime=PENDING");
    }

    override void StepCache()
    {
        super.StepCache();
        if (!GetGame() || !GetGame().IsServer() || !m_Caches || !m_Policy || !HCPickers.Get()) { return; }
        HCScavengeTrip trip = HCPickers.Get().HCTrip();
        if (!trip || !trip.m_IO || !trip.m_IO.Survey || !trip.m_Ready) { return; }
        HCPickerSurvey survey = trip.m_IO.Survey;
        string refusal = survey.HCPickerCacheRefusal();
        if (refusal != "")
        {
            this.HCPickerCacheRefused(refusal);
            return;
        }
        if (!survey.Routes || survey.Routes.Count() == 0) { return; }
        int now = HCXExpansionBridge.HCGetTimestamp();
        if (now < 0) { return; }
        if (!HCServer.HCTickWork().HCTakeAISlice(HCUnitBudget.HC_AI_PICKER_CACHE, HCUnitBudget.HC_WORK_AI_SITES, 1)) { return; }
        int endpoints = survey.Routes.Count() * 2;
        if (m_HCPickerCacheCursor >= endpoints) { m_HCPickerCacheCursor = 0; }
        HCPickerRoute route = survey.Routes[m_HCPickerCacheCursor / 2];
        bool source = (m_HCPickerCacheCursor % 2) == 1;
        m_HCPickerCacheCursor++;
        this.HCPickerCacheStep(survey, route, source, now);
    }

    EntityAI HCPickerFindCache(HCPickerSurvey survey, vector at, HCXAICacheRow row)
    {
        m_HCPickerCacheScanBlocked = false;
        array<Object> objects = new array<Object>();
        array<CargoBase> cargos = new array<CargoBase>();
        GetGame().GetObjectsAtPosition3D(at, survey.ArrivalRangeMeters, objects, cargos);
        if (objects.Count() > survey.MaxScannedObjects || cargos.Count() > survey.MaxScannedObjects) { m_HCPickerCacheScanBlocked = true; return null; }
        for (int objectIndex = 0; objectIndex < objects.Count(); objectIndex++)
        {
            Object candidate = objects[objectIndex];
            if (!candidate || candidate.GetType() != survey.CacheClass) { continue; }
            EntityAI crate = EntityAI.Cast(candidate);
            string crateId = HCSearchSupplyRegistry.PersistentId(crate);
            if (crateId == "") { m_HCPickerCacheScanBlocked = true; return null; }
            if (!row || row.HCPickerCrateId == "" || row.HCPickerCrateId == crateId) { return crate; }
        }
        return null;
    }

    bool HCPickerCacheNear(HCPickerSurvey survey, HCPickerRoute route)
    {
        // Same HC-18 cached player list, identity filter and clear radius. Check
        // BOTH endpoints: neither initial creation nor refill may occur nearby.
        this.HCRefreshPlayers();
        for (int playerIndex = 0; playerIndex < m_Players.Count(); playerIndex++)
        {
            Man player = m_Players[playerIndex];
            if (!player || !player.GetIdentity()) { continue; }
            float radiusSq = m_Policy.CacheClearRadius * m_Policy.CacheClearRadius;
            if (vector.DistanceSq(player.GetPosition(), route.HCHomePoint()) < radiusSq) { return true; }
            if (vector.DistanceSq(player.GetPosition(), route.HCSourcePoint()) < radiusSq) { return true; }
        }
        return false;
    }

    bool HCPickerCustody(HCPickerRoute route)
    {
        if (!HCPickers.Get()) { return false; }
        HCScavengeTrip trip = HCPickers.Get().HCTrip();
        if (!trip || !trip.m_State || trip.m_State.RouteId != route.RouteId) { return false; }
        string phase = trip.m_State.Phase;
        // Lost/quarantined receipts remain conservative until resolved/rearmed.
        return phase != "idle" && phase != "returned";
    }

    void HCPickerCacheStep(HCPickerSurvey survey, HCPickerRoute route, bool source, int now)
    {
        string key = route.SiteId + ":picker-home";
        vector at = route.HCHomePoint();
        if (source) { key = route.SiteId + ":picker-source"; at = route.HCSourcePoint(); }
        HCXAICacheRow row = this.CacheRow(key);
        EntityAI crate = this.HCPickerFindCache(survey, at, row);
        if (m_HCPickerCacheScanBlocked) { return; }
        int items = 0;
        if (crate && crate.GetInventory() && crate.GetInventory().GetCargo()) { items = crate.GetInventory().GetCargo().GetItemCount(); }
        // Empty is the home's intended state; only a missing home is looted.
        if (!source && crate) { items = 1; }
        bool nearPlayer = this.HCPickerCacheNear(survey, route);
        if (this.HCPickerCustody(route)) { return; }
        bool present = false;
        if (crate) { present = true; }
        string action = HCXAISiteRules.CacheAction(row, present, items, now, nearPlayer);
        // A player may have restocked a previously looted source. Never add to it.
        if (action == "refill" && source && items > 0) { action = "adopt"; }
        if (action == "seed" || action == "refill")
        {
            this.HCPickerSeedCache(survey, key, at, source, row, crate, now);
            return;
        }
        if (action == "adopt")
        {
            row.State = "seeded";
            row.HCPickerCrateId = HCSearchSupplyRegistry.PersistentId(crate);
            this.SaveCaches();
            Print("[HC Pickers] cache key=" + key + " outcome=adopted runtime=PENDING");
        }
        if (action == "mark-looted")
        {
            row.State = "looted";
            row.LootedAt = now;
            row.NextRefillAt = HCXAISiteRules.RefillAt(now, survey.CacheCooldownSeconds);
            this.SaveCaches();
        }
    }

    void HCPickerSeedCache(HCPickerSurvey survey, string key, vector at, bool source, HCXAICacheRow row, EntityAI crate, int now)
    {
        // Refuse before touching the row while the barrier is busy: a "seeding" row that
        // was never persisted must not survive to be read back as looted.
        if (this.HCCacheSaveBusy(key)) { return; }
        bool wasAdded = false;
        if (!row)
        {
            if (m_Caches.Rows.Count() >= HCXAISiteRules.HCMaxCatalogRows()) { return; }
            HCXAICacheRow added = new HCXAICacheRow();
            added.SiteId = key;
            m_Caches.Rows.Insert(added);
            row = added;
            wasAdded = true;
        }
        HCXAICacheRowMemo memo = HCXAICacheRowMemo.Take(row);
        // An unjournaled existing crate is adopted without replaying stock.
        bool existing = false;
        if (crate) { existing = true; }
        row.State = "seeding";
        row.ClassName = survey.CacheClass;
        row.Lifecycle = row.Lifecycle + 1;
        row.SeededAt = now;
        row.LootedAt = 0;
        row.NextRefillAt = 0;
        row.HCPickerCrateId = "";
        if (!this.SaveCaches())
        {
            this.HCCacheSeedRevert(row, memo, wasAdded);
            Print("[HC Pickers] cache key=" + key + " outcome=seed_refused reason=cache_intent_unsaved runtime=PENDING");
            return;
        }
        if (!crate)
        {
            crate = EntityAI.Cast(GetGame().CreateObjectEx(survey.CacheClass, at, ECE_SETUP | ECE_CREATEPHYSICS | ECE_KEEPHEIGHT | ECE_NOLIFETIME));
            HCGroundSnap.Snap(crate);
            // Movable crates keep native item pathgraph behaviour; forcing a
            // static obstacle here would leave it behind after a player moves it.
        }
        if (!crate || !crate.GetInventory()) { return; }
        row.HCPickerCrateId = HCSearchSupplyRegistry.PersistentId(crate);
        if (row.HCPickerCrateId == "" || !this.SaveCaches()) { return; }
        int created = 0;
        // Existing empty source can refill only on the recorded cooldown path.
        if (source && (!existing || row.Lifecycle > 1))
        {
            for (int seedIndex = 0; seedIndex < survey.CacheLoot.Count(); seedIndex++)
            {
                HCXAISiteLoot loot = survey.CacheLoot[seedIndex];
                int made = 0;
                while (made < loot.Quantity && created < survey.CacheMaxItems)
                {
                    made++;
                    created++;
                    crate.GetInventory().CreateEntityInCargo(loot.ClassName);
                }
            }
        }
        row.State = "seeded";
        this.SaveCaches();
        string receipt = "[HC Pickers] cache key=" + key + " outcome=seeded lifecycle=" + row.Lifecycle.ToString();
        Print(receipt + " attempts=" + created.ToString() + " runtime=PENDING");
    }

}
