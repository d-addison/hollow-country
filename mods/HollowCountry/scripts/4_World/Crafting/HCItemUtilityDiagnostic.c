// Native scripts-1.30.164289: 1_Core/proto/EnScript.c:902/917 map Set/Contains (hash lookup).
// N2/N3, explicit disposable-profile invocation ONLY. No constructor, module,
// mission, timer, RPC or startup hook. Caller pins the complete N1 queue, calls
// Begin, ObserveNext once per row and PollCleanup until confirmed, and enforces
// an EXTERNAL wall-clock deadline. A stalled VM cannot confirm cleanup.
// API anchors and config evidence: tests/fixtures/runtime/crafting-contract.json (T0 only).
// Complete here means supplied rows emitted + owned deletion confirmed, never
// gameplay acceptance, effective action execution or production qualification.
#ifdef DIAG_DEVELOPER
class HCItemUtilityRequest
{
    int Index;
    string ConfigRoot;
    string ItemClass;
    int KitIndex = -1; // -1 metadata only; 0..8 regular kits, 9..11 special routes
    bool CreationReviewed; // caller's pinned concrete-class review, not a cast
}

class HCItemUtilityState
{
    bool Present;
    bool Deleting;
    float Health;
    float Quantity;
    bool HasQuantity;
    float Wet;
    int Agents;
    int Attachments;
    int CargoItems;
    int Ammo = -1;
    float Energy = -1;
    ref array<string> Zones = new array<string>;
    ref array<float> ZoneHealth = new array<float>;
    bool ZonesComplete;
}

class HCItemUtilityObservation
{
    int SchemaVersion = 1;
    bool Captured;
    int Index;
    string ConfigRoot;
    string ItemClass;
    string Status;
    int Scope = -1;
    int ScopeType = -1;
    int RepairKitType = -1;
    int RepairKitFieldType = -1;
    int RepairableFieldType = -1;
    int CostsFieldType = -1;
    ref array<string> Ancestors = new array<string>;
    bool AncestryComplete;
    ref array<int> RepairableWithKits = new array<int>;
    ref array<float> RepairCosts = new array<float>;
    bool ArrayElementKindsVerified; // deliberately false: native container type only
    string ToolClass;
    string RecipeClass;
    int RecipeId = -1;
    bool Created;
    bool CastSucceeded;
    bool CanBeRepairedByCrafting;
    bool CanBeRepairedToPristine;
    bool CanRepairObserved; // false means unknown, including missing plugin
    bool CanRepair;
    bool Discovered;
    bool Attempted;
    bool SameTargetHandle;
    bool SameToolHandle;
    ref array<int> RecipeIds = new array<int>;
    ref array<string> ActionNames = new array<string>;
    ref array<string> TargetActions = new array<string>;
    ref array<string> ToolActions = new array<string>;
    ref HCItemUtilityState TargetBefore;
    ref HCItemUtilityState TargetAfter;
    ref HCItemUtilityState ToolBefore;
    ref HCItemUtilityState ToolAfter;
    int ByteBound;
    bool RuntimeQualified; // never promoted by this source
}

class HCItemUtilitySummary
{
    int SchemaVersion = 1;
    int Total;
    int Emitted;
    int Remaining;
    int ByteBound;
    int CreatedObjects;
    int DeleteRequests;
    bool CleanupConfirmed;
    bool Complete;
    bool Partial;
    string Reason;
    bool RuntimeQualified;
}

class HCItemUtilityDiagnostic
{
    protected static bool s_Active;
    protected bool m_Running;
    protected bool m_Stopped;
    protected bool m_Execute;
    protected bool m_Partial;
    protected bool m_PairDeleting;
    protected bool m_FixturesDeleting;
    protected string m_Reason;
    protected int m_Total;
    protected int m_Cursor;
    protected int m_Emitted;
    protected int m_StartedMs;
    protected int m_MaxMillis;
    protected int m_Bytes;
    protected int m_MaxBytes;
    protected int m_CreatedObjects;
    protected int m_DeleteRequests;
    protected vector m_Position;
    // Raw allocations are retained even when the ItemBase/PlayerBase cast fails.
    protected Object m_ActorObject;
    protected PlayerBase m_Actor;
    protected EntityAI m_Bag;
    protected EntityAI m_TargetObject;
    protected EntityAI m_ToolObject;
    protected ItemBase m_Target;
    protected ItemBase m_Tool;

    static string KitAt(int index)
    {
        if (index == 0) return "WeaponCleaningKit";
        if (index == 1) return "SewingKit";
        if (index == 2) return "LeatherSewingKit";
        if (index == 3) return "Whetstone";
        if (index == 4) return "DuctTape";
        if (index == 5) return "TireRepairKit";
        if (index == 6) return "ElectronicRepairKit";
        if (index == 7) return "EpoxyPutty";
        if (index == 8) return "Blowtorch";
        if (index == 9) return "WoodenPlank";
        if (index == 10) return "Pliers";
        if (index == 11) return "Fabric";
        return "";
    }

    static string RecipeAt(int index)
    {
        if (index == 0) return "CleanWeapon";
        if (index == 1) return "RepairWithSewingKit";
        if (index == 2) return "RepairWithLeatherSewingKit";
        if (index == 3) return "SharpenMelee";
        if (index == 4) return "RepairWithTape";
        if (index == 5) return "RepairWithTireKit";
        if (index == 6) return "RepairElectric";
        if (index == 7) return "RepairEpoxy";
        if (index == 9) return "RepairPlanks";
        if (index == 10) return "RepairWithPliers";
        // Blowtorch fuel/selection and Fabric deployed-zone action stay separate.
        return "";
    }

    static typename ActionAt(int index)
    {
        if (index == 0) return ActionRepairBoatChassis;
        if (index == 1) return ActionRepairBoatEngine;
        if (index == 2) return ActionRepairCarChassis;
        if (index == 3) return ActionRepairCarChassisWithBlowtorch;
        if (index == 4) return ActionRepairCarEngine;
        if (index == 5) return ActionRepairCarEngineWithBlowtorch;
        if (index == 6) return ActionRepairCarPart;
        if (index == 7) return ActionRepairCarPartWithBlowtorch;
        if (index == 8) return ActionRepairItemWithBlowtorch;
        if (index == 9) return ActionRepairMotorbikeChassis;
        if (index == 10) return ActionRepairMotorbikeChassisWithBlowtorch;
        if (index == 11) return ActionRepairMotorbikeEngine;
        if (index == 12) return ActionRepairMotorbikeEngineWithBlowtorch;
        if (index == 13) return ActionRepairMotorbikePart;
        if (index == 14) return ActionRepairMotorbikePartWithBlowTorch;
        if (index == 15) return ActionRepairPart;
        if (index == 16) return ActionRepairShelter;
        if (index == 17) return ActionRepairTent;
        if (index == 18) return ActionRepairTentPart;
        return ActionRepairVehiclePartBase;
    }

    // This allowlist is a creation safety boundary, never a sample limit. Every
    // supplied class still gets a row. Unknown actors, explosives, bases and
    // arbitrary world definitions are recorded as creation-unreviewed-pending.
    // Expand only after inspecting concrete config AND script construction.
    static bool SafeConcrete(string root, string name)
    {
        if (root == "CfgWeapons")
            return name == "AKM";
        if (root != "CfgVehicles")
            return false;
        if (HCSalvageTools.Allows("KitchenKnife", name)) return true;
        if (HCSalvageSources.AllowsSource("HCRecoverLargeLeather", name)) return true;
        if (HCSalvageSources.AllowsSource("HCRecoverMediumLeather", name)) return true;
        if (HCSalvageSources.AllowsSource("HCRecoverBatWood", name)) return true;
        if (name == "WoodenCrate" || name == "SeaChest") return true;
        if (name == "CableReel" || name == "CamoNet") return true;
        if (name == "Chainmail" || name == "Chainmail_Coif" || name == "Chainmail_Leggings") return true;
        if (name == "WitchHoodCoif_Black" || name == "Truck_01_Wheel") return true;
        if (name == "TShirt_Green" || name == "SmallTent") return true;
        for (int kitIndex = 0; kitIndex < 12; kitIndex++)
        {
            if (name == KitAt(kitIndex)) return true;
        }
        return false;
    }

    // One source object per instance; exclusive across instances until deletion
    // confirmation. No caller-owned actor, target, tool or profile is accepted.
    bool Begin(int totalRows, bool explicitOptIn, bool isolatedExternalProfileConfirmed, vector fixturePosition, bool executeRepairs = false, int maxMillis = 60000, int maxBytes = 16777216)
    {
        if (!GetGame() || !GetGame().IsServer() || !explicitOptIn || !isolatedExternalProfileConfirmed)
            return false;
        if (s_Active || m_Running || m_Stopped)
            return false;
        if (totalRows < 1 || totalRows > 262144 || maxMillis < 1 || maxMillis > 60000)
            return false;
        if (maxBytes < 131072 || maxBytes > 67108864)
            return false;
        array<Man> players = new array<Man>;
        GetGame().GetPlayers(players);
        if (players.Count() > 0)
            return false;
        s_Active = true;
        m_Running = true;
        m_Total = totalRows;
        m_Position = fixturePosition;
        m_Execute = executeRepairs;
        m_MaxMillis = maxMillis;
        m_MaxBytes = maxBytes;
        m_StartedMs = GetGame().GetTime();
        return true;
    }

    protected bool BudgetAllows(int now, int rowBytes)
    {
        if (now < m_StartedMs || now - m_StartedMs >= m_MaxMillis)
            return false;
        if (rowBytes < 0 || rowBytes > m_MaxBytes - m_Bytes - 1024)
            return false;
        return true;
    }

    protected bool ValidRequest(HCItemUtilityRequest request)
    {
        if (!request || request.Index != m_Cursor || m_Cursor >= m_Total)
            return false;
        if (request.ItemClass.Length() < 1 || request.ItemClass.Length() > 128)
            return false;
        // No spaces, separators or config subpaths accepted in a class identity.
        string alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789";
        for (int charIndex = 0; charIndex < request.ItemClass.Length(); charIndex++)
        {
            string character = request.ItemClass.Substring(charIndex, 1);
            if (!alphabet.Contains(character))
                return false;
        }
        if (request.KitIndex < -1 || request.KitIndex > 11)
            return false;
        return request.ConfigRoot == "CfgVehicles" || request.ConfigRoot == "CfgWeapons" || request.ConfigRoot == "CfgMagazines" || request.ConfigRoot == "CfgAmmo";
    }

    protected void ObserveMetadata(HCItemUtilityRequest request, HCItemUtilityObservation row)
    {
        row.Index = request.Index;
        row.ConfigRoot = request.ConfigRoot;
        row.ItemClass = request.ItemClass;
        string path = request.ConfigRoot + " " + request.ItemClass;
        row.Status = "config-missing-pending";
        if (!GetGame().ConfigIsExisting(path)) return;
        row.Status = "metadata-only";
        if (GetGame().ConfigIsExisting(path + " scope"))
        {
            row.ScopeType = GetGame().ConfigGetType(path + " scope");
            if (row.ScopeType == CT_INT) row.Scope = GetGame().ConfigGetInt(path + " scope");
        }
        if (GetGame().ConfigIsExisting(path + " repairKitType"))
        {
            row.RepairKitFieldType = GetGame().ConfigGetType(path + " repairKitType");
            if (row.RepairKitFieldType == CT_INT) row.RepairKitType = GetGame().ConfigGetInt(path + " repairKitType");
        }
        if (GetGame().ConfigIsExisting(path + " repairableWithKits"))
        {
            row.RepairableFieldType = GetGame().ConfigGetType(path + " repairableWithKits");
            if (row.RepairableFieldType == CT_ARRAY) GetGame().ConfigGetIntArray(path + " repairableWithKits", row.RepairableWithKits);
        }
        if (GetGame().ConfigIsExisting(path + " repairCosts"))
        {
            row.CostsFieldType = GetGame().ConfigGetType(path + " repairCosts");
            if (row.CostsFieldType == CT_ARRAY) GetGame().ConfigGetFloatArray(path + " repairCosts", row.RepairCosts);
        }
        if (row.RepairableWithKits.Count() > 128 || row.RepairCosts.Count() > 128)
        {
            row.RepairableWithKits.Clear();
            row.RepairCosts.Clear();
            row.Status = "array-limit-pending";
            return;
        }
        map<string, bool> ancestorsSeen = new map<string, bool>;
        foreach (string priorAncestor : row.Ancestors) { ancestorsSeen.Set(priorAncestor, true); }
        string ancestor;
        string current = request.ItemClass;
        for (int depth = 0; depth < 64; depth++)
        {
            if (!GetGame().ConfigGetBaseName(request.ConfigRoot + " " + current, ancestor) || ancestor == "")
            {
                row.AncestryComplete = true;
                return;
            }
            if (ancestor.Length() > 128 || ancestorsSeen.Contains(ancestor)) return;
            row.Ancestors.Insert(ancestor);
            ancestorsSeen.Set(ancestor, true);
            current = ancestor;
        }
    }

    protected bool EnsureActor()
    {
        if (m_Actor) return !m_Actor.GetIdentity() && m_Actor.IsAlive();
        m_ActorObject = GetGame().CreatePlayer(null, "SurvivorM_Mirek", m_Position, 0, "NONE");
        if (m_ActorObject) m_CreatedObjects++;
        m_Actor = PlayerBase.Cast(m_ActorObject);
        if (!m_Actor || m_Actor.GetIdentity()) return false;
        m_Bag = m_Actor.GetInventory().CreateAttachment("MountainBag_Blue");
        if (m_Bag) m_CreatedObjects++;
        return m_Bag != null;
    }

    protected HCItemUtilityState Snapshot(ItemBase item)
    {
        HCItemUtilityState state = new HCItemUtilityState;
        if (!item) return state;
        state.Present = true;
        state.Deleting = item.IsSetForDeletion();
        state.Health = item.GetHealth01("", "");
        state.HasQuantity = item.HasQuantity();
        state.Quantity = item.GetQuantity();
        state.Wet = item.GetWet();
        state.Agents = item.GetAgents();
        state.Attachments = item.GetInventory().AttachmentCount();
        CargoBase cargo = item.GetInventory().GetCargo();
        if (cargo) state.CargoItems = cargo.GetItemCount();
        Magazine magazine = Magazine.Cast(item);
        if (magazine) state.Ammo = magazine.GetAmmoCount();
        if (item.GetCompEM()) state.Energy = item.GetCompEM().GetEnergy();
        item.GetDamageZones(state.Zones);
        if (state.Zones.Count() > 32)
        {
            state.Zones.Clear();
            return state;
        }
        for (int zoneIndex = 0; zoneIndex < state.Zones.Count(); zoneIndex++)
        {
            state.ZoneHealth.Insert(item.GetHealth01(state.Zones[zoneIndex], ""));
        }
        state.ZonesComplete = true;
        return state;
    }

    protected string ObserveAction(ItemBase item, typename actionType)
    {
        ActionBase action = ActionManagerBase.GetAction(actionType);
        if (!action) return "registry-unavailable-pending";
        array<ActionBase_Basic> actions;
        item.GetActions(action.GetInputType(), actions);
        if (!actions) return "absent-in-observed-input-map";
        if (actions.Count() > 512) return "action-map-limit-pending";
        if (actions.Find(action) >= 0) return "present-condition-unexecuted";
        return "absent-in-observed-input-map";
    }

    protected bool CanExecute(RecipeBase recipe, bool selected)
    {
        if (!m_Execute || !selected || !recipe || recipe.m_NumberOfResults != 0)
            return false;
        if (!m_Actor || !m_Target || !m_Tool)
            return false;
        if (!m_Actor.IsAlive() || m_Actor.IsUnconscious() || m_Actor.IsSetForDeletion())
            return false;
        if (m_Target.IsSetForDeletion() || m_Tool.IsSetForDeletion())
            return false;
        return m_Target.GetHierarchyRootPlayer() == m_Actor && m_Tool.GetHierarchyRootPlayer() == m_Actor;
    }

    protected void ObserveRepairEligibility(int kitIndex, HCItemUtilityObservation row)
    {
        if (!m_Target || !m_Tool) return;
        row.CanBeRepairedByCrafting = m_Target.CanBeRepairedByCrafting();
        row.CanBeRepairedToPristine = m_Target.CanBeRepairedToPristine();
        // The three special routes do not use regular-kit eligibility. Missing
        // plugins remain unobserved rather than becoming a negative verdict.
        if (kitIndex < 0 || kitIndex >= 9) return;
        PluginRepairing repairing = PluginRepairing.Cast(GetPlugin(PluginRepairing));
        if (!repairing) return;
        row.CanRepairObserved = true;
        row.CanRepair = repairing.CanRepair(m_Tool, m_Target);
    }

    protected void ObserveObjects(HCItemUtilityRequest request, HCItemUtilityObservation row)
    {
        if (row.Status != "metadata-only" || !row.AncestryComplete) return;
        if (row.Scope != 2 || request.KitIndex == -1) return;
        row.Status = "creation-unreviewed-pending";
        if (!request.CreationReviewed || !SafeConcrete(request.ConfigRoot, request.ItemClass)) return;
        if (m_TargetObject || m_ToolObject)
        {
            Stop("stale-fixture-partial");
            return;
        }
        if (!EnsureActor())
        {
            Stop("actor-creation-failed-partial");
            return;
        }
        row.Status = "creation-failed-observed";
        row.ToolClass = KitAt(request.KitIndex);
        row.RecipeClass = RecipeAt(request.KitIndex);
        m_TargetObject = m_Actor.GetHumanInventory().CreateInHands(request.ItemClass);
        if (m_TargetObject) m_CreatedObjects++;
        m_ToolObject = m_Bag.GetInventory().CreateInInventory(row.ToolClass);
        if (m_ToolObject) m_CreatedObjects++;
        row.Created = m_TargetObject && m_ToolObject;
        m_Target = ItemBase.Cast(m_TargetObject);
        m_Tool = ItemBase.Cast(m_ToolObject);
        row.CastSucceeded = m_Target && m_Tool;
        if (!row.CastSucceeded) return;
        // Initialize ONLY this newly allocated fixture target. This does not
        // establish pristine/ruined/zone/cargo policy for any existing item.
        m_Target.SetHealth01("", "", 0.40);
        ObserveRepairEligibility(request.KitIndex, row);
        for (int actionIndex = 0; actionIndex < 20; actionIndex++)
        {
            typename actionType = ActionAt(actionIndex);
            row.ActionNames.Insert(actionType.ToString());
            row.TargetActions.Insert(ObserveAction(m_Target, actionType));
            row.ToolActions.Insert(ObserveAction(m_Tool, actionType));
        }
        row.TargetBefore = Snapshot(m_Target);
        row.ToolBefore = Snapshot(m_Tool);
        row.Status = "manager-unavailable-pending";
        PluginRecipesManager manager = PluginRecipesManager.Cast(GetPlugin(PluginRecipesManager));
        if (!manager) return;
        manager.GetValidRecipes(m_Tool, m_Target, row.RecipeIds, m_Actor);
        if (row.RecipeIds.Count() > 512)
        {
            row.RecipeIds.Clear();
            row.Status = "recipe-limit-pending";
            return;
        }
        RecipeBase recipe;
        if (row.RecipeClass != "") recipe = manager.HCGetRegisteredSalvage(row.RecipeClass);
        if (recipe) row.RecipeId = recipe.GetID();
        row.Discovered = recipe && row.RecipeIds.Find(row.RecipeId) >= 0;
        row.Status = "native-route-observed";
        if (row.RecipeClass == "") row.Status = "special-action-condition-pending";
        // The only callable classes are the ten zero-output native maintenance
        // recipes above. Selection/zone/fuel actions never use this commit seam.
        if (BudgetAllows(GetGame().GetTime(), 65536) && CanExecute(recipe, row.Discovered))
        {
            row.Attempted = true; // consume one attempt before entering native code
            manager.PerformRecipeServer(row.RecipeId, m_Tool, m_Target, m_Actor);
        }
        row.TargetAfter = Snapshot(m_Target);
        row.ToolAfter = Snapshot(m_Tool);
        row.SameTargetHandle = m_Target && !m_Target.IsSetForDeletion() && m_Actor.GetItemInHands() == m_Target;
        row.SameToolHandle = m_Tool && !m_Tool.IsSetForDeletion() && m_Tool.GetHierarchyRootPlayer() == m_Actor;
    }

    protected bool RowFits(HCItemUtilityObservation row)
    {
        string payload;
        string error;
        if (!JsonFileLoader<HCItemUtilityObservation>.MakeData(row, payload, error, false)) return false;
        // Account for JSON integer bound itself, UTF-8 and framing. Do not
        // claim native strings' character count is their actual byte length.
        if (payload.Length() > 16000) return false;
        row.ByteBound = payload.Length() * 4 + 128;
        return BudgetAllows(GetGame().GetTime(), row.ByteBound);
    }

    bool ObserveNext(HCItemUtilityRequest request, HCItemUtilityObservation row)
    {
        if (!m_Running || m_Stopped || !row || row.Captured) return false;
        if (!BudgetAllows(GetGame().GetTime(), 65536))
        {
            Stop("budget-partial");
            return false;
        }
        if (m_PairDeleting && !PollCleanup()) return false;
        if (!ValidRequest(request)) return false;
        ObserveMetadata(request, row);
        ObserveObjects(request, row);
        if (m_Stopped) return false;
        row.Captured = true;
        if (!RowFits(row))
        {
            row.Captured = false;
            Stop("row-budget-partial");
            return false;
        }
        m_Bytes += row.ByteBound;
        m_Cursor++;
        m_Emitted++;
        DeletePair();
        if (m_Cursor == m_Total) Stop("supplied-queue-emitted");
        return true;
    }

    protected void DeletePair()
    {
        if (m_PairDeleting) return;
        m_PairDeleting = true;
        if (m_TargetObject)
        {
            GetGame().ObjectDelete(m_TargetObject);
            m_DeleteRequests++;
        }
        if (m_ToolObject)
        {
            GetGame().ObjectDelete(m_ToolObject);
            m_DeleteRequests++;
        }
    }

    protected void DeleteFixtures()
    {
        DeletePair();
        if (m_FixturesDeleting) return;
        m_FixturesDeleting = true;
        // Delete the owned actor tree only after pair cleanup has been issued.
        // Retain raw handles until the engine invalidates them on a later poll.
        if (m_Bag)
        {
            GetGame().ObjectDelete(m_Bag);
            m_DeleteRequests++;
        }
        if (m_ActorObject)
        {
            GetGame().ObjectDelete(m_ActorObject);
            m_DeleteRequests++;
        }
    }

    void Stop(string reason)
    {
        if (!m_Running || m_Stopped) return;
        m_Stopped = true;
        m_Partial = m_Cursor != m_Total;
        m_Reason = reason;
        DeleteFixtures();
    }

    // No deletion request or IsSetForDeletion flag is treated as confirmation.
    // Caller must keep polling even after Stop/timeout, then terminate the owned
    // disposable process if the external deadline expires. No timer is installed.
    bool PollCleanup()
    {
        if (m_TargetObject || m_ToolObject) return false;
        m_Target = null;
        m_Tool = null;
        m_PairDeleting = false;
        if (!m_Stopped) return true;
        if (m_Bag || m_ActorObject) return false;
        m_Actor = null;
        m_Running = false;
        s_Active = false;
        return true;
    }

    HCItemUtilitySummary Summary()
    {
        HCItemUtilitySummary summary = new HCItemUtilitySummary;
        summary.Total = m_Total;
        summary.Emitted = m_Emitted;
        summary.Remaining = m_Total - m_Cursor;
        summary.ByteBound = m_Bytes + 1024;
        summary.CreatedObjects = m_CreatedObjects;
        summary.DeleteRequests = m_DeleteRequests;
        summary.CleanupConfirmed = m_Stopped && !m_Running;
        summary.Complete = summary.CleanupConfirmed && !m_Partial && m_Total > 0;
        summary.Partial = !summary.Complete;
        summary.Reason = m_Reason;
        return summary;
    }
}

#endif
