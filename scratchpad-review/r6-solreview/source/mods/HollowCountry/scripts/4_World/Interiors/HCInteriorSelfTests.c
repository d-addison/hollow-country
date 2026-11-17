// Called on server start in DIAG_DEVELOPER; no world or inventory mutations.
class HCInteriorSelfTests
{
    static bool Run()
    {
        if (HCInteriorRules.Quantize(1.234) != 123 || HCInteriorRules.Quantize(-1.236) != -124) return false;
        if (HCInteriorRules.Yaw(-90) != 27000 || HCInteriorRules.Yaw(360) != 0) return false;
        if (!HCInteriorRules.Transition(0, 1) || !HCInteriorRules.Transition(1, 2)) return false;
        if (HCInteriorRules.Transition(2, 0) || HCInteriorRules.Transition(3, 1)) return false;
        if (HCInteriorRules.Recover(true, false, 1, 0) != 3) return false;
        if (HCInteriorRules.Recover(true, true, 1, 1) != 3) return false;
        if (HCInteriorRules.Recover(true, true, 1, 2) != 2) return false;
        if (HCInteriorRules.Recover(false, false, 0, 0) != 0) return false;
        if (HCInteriorRules.Allocation(0, 4, 0) != 0 || HCInteriorRules.Allocation(1, 0, 2) != 0) return false;
        if (HCInteriorRules.Allocation(2, 0, 0) != 0 || HCInteriorRules.Allocation(0, 0, 0) != 1) return false;
        if (!HCInteriorRules.PoolWithinBounds(12, 4, 2) || HCInteriorRules.PoolWithinBounds(12, 5, 2)) return false;
        if (!HCInteriorRules.MigrationAllowed(1, 2, true, true) || HCInteriorRules.MigrationAllowed(2, 1, true, true)) return false;
        if (HCInteriorRules.ReconcilePhase(3, 0) != 3 || HCInteriorRules.ReconcilePhase(1, 0) != 3) return false;
        if (HCInteriorRules.RecoverJournal(true, true, false, false, false, false, 2, 0) != 3) return false;
        if (HCInteriorRules.RecoverJournal(true, true, true, true, true, true, 2, 2) != 2) return false;
        if (HCInteriorRules.OrphanDecision(true, 1, 0, true) != 3) return false;
        if (HCInteriorRules.TransformKey("100.001 20 100", "0 0 0") != HCInteriorRules.TransformKey("100 20 100", "360 0 0")) return false;
        for (int x = -1000; x <= 1000; x += 10)
        {
            int choice = HCInteriorRules.Layout(x, 120, 800, 0, 17);
            if (choice < 0 || choice > 2 || !HCInteriorCatalog.Get(choice)) return false;
        }
        Print("[HC Interiors] scalar self-tests PASS (not runtime transaction/placement acceptance)");
        return true;
    }
    #ifdef DIAG_DEVELOPER
    // Explicit Workbench experiment: HCInteriorSelfTests.RunStorageProbe(900001).
    // A fresh reserved test epoch is required; preserves files for crash inspection.
    // Exercises real Enforce file/serializer/recovery code, never inventory grants.
    static bool RunStorageProbe(int epoch)
    {
        if (!GetGame().IsServer() || epoch < 900001 || epoch > 900999) return false;
        string root = "$profile:HollowCountry/interiors_s1_e" + epoch.ToString();
        if (FileExist(root)) return false;
        if (!FileExist("$profile:HollowCountry") && !MakeDirectory("$profile:HollowCountry")) return false;
        HCInteriorConfig config = new HCInteriorConfig;
        config.Epoch = epoch;
        config.InitializeNewEpoch = true;
        HCInteriorManifest manifest = new HCInteriorManifest;
        manifest.SchemaVersion = 1;
        manifest.Epoch = epoch;
        for (int slot = 0; slot < 3; slot++)
        {
            HCInteriorAssignment assignment = new HCInteriorAssignment;
            assignment.SlotId = slot;
            assignment.InstanceId = "SYNTHETIC_STORAGE_PROBE_" + slot.ToString();
            manifest.Assignments.Insert(assignment);
        }
        HCInteriorStore store = new HCInteriorStore;
        if (!store.Open(config, manifest)) return false;
        HCInteriorSite site = new HCInteriorSite;
        site.SlotId = 0;
        site.Id = "SYNTHETIC_STORAGE_PROBE_0_storage_v1";
        if (store.RecoverSite(site) != 0) return false;
        if (!store.Reserve(site, "SYNTHETIC_ACTOR")) return false;
        if (!store.BeginGrant(site, "SYNTHETIC_ACTOR")) return false;
        if (!store.Finish(site, "SYNTHETIC_ACTOR", 2)) return false;
        HCInteriorStore restarted = new HCInteriorStore;
        if (!restarted.Open(config, manifest) || restarted.RecoverSite(site) != 2) return false;
        site.Phase = 0;
        if (restarted.Reserve(site, "SYNTHETIC_RETRY")) return false;
        HCInteriorSite corrupt = new HCInteriorSite;
        corrupt.SlotId = 1;
        corrupt.Id = "SYNTHETIC_STORAGE_PROBE_1_storage_v1";
        FileHandle handle = OpenFile(root + "/claim_1.json", FileMode.WRITE);
        if (!handle) return false;
        FPrint(handle, "{");
        CloseFile(handle);
        if (restarted.RecoverSite(corrupt) != 3) return false;
        HCInteriorSite interrupted = new HCInteriorSite;
        interrupted.SlotId = 2;
        interrupted.Id = "SYNTHETIC_STORAGE_PROBE_2_storage_v1";
        if (!restarted.Reserve(interrupted, "SYNTHETIC_INTERRUPTED")) return false;
        HCInteriorStore third = new HCInteriorStore;
        if (!third.Open(config, manifest) || third.RecoverSite(interrupted) != 3) return false;
        HCInteriorSupplyCount count = third.Supply("");
        if (!count || count.Allocated != 3 || count.Spent != 1 || count.Quarantined != 2 || count.Available != 0) return false;
        Print("[HC Interiors] storage probe PASS; synthetic state only, no inventory atomicity proof");
        return true;
    }
    #endif
}
