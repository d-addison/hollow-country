
// Hollow Country DISPOSABLE infected competence probe. Runtime acceptance PENDING.
// One owned entity at a time. Two endpoint samples; no player competence inference.
class HCICSample
{
    int mind = -1;
    bool target;
    bool crawling;
    bool alive;
    string left;
    string right;
    string position;
}
class HCICDoor
{
    int index;
    bool opened;
    bool locked;
}
class HCICTrial
{
    string id;
    string kind;
    string support_state;
    string status = "inconclusive";
    string reason;
    bool observed;
    int spawned;
    int deleted;
    int elapsed_ms;
    string anchor_authored_y;
    string anchor_surface_y;
    string spawn_authored_y;
    string spawn_surface_y;
    ref array<ref HCICSample> samples = new array<ref HCICSample>;
    ref array<ref HCICDoor> doors = new array<ref HCICDoor>;
    ref array<int> geometry = new array<int>;
}
class HCICReceipt
{
    int schema = 1;
    string kind = "infected-competence-observations";
    string hook_sha256;
    string status = "partial";
    string world;
    string version;
    int clients;
    int spawned;
    int deleted;
    ref array<ref HCICTrial> trials = new array<ref HCICTrial>;
}
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_Started;
    protected bool m_Done;
    protected bool m_Ready;
    protected int m_Index;
    protected int m_TrialBegin;
    protected int m_Begin;
    protected float m_LegBefore;
    protected Object m_Owned;
    protected ZombieBase m_Actor;
    protected ref HCICReceipt m_Receipt;
    protected ref HCICTrial m_Trial;

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_Started)
            return;
        m_Started = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICBegin, 30000, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICWatchdog, 124900, false);
    }

    override void OnMissionFinish()
    {
        HCICCleanup();
        if (m_Ready && !m_Done)
            HCICFinish("partial");
        super.OnMissionFinish();
    }

    bool HCICNoClients()
    {
        array<PlayerIdentity> identities = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(identities);
        if (identities.Count() != 0)
        {
            m_Receipt.clients = identities.Count();
            HCICFinish("partial");
            return false;
        }
        return true;
    }

    void HCICBegin()
    {
        if (m_Done)
            return;
        string directory = "$profile:HCInfectedCompetence";
        if (FileExist(directory))
        {
            m_Done = true;
            return;
        }
        if (!MakeDirectory(directory))
        {
            m_Done = true;
            return;
        }
        m_Receipt = new HCICReceipt;
        FileHandle hashFile = OpenFile("$mission:hc-infected-hook-sha.txt", FileMode.READ);
        if (!hashFile)
        {
            m_Done = true;
            return;
        }
        string hookHash;
        int readCount = ReadFile(hashFile, hookHash, 64);
        CloseFile(hashFile);
        if (readCount != 64 || hookHash.Length() != 64)
        {
            m_Done = true;
            return;
        }
        m_Receipt.hook_sha256 = hookHash;
        string worldName;
        string buildName;
        GetGame().GetWorldName(worldName);
        GetGame().GetVersion(buildName);
        m_Receipt.world = worldName;
        m_Receipt.version = buildName;
        m_Ready = true;
        m_Begin = GetGame().GetTime();
        HCICStep();
    }

    void HCICSetup(int sequence, out string structureName, out vector anchor, out vector spawnPoint)
    {
        if (sequence == 0)
        {
            m_Trial.id = "t000";
            m_Trial.kind = "spawn_lifecycle";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "Native spawn/state/delete at authored fixed position.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 1)
        {
            m_Trial.id = "t001";
            m_Trial.kind = "mind_no_target";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "Two native mind-state samples; target presence invalidates no-target control.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 2)
        {
            m_Trial.id = "t002";
            m_Trial.kind = "door_state";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "Read existing door open/locked state only; no contact or opening inference.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 3)
        {
            m_Trial.id = "t003";
            m_Trial.kind = "footprint_geometry";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "Four short view-geometry rays at spawn height; not LOS acquisition or full collision proof.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 4)
        {
            m_Trial.id = "t004";
            m_Trial.kind = "limb_damage";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "One LeftLeg DecreaseHealth stimulus; before/after limb health and alive state.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 5)
        {
            m_Trial.id = "t005";
            m_Trial.kind = "crawl_health_only";
            m_Trial.support_state = "server_observable";
            m_Trial.reason = "LeftLeg health-only decrease and IsCrawling endpoints; hit-path not exercised, no crawl-transition inference.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 6)
        {
            m_Trial.id = "t006";
            m_Trial.kind = "player_los_chase";
            m_Trial.support_state = "client_required";
            m_Trial.reason = "Requires a real connected player and paired LOS/chase observations; server-only has no target.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 7)
        {
            m_Trial.id = "t007";
            m_Trial.kind = "player_wall_attack";
            m_Trial.support_state = "client_required";
            m_Trial.reason = "Requires real player damage/attack observations through walls with two clients.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
        if (sequence == 8)
        {
            m_Trial.id = "t008";
            m_Trial.kind = "audible_pursuit";
            m_Trial.support_state = "client_required";
            m_Trial.reason = "Requires two clients hearing pursuit on surfaces, at distance and through occlusion.";
            structureName = "Land_House_1W01";
            anchor = Vector(6505.000000, 0.000000, 2500.000000);
            spawnPoint = Vector(6500.000000, 0.000000, 2500.000000);
            return;
        }
    }

    Building HCICStructure(string expected, vector anchor)
    {
        array<Object> nearby = new array<Object>;
        array<CargoBase> proxyCargos = new array<CargoBase>;
        // Allow a bounded vertical-origin tolerance on slopes; ambiguity still refuses.
        GetGame().GetObjectsAtPosition3D(anchor, 5.0, nearby, proxyCargos);
        if (nearby.Count() > 128 || proxyCargos.Count() > 128)
            return null;
        Building chosen;
        int matches = 0;
        for (int scanIndex = 0; scanIndex < nearby.Count() && scanIndex < 128; scanIndex++)
        {
            Building candidate = Building.Cast(nearby.Get(scanIndex));
            if (candidate && candidate.GetType() == expected)
            {
                chosen = candidate;
                matches = matches + 1;
            }
        }
        if (matches != 1)
            return null;
        return chosen;
    }

    bool HCICGeometry(vector spawnPoint)
    {
        bool clear = true;
        vector rayBegin = spawnPoint + Vector(0, 0.8, 0);
        for (int rayIndex = 0; rayIndex < 4; rayIndex++)
        {
            vector rayOffset = Vector(0.6, 0, 0);
            if (rayIndex == 1)
                rayOffset = Vector(-0.6, 0, 0);
            if (rayIndex == 2)
                rayOffset = Vector(0, 0, 0.6);
            if (rayIndex == 3)
                rayOffset = Vector(0, 0, -0.6);
            vector rayEnd = rayBegin + rayOffset;
            vector contactPoint;
            vector contactDirection;
            int contactComponent;
            bool hit = DayZPhysics.RaycastRV(rayBegin, rayEnd, contactPoint, contactDirection, contactComponent);
            int hitValue = 0;
            if (hit)
            {
                hitValue = 1;
                clear = false;
            }
            m_Trial.geometry.Insert(hitValue);
        }
        return clear;
    }

    bool HCICSampleActor()
    {
        if (!m_Actor || !m_Actor.IsAlive())
            return false;
        DayZInfectedInputController nativeInput = m_Actor.GetInputController();
        if (!nativeInput)
            return false;
        HCICSample sampleRow = new HCICSample;
        sampleRow.mind = nativeInput.GetMindState();
        if (nativeInput.GetTargetEntity())
            sampleRow.target = true;
        sampleRow.crawling = m_Actor.IsCrawling();
        sampleRow.alive = m_Actor.IsAlive();
        sampleRow.left = m_Actor.GetHealth("LeftLeg", "Health").ToString();
        sampleRow.right = m_Actor.GetHealth("RightLeg", "Health").ToString();
        vector actualPoint = m_Actor.GetPosition();
        sampleRow.position = actualPoint.ToString();
        m_Trial.samples.Insert(sampleRow);
        if (sampleRow.target)
            return false;
        return true;
    }

    void HCICStep()
    {
        if (m_Done)
            return;
        if (!HCICNoClients())
            return;
        if (GetGame().GetTime() - m_Begin > 84900)
        {
            HCICFinish("partial");
            return;
        }
        if (m_Index >= 9)
        {
            HCICFinish("complete");
            return;
        }
        m_Trial = new HCICTrial;
        string structureName;
        vector anchor;
        vector spawnPoint;
        HCICSetup(m_Index, structureName, anchor, spawnPoint);
        m_Receipt.trials.Insert(m_Trial);
        m_TrialBegin = GetGame().GetTime();
        if (m_Trial.support_state == "client_required")
        {
            m_Trial.status = "client_required";
            HCICNext();
            return;
        }
        m_Trial.anchor_authored_y = anchor[1].ToString();
        m_Trial.spawn_authored_y = spawnPoint[1].ToString();
        anchor[1] = GetGame().SurfaceY(anchor[0], anchor[2]);
        spawnPoint[1] = GetGame().SurfaceY(spawnPoint[0], spawnPoint[2]);
        m_Trial.anchor_surface_y = anchor[1].ToString();
        m_Trial.spawn_surface_y = spawnPoint[1].ToString();
        Building structure = HCICStructure(structureName, anchor);
        if (!structure)
        {
            m_Trial.reason = "structure_missing_ambiguous_or_query_budget";
            HCICNext();
            return;
        }
        if (!HCICGeometry(spawnPoint))
        {
            m_Trial.reason = "footprint_ray_hit";
            HCICNext();
            return;
        }
        m_Owned = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", spawnPoint, ECE_PLACE_ON_SURFACE|ECE_INITAI);
        if (m_Owned)
        {
            m_Trial.spawned = 1;
            m_Receipt.spawned = m_Receipt.spawned + 1;
        }
        m_Actor = ZombieBase.Cast(m_Owned);
        if (!HCICSampleActor())
        {
            m_Trial.reason = "spawn_controller_or_no_target_control_failed";
            HCICNext();
            return;
        }
        if (m_Trial.kind == "door_state")
        {
            int doorCount = structure.GetDoorCount();
            if (doorCount < 1 || doorCount > 16)
            {
                m_Trial.reason = "door_budget_or_no_doors";
                HCICNext();
                return;
            }
            for (int doorIndex = 0; doorIndex < doorCount && doorIndex < 16; doorIndex++)
            {
                HCICDoor doorRow = new HCICDoor;
                doorRow.index = doorIndex;
                doorRow.opened = structure.IsDoorOpen(doorIndex);
                doorRow.locked = structure.IsDoorLocked(doorIndex);
                m_Trial.doors.Insert(doorRow);
            }
        }
        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_health_only")
        {
            float legHealth = m_Actor.GetHealth("LeftLeg", "Health");
            if (legHealth <= 0 || legHealth > 10000)
            {
                m_Trial.reason = "invalid_initial_leg_health";
                HCICNext();
                return;
            }
            m_LegBefore = legHealth;
            m_Actor.DecreaseHealth("LeftLeg", "Health", legHealth);
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICObserve, 5000, false);
    }

    void HCICObserve()
    {
        if (m_Done)
            return;
        if (!HCICNoClients())
            return;
        int elapsed = GetGame().GetTime() - m_TrialBegin;
        if (elapsed > 5000 + 1000)
        {
            m_Trial.reason = "trial_time_budget";
            HCICNext();
            return;
        }
        if (!HCICSampleActor())
        {
            m_Trial.reason = "actor_dead_missing_or_target_present";
            HCICNext();
            return;
        }
        if (m_Trial.kind == "limb_damage" || m_Trial.kind == "crawl_health_only")
        {
            float currentLegHealth = m_Actor.GetHealth("LeftLeg", "Health");
            if (currentLegHealth >= m_LegBefore)
            {
                m_Trial.reason = "left_leg_health_did_not_fall";
                HCICNext();
                return;
            }
        }
        m_Trial.observed = true;
        m_Trial.status = "completed";
        m_Trial.reason = "two_endpoint_samples_only";
        HCICNext();
    }

    void HCICCleanup()
    {
        if (m_Owned)
        {
            GetGame().ObjectDelete(m_Owned);
            m_Receipt.deleted = m_Receipt.deleted + 1;
            if (m_Trial)
                m_Trial.deleted = m_Trial.deleted + 1;
        }
        m_Owned = null;
        m_Actor = null;
    }

    void HCICNext()
    {
        HCICCleanup();
        if (m_Trial.support_state == "client_required")
            m_Trial.elapsed_ms = 0;
        else
            m_Trial.elapsed_ms = GetGame().GetTime() - m_TrialBegin;
        m_Index = m_Index + 1;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCICStep, 100, false);
    }

    void HCICWatchdog()
    {
        if (m_Ready && !m_Done)
            HCICFinish("partial");
        m_Done = true;
    }

    void HCICFinish(string outcome)
    {
        if (m_Done)
            return;
        HCICCleanup();
        m_Done = true;
        m_Receipt.status = outcome;
        string outputData;
        string outputError;
        if (!JsonFileLoader<HCICReceipt>.MakeData(m_Receipt, outputData, outputError, false))
            return;
        if (outputData.Length() > 262144)
            return;
        FileHandle outputFile = OpenFile("$profile:HCInfectedCompetence/observations.json", FileMode.WRITE);
        if (!outputFile)
            return;
        FPrint(outputFile, outputData);
        CloseFile(outputFile);
        FileHandle sentinelFile = OpenFile("$profile:HCInfectedCompetence/complete.txt", FileMode.WRITE);
        if (!sentinelFile)
            return;
        FPrintln(sentinelFile, "status=" + outcome);
        CloseFile(sentinelFile);
    }
}
