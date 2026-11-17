
// Disposable 4_World observer/provider. Unarmed unless the generated mission begins.
class HCDSSample
{
    float elapsed;
    int frame;
    float health;
    bool death_processed;
    ref array<float> position = new array<float>;
    ref array<float> spine = new array<float>;
}
class HCDSCase
{
    int index;
    string name;
    int spawn_frame;
    int spawn_queue;
    int damage_frame;
    int damage_queue;
    int command_frame;
    int delete_frame;
    int delete_queue;
    int cleanup_frame;
    int cleanup_queue;
    float spawn_elapsed;
    float damage_elapsed;
    float command_elapsed;
    float delete_elapsed;
    float cleanup_elapsed;
    int damage_calls;
    int eval_calls;
    int before_type = -1;
    int after_type = -1;
    int command_type = -1;
    float hit_direction;
    float command_direction;
    string ammo;
    string zone;
    int ammo_physics_flag = -1;
    float ammo_damage;
    bool cleanup_confirmed;
    ref array<ref HCDSSample> samples = new array<ref HCDSSample>;
}
class HCDSReceipt
{
    int schema = 1;
    string kind = "native-death-selection-observations";
    string run_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    string request_sha256 = "59a74de61c6bbdc0843d4e3fe6af5894e91e5ab42ed065b2f20db58ebb460ee7";
    string world_name;
    string engine_version;
    string ce_initialization = "omitted";
    bool server_context;
    bool complete;
    bool failed;
    string reason;
    bool callbacks_detached;
    int frames;
    int queues;
    float elapsed_seconds;
    int peak_owned_entities;
    int owned_entities_remaining;
    bool render_observed;
    bool ragdoll_observed;
    bool gameplay_acceptance;
    ref array<ref HCDSCase> cases = new array<ref HCDSCase>;
}
class HCDS
{
    static ref HCDSReceipt State;
    static ref HCDSCase Row;
    static ZombieBase Victim;
    static EntityAI Source;
    static Object OwnedVictim;
    static Object OwnedSource;
    static bool Done;
    static int Phase;
    static float Started;
    static float LastTime;
    static float LastSample;

    static int Owned()
    {
        int count;
        if (OwnedVictim) count++;
        if (OwnedSource) count++;
        return count;
    }
    static float Elapsed()
    {
        return GetGame().GetTickTime() - Started;
    }
    static bool Save()
    {
        string error;
        if (!JsonFileLoader<HCDSReceipt>.SaveFile("$profile:hc-death-selection-result.json", State, error))
        {
            State.failed = true;
            State.complete = false;
            State.reason = "receipt-write-failed";
            Print("[HC Death Selection] FAIL receipt write run=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
            return false;
        }
        return true;
    }
    static void Begin()
    {
        if (State || Done || !GetGame() || !GetGame().IsServer()) return;
        if (FileExist("$profile:hc-death-selection-result.json"))
        {
            Done = true;
            Print("[HC Death Selection] REJECT stale receipt run=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
            return;
        }
        State = new HCDSReceipt;
        State.server_context = GetGame().IsServer();
        GetGame().GetWorldName(State.world_name);
        GetGame().GetVersion(State.engine_version);
        Started = GetGame().GetTickTime();
        LastTime = Started;
        if (State.world_name != "chernarusplus" || State.engine_version != "1.30.164289.70")
        {
            Fault("world-or-build");
            Stop();
            return;
        }
        if (!Save())
        {
            Stop();
            return;
        }
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(Tick, 100, true);
        if (!GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(Frame))
        {
            Fault("callback-registration");
            Stop();
        }
    }
    static void Fault(string reason)
    {
        if (!State || Done) return;
        State.failed = true;
        if (State.reason == "") State.reason = reason;
        // Native damage/command callbacks only latch failure; Tick owns cleanup.
    }
    static void Cleanup()
    {
        if (Phase == 3) return;
        Phase = 3;
        if (Row)
        {
            Row.delete_frame = State.frames;
            Row.delete_queue = State.queues;
            Row.delete_elapsed = Elapsed();
        }
        if (OwnedVictim) GetGame().ObjectDelete(OwnedVictim);
        if (OwnedSource) GetGame().ObjectDelete(OwnedSource);
        // Keep references: issuing deletion is not observing deletion.
    }
    static void Stop()
    {
        if (Done || !State) return;
        Done = true;
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(Tick);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(Frame);
        State.callbacks_detached = true;
        State.elapsed_seconds = Elapsed();
        State.owned_entities_remaining = Owned();
        State.complete = !State.failed && State.cases.Count() == 2 && Owned() == 0;
        Save();
        Print("[HC Death Selection] terminal run=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa complete=" + State.complete);
    }
    static void Interrupt()
    {
        if (!State || Done) return;
        Fault("mission-finished");
        // No synchronous deletion confirmation is claimed during shutdown.
        Stop();
    }
    static void Frame(float dt)
    {
        if (Done || !State) return;
        State.frames++;
        if (State.frames > 20000) Fault("frame-budget");
    }
    static void Sample()
    {
        if (!Victim || !Row || Row.samples.Count() >= 16)
        {
            Fault("sample-budget-or-missing-victim");
            return;
        }
        int bone = Victim.GetBoneIndexByName("spine3");
        if (bone < 0)
        {
            Fault("missing-spine");
            return;
        }
        HCDSSample sample = new HCDSSample;
        sample.elapsed = Elapsed();
        sample.frame = State.frames;
        sample.health = Victim.GetHealth("", "Health");
        sample.death_processed = Victim.IsDeathProcessed();
        vector position = Victim.GetPosition();
        vector spine = Victim.GetBonePositionWS(bone);
        for (int i = 0; i < 3; i++)
        {
            sample.position.Insert(position[i]);
            sample.spine.Insert(spine[i]);
        }
        Row.samples.Insert(sample);
        LastSample = sample.elapsed;
    }
    static void Spawn()
    {
        if (Owned() != 0 || State.cases.Count() >= 2)
        {
            Fault("ownership-or-case-bound");
            return;
        }
        vector vp = "100 0 100";
        vector sp = "102 0 100";
        float size = GetGame().GetWorld().GetWorldSize();
        if (vp[0] >= size || vp[2] >= size || sp[0] >= size || sp[2] >= size)
        {
            Fault("outside-world");
            return;
        }
        // Resolve terrain height before object creation, never reposition a live actor.
        vp[1] = GetGame().SurfaceY(vp[0], vp[2]);
        sp[1] = GetGame().SurfaceY(sp[0], sp[2]);
        if (!GetGame().ConfigIsExisting("CfgVehicles ZmbF_JournalistNormal_Blue") || !GetGame().ConfigIsExisting("CfgVehicles Stone") || !GetGame().ConfigIsExisting("CfgAmmo MeleeFist DamageApplied Health damage"))
        {
            Fault("stock-config-missing");
            return;
        }
        Row = new HCDSCase;
        Row.index = State.cases.Count();
        Row.name = "vanilla";
        if (Row.index == 1) Row.name = "impulse-selection";
        Row.spawn_frame = State.frames;
        Row.spawn_queue = State.queues;
        Row.spawn_elapsed = Elapsed();
        State.cases.Insert(Row);
        OwnedSource = GetGame().CreateObjectEx("Stone", sp, 0);
        Source = EntityAI.Cast(OwnedSource);
        OwnedVictim = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", vp, ECE_INITAI);
        Victim = ZombieBase.Cast(OwnedVictim);
        State.peak_owned_entities = Math.Max(State.peak_owned_entities, Owned());
        if (!Source || !Victim || !Victim.IsAlive())
        {
            Fault("owned-spawn-failed");
            return;
        }
        Phase = 1;
        Sample();
        if (!Save()) Fault("receipt-write-failed");
    }
    static void Damage()
    {
        if (!Victim || !Source || !Victim.IsAlive() || Victim.IsBeingBackstabbed())
        {
            Fault("pre-damage-state");
            return;
        }
        array<string> zones = new array<string>;
        Victim.GetDamageZones(zones);
        if (zones.Count() > 64 || zones.Find("Torso") < 0)
        {
            Fault("stock-torso-zone-missing");
            return;
        }
        Row.ammo = "MeleeFist";
        Row.zone = "Torso";
        Row.ammo_physics_flag = GetGame().ConfigGetInt("CfgAmmo MeleeFist doPhxImpulse");
        Row.ammo_damage = GetGame().ConfigGetFloat("CfgAmmo MeleeFist DamageApplied Health damage");
        if (Row.ammo_physics_flag != 0 || !(Row.ammo_damage > 0) || !(Row.ammo_damage <= 1000000))
        {
            Fault("native-ammo-policy");
            return;
        }
        Row.damage_frame = State.frames;
        Row.damage_queue = State.queues;
        Row.damage_elapsed = Elapsed();
        Row.damage_calls++;
        Phase = 2;
        // GetDamageZonePos returns world space; ProcessDirectDamage takes model space.
        vector modelPos = Victim.WorldToModel(Victim.GetDamageZonePos("Torso"));
        Victim.ProcessDirectDamage(DamageType.CUSTOM, Source, "Torso", "MeleeFist",
            modelPos, 100.0, ProcessDirectDamageFlags.ALL_TRANSFER);
        if (!Victim || Victim.IsAlive() || Row.eval_calls != 1)
        {
            Fault("native-fatal-damage-not-observed");
            return;
        }
        Sample();
        if (!Save()) Fault("receipt-write-failed");
    }
    static void Tick()
    {
        if (Done || !State) return;
        State.queues++;
        float now = GetGame().GetTickTime();
        if (!(now >= LastTime) || !(now - Started <= 60) || State.queues > 512)
            Fault("clock-or-fixture-budget");
        LastTime = now;
        State.elapsed_seconds = now - Started;
        array<PlayerIdentity> clients = new array<PlayerIdentity>;
        GetGame().GetPlayerIndentities(clients);
        if (clients.Count() != 0) Fault("unexpected-clients");
        if (State.failed) Cleanup();
        if (State.frames < 2 || State.queues < 2) return;
        if (Phase == 0 && !State.failed)
        {
            Spawn();
            return;
        }
        if (Phase == 1 && !State.failed)
        {
            if (State.frames > Row.spawn_frame && State.queues > Row.spawn_queue) Damage();
            return;
        }
        if (Phase == 2 && !State.failed)
        {
            if (!Victim || !Source)
            {
                Fault("actor-disappeared");
                return;
            }
            if (Elapsed() - LastSample >= 0.25) Sample();
            if (!State.failed && Elapsed() - Row.damage_elapsed >= 2.0 && Row.command_frame > 0 && State.frames > Row.command_frame)
            {
                Sample();
                Cleanup();
            }
        }
        if (Phase == 3)
        {
            if (!Row || Elapsed() - Row.delete_elapsed > 2)
            {
                State.failed = true;
                if (State.reason == "") State.reason = "deletion-deadline";
                Stop();
                return;
            }
            if (Owned() == 0 && Row && State.frames > Row.delete_frame && State.queues > Row.delete_queue)
            {
                Row.cleanup_frame = State.frames;
                Row.cleanup_queue = State.queues;
                Row.cleanup_elapsed = Elapsed();
                Row.cleanup_confirmed = true;
                if (!Save()) Fault("receipt-write-failed");
                if (State.failed || State.cases.Count() == 2)
                {
                    Stop();
                    return;
                }
                Row = null;
                Phase = 0;
                return;
            }
        }
    }
}
modded class ZombieBase
{
    override bool EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data,
        out int pAnimType, out float pAnimHitDir)
    {
        bool result = super.EvaluateDeathAnimationEx(pSource, data, pAnimType, pAnimHitDir);
        if (HCDS.Victim != this || !HCDS.Row || HCDS.Done) return result;
        if (!result || !data || pSource != HCDS.Source || data.m_AmmoType != "MeleeFist" || data.m_DamageZone != "Torso" || IsBeingBackstabbed() || IsAlive() || HCDS.Phase != 2 || HCDS.Row.eval_calls != 0)
        {
            HCDS.Fault("unexpected-native-death-evaluation");
            return result;
        }
        HCDS.Row.eval_calls++;
        HCDS.Row.before_type = pAnimType;
        if (pAnimType != DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT)
        {
            HCDS.Fault("unexpected-native-animation");
            return result;
        }
        if (HCDS.Row.index == 1) pAnimType = DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;
        HCDS.Row.after_type = pAnimType;
        HCDS.Row.hit_direction = pAnimHitDir;
        return result;
    }
    override void CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)
    {
        if (HCDS.Victim == this && HCDS.Row && !HCDS.Done && pCurrentCommandID == DayZInfectedConstants.COMMANDID_DEATH && HCDS.Row.command_frame == 0)
        {
            HCDS.Row.command_frame = HCDS.State.frames;
            HCDS.Row.command_elapsed = HCDS.Elapsed();
            HCDS.Row.command_type = m_DeathType;
            HCDS.Row.command_direction = m_DamageHitDirection;
        }
        super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished);
    }
}
