"""Prepare a disposable five-case native infected death diagnostic; never launch.

API: prepare_probe(source,destination,scripts_root,*,x,z,seconds_per_case=2,
impulse=(0,0,0),allow_observers=False,run_id=None). Source/destination are outside
Steam/source, stock factory preserved, fresh destination only. Interface records
contain hashes, not installed code. Partial staging is retained and not reusable.

The health-only control uses native health/death handling. Remaining cases request
the four native death enums, NOT damage/ammo/finisher equivalence. Infected expose
no inspected command-ID getter or Human ragdoll methods. Samples record health,
animation UUID, death processing, origin/spine and attached-body state/velocity.
Impulse is an explicit bounded diagnostic vector (length <=120 native units),
only applied to a present dynamic body in the impulse case; zero is the default.
Generated vectors use six decimal places; nonzero values rounding to zero fail.
No physics body, collision, gravity, inventory, production class or PBO is changed.

OnInit starts synchronously. SYSTEM queue and update callbacks remain subject to
native scheduling/clock progress: an EXTERNAL wall-clock timeout <=90s is mandatory.
Internal observation watchdog 60s, one actor, five cases, <=32 samples/case,
<=20 heartbeat logs, <=20000 frames, 2s observed-deletion windows. A requested
delete never counts as confirmation. Mission shutdown requests owned cleanup but
cannot claim it completed. Failure/interruption receipts are never promoted.

validate_result(path,mission,*,outer_timed_out) requires the actual outer outcome;
even a final receipt cannot pass after timeout. This is bounded structural checking
of operator-supplied evidence, not engine authentication or proof of a fresh run.
Default nonce is fresh, so old receipts fail correlation; no live profiles read.

MakeScreenshot is declared in installed 1_Core/proto/proto.c, but this server
mission does not capture/render. No limb ragdoll, visual, loot-access, collision,
network, performance or production acceptance follows from server observations.
Those require paired rendered clients and normal signed-PBO/server qualification.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat

from tools.setup import diagnostic_mission as staging

CASES=('health-only','default-command','impulse-command','backstab-command','neckstab-command')
MARKER='.hc-infected-death-probe.json'
KIND='native-infected-death-observations'
RESULT='hc-infected-death-result.json'
MAX_JSON_BYTES=256*1024
INTERFACES={
    '3_Game/Entities/DayZInfected.c': ('class DayZInfected extends DayZCreatureAI',
        'ANIM_DEATH_DEFAULT = 0','ANIM_DEATH_IMPULSE = 1','ANIM_DEATH_BACKSTAB = 2',
        'ANIM_DEATH_NECKSTAB = 3','StartCommand_Death(int pType, float pDirection)'),
    '4_World/Entities/Creatures/Infected/ZombieBase.c': ('bool HandleDeath(int pCurrentCommandID)',
        'float m_DamageHitDirection = 0','int m_DeathType = 0',
        'StartCommand_Death(m_DeathType, m_DamageHitDirection)', 'dBodyApplyImpulse(this, impulse)'),
    '3_Game/Entities/DayZAnimal.c': ('class DayZCreature extends EntityAI',
        'class DayZCreatureAI extends DayZCreature','GetCurrentAnimationInstanceUUID()',
        'IsDeathProcessed()','GetBoneIndexByName(string pBoneName)'),
    '3_Game/Entities/Object.c': ('GetBonePositionWS(int pivot)',
        'SetHealth(string zoneName, string healthType, float value)'),
    '1_Core/proto/EnPhysics.c': ('dBodyIsSet(notnull IEntity ent)',
        'dBodyIsDynamic(notnull IEntity ent)','dBodyIsActive(notnull IEntity ent)',
        'GetVelocity(notnull IEntity ent)','dBodyApplyImpulse(notnull IEntity body, vector impulse)'),
    '3_Game/Global/Game.c': ('GetPlayerIndentities( out array<PlayerIdentity> identities )',
        'GetTickTime()', 'ObjectDelete(', 'CreateObjectEx('),
    '3_Game/DayZGame.c': ('if (doSim && mission)',
        'GetCallQueue(CALL_CATEGORY_SYSTEM).Tick(timeslice)',
        'GetUpdateQueue(CALL_CATEGORY_SYSTEM).Invoke(timeslice)'),
    '3_Game/tools/JsonFileLoader.c': ('static bool SaveFile(string filename, T data, out string errorMessage)',),
    '1_Core/proto/proto.c': ('proto native void MakeScreenshot(string name)',),
    '3_Game/human.c': ('PhysicsSetRagdoll(bool pEnable)',),
    '4_World/Plugins/PluginBase/PluginDayZInfectedDebug.c': ('CreateObjectEx("ZmbF_JournalistNormal_Blue"',
        'ECE_PLACE_ON_SURFACE|ECE_INITAI|ECE_EQUIP_ATTACHMENTS'),
}


def _safe(path):
    path=staging._safe_path(path)
    for node in (path,*path.parents):
        try: info=os.lstat(node)
        except FileNotFoundError: continue
        if getattr(info,'st_file_attributes',0)&1024:
            raise ValueError('reparse points forbidden')
    return path


def _read(path,limit):
    path=_safe(path);info=os.lstat(path)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>limit:
        raise ValueError('bounded regular input required')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0))
    with os.fdopen(fd,'rb') as stream:
        if staging._identity(os.fstat(stream.fileno()))!=staging._identity(info):
            raise ValueError('input changed')
        data=stream.read(limit+1)
    if len(data)!=info.st_size or staging._identity(os.lstat(path))!=staging._identity(info):
        raise ValueError('input changed/size exceeded')
    return data


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _encode(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def _pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value: raise ValueError('duplicate JSON key')
        value[key]=item
    return value


def _json(path):
    def constant(_): raise ValueError('nonfinite JSON')
    try:
        value=json.loads(_read(path,MAX_JSON_BYTES).decode('utf-8-sig'),object_pairs_hook=_pairs,parse_constant=constant)
    except (UnicodeError,json.JSONDecodeError,RecursionError) as exc:
        raise ValueError('malformed bounded UTF-8 JSON') from exc
    if type(value) is not dict: raise ValueError('JSON object required')
    return value


def inspect_interfaces(root):
    records={}
    for name,tokens in INTERFACES.items():
        data=_read(Path(root)/name,2*1024*1024)
        try: text=' '.join(data.decode('utf-8-sig').split())
        except UnicodeError as exc: raise ValueError('invalid installed interface encoding') from exc
        if any(' '.join(token.split()) not in text for token in tokens):
            raise ValueError('installed interface mismatch: '+name)
        records[name]={'sha256':_sha(data),'bytes':len(data)}
    return records


def _number(value,low,high):
    if type(value) not in (int,float) or not low<=value<=high:
        raise ValueError('finite number outside probe bounds')
    return value


def _options(x,z,seconds_per_case,impulse,allow_observers,run_id):
    for value in (x,z): _number(value,1,100000)
    if type(seconds_per_case) is not int or not 1<=seconds_per_case<=5:
        raise ValueError('integer observation window 1..5 seconds required')
    if type(impulse) not in (tuple,list) or len(impulse)!=3:
        raise ValueError('three-component impulse required')
    for value in impulse:
        _number(value,-120,120)
        if value!=0 and float(format(value,'.6f'))==0:
            raise ValueError('nonzero impulse below generated vector precision')
    if sum(value*value for value in impulse)>120*120:
        raise ValueError('impulse vector exceeds diagnostic safety bound')
    if type(allow_observers) is not bool or type(run_id) is not str or not re.fullmatch('[0-9a-f]{32}',run_id):
        raise ValueError('explicit observer policy and hexadecimal run ID required')


def prepare_probe(source,destination,scripts_root,*,x,z,seconds_per_case=2,impulse=(0,0,0),allow_observers=False,run_id=None):
    run_id=secrets.token_hex(16) if run_id is None else run_id
    _options(x,z,seconds_per_case,impulse,allow_observers,run_id)
    # Record the actual emitted vector, not higher precision Python inputs.
    impulse=tuple(float(format(value,'.6f')) for value in impulse)
    _options(x,z,seconds_per_case,impulse,allow_observers,run_id)
    source,destination=_safe(source),_safe(destination)
    if source==destination or source in destination.parents or destination in source.parents:
        raise ValueError('overlapping source/destination')
    if not source.is_dir() or destination.exists(): raise ValueError('existing source and fresh destination required')
    interfaces=inspect_interfaces(scripts_root)
    files,directories,total=staging._inventory(source)
    for relative,_ in files:
        if relative.name in {MARKER,RESULT,'.hc-native-autotest.json','hc-autotest.json'}:
            raise ValueError('previous instrumentation/result forbidden')
    if any(relative.parts[0].startswith('storage_') for relative in directories):
        raise ValueError('runtime storage forbidden')
    original=_read(source/'init.c',staging.MAX_INIT_BYTES)
    if any(token in original for token in (b'HCInfectedDeath',b'HCNativeAutotest',b'HCDisposableDiagnosticMission')):
        raise ValueError('instrumented source forbidden')
    if len(re.findall(rb'class\s+CustomMission\s*:\s*MissionServer\b',original))!=1:
        raise ValueError('stock CustomMission chain required')
    replaced,count=staging._FACTORY.subn(rb'\g<1>HCInfectedDeathProbeMission\g<2>',original)
    if count!=1 or len(re.findall(rb'\bCreateCustomMission\s*\(',original))!=1:
        raise ValueError('exact stock factory required')
    hook=HOOK.replace('@X@',format(x,'.6f')).replace('@Z@',format(z,'.6f'))
    hook=hook.replace('@SECONDS@',str(seconds_per_case)).replace('@RUN@',run_id)
    hook=hook.replace('@IMPULSE@',' '.join(format(v,'.6f') for v in impulse))
    hook=hook.replace('@OBSERVERS@','true' if allow_observers else 'false').encode()
    generated=replaced+hook
    manifest={'schema':1,'kind':KIND,'run_id':run_id,'cases':list(CASES),
        'max_owned_actors':1,'seconds_per_case':seconds_per_case,'impulse':list(impulse),
        'allow_observers':allow_observers,'spawn_xz':[x,z],'interfaces':interfaces,
        'runtime_acceptance':'pending','outer_timeout_required':True,'outer_timeout_max_seconds':90,
        'source_root':str(source),'mission_path':str(destination),'source_bytes':total,'files':{},
        'render_capture':'MakeScreenshot declaration inspected; not invoked in server mission',
        'command_observation':'requested enum + animation UUID; no infected command-ID getter inspected'}
    _safe(destination);destination.mkdir(parents=True,exist_ok=False)
    for relative in directories: (destination/relative).mkdir(exist_ok=False)
    for relative,info in files:
        src,dst=source/relative,destination/relative
        _safe(src);staging._unchanged(src,info)
        digest=hashlib.sha256()
        with src.open('rb') as stream,dst.open('xb') as output:
            remaining=info.st_size
            while remaining:
                data=stream.read(min(65536,remaining))
                if not data: raise ValueError('source truncated')
                digest.update(data)
                if relative.as_posix()!='init.c': output.write(data)
                remaining-=len(data)
            if stream.read(1): raise ValueError('source grew')
            if relative.as_posix()=='init.c': output.write(generated)
        staging._unchanged(src,info)
        staged=_read(dst,staging.MAX_FILE_BYTES)
        manifest['files'][relative.as_posix()]={'source_sha256':digest.hexdigest(),
            'staged_sha256':_sha(staged),'bytes':len(staged)}
    # Completion marker last. Partial output is intentionally never overwritten.
    with (destination/MARKER).open('xb') as stream: stream.write(_encode(manifest))
    return manifest


def validate_result(path,mission,*,outer_timed_out):
    if type(outer_timed_out) is not bool or outer_timed_out:
        raise ValueError('non-timed-out outer run outcome required')
    mission=_safe(mission);manifest=_json(mission/MARKER)
    if (type(manifest.get('schema')) is not int or manifest['schema']!=1 or
            manifest.get('kind')!=KIND or manifest.get('cases')!=list(CASES)):
        raise ValueError('prepared mission marker mismatch')
    spawn=manifest.get('spawn_xz')
    if type(spawn) is not list or len(spawn)!=2:
        raise ValueError('missing/bounded spawn coordinate pair required')
    _options(spawn[0],spawn[1],manifest.get('seconds_per_case'),manifest.get('impulse'),
             manifest.get('allow_observers'),manifest.get('run_id'))
    files=manifest.get('files')
    if type(files) is not dict or not 1<=len(files)<=staging.MAX_ENTRIES or 'init.c' not in files:
        raise ValueError('invalid staged file inventory')
    for name,record in files.items():
        if type(name) is not str or not name or '\\' in name or ':' in name or any(p in {'','..','.'} for p in name.split('/')) or name.startswith('/'):
            raise ValueError('invalid staged path')
        if type(record) is not dict or _sha(_read(mission/name,staging.MAX_FILE_BYTES))!=record.get('staged_sha256'):
            raise ValueError('staged source drift')
    value=_json(path)
    if (type(value.get('schema')) is not int or value['schema']!=1 or
            value.get('kind')!=KIND or value.get('run_id')!=manifest['run_id'] or
            value.get('complete') is not True or value.get('failed') is not False or value.get('reason')!='' or
            value.get('server_context') is not True or value.get('render_observed') is not False or
            value.get('replication_observed') is not False or value.get('allow_observers') is not manifest['allow_observers']):
        raise ValueError('incomplete/failed/stale receipt')
    for field,high in (('frames',20000),('heartbeat_count',20),('max_observed_clients',90)):
        if type(value.get(field)) is not int or not 0<=value[field]<=high: raise ValueError('invalid bounded telemetry')
    if not manifest['allow_observers'] and value['max_observed_clients']:
        raise ValueError('unexpected connected observers')
    for field in ('world','engine_version'):
        if type(value.get(field)) is not str or not 1<=len(value[field])<=128:
            raise ValueError('missing actual engine/world identity')
    cases=value.get('cases')
    if type(cases) is not list or len(cases)!=5: raise ValueError('exact five cases required')
    for index,(name,case) in enumerate(zip(CASES,cases)):
        if type(case) is not dict or type(case.get('index')) is not int or case['index']!=index or case.get('name')!=name:
            raise ValueError('case identity mismatch')
        for field in ('spawned','dead_observed','cleanup_requested','cleanup_confirmed'):
            if case.get(field) is not True: raise ValueError('missing observed lifecycle/cleanup')
        if case.get('command_requested') is not (index>0): raise ValueError('wrong death case method')
        impulse=index==2 and any(manifest['impulse'])
        if case.get('impulse_requested') is not impulse or type(case.get('impulse_applied')) is not bool:
            raise ValueError('wrong impulse record')
        if case['impulse_applied'] and not impulse: raise ValueError('unexpected impulse')
        samples=case.get('samples')
        if type(samples) is not list or not 2<=len(samples)<=32: raise ValueError('bounded nonempty samples required')
        previous=-1
        for sample in samples:
            if type(sample) is not dict: raise ValueError('invalid sample')
            elapsed=_number(sample.get('elapsed_seconds'),0,60)
            if elapsed<previous: raise ValueError('sample clock rollback')
            previous=elapsed
            _number(sample.get('health'),0,1000000)
            for field in ('alive','body_present','body_dynamic','body_active','velocity_sampled','bone_available','death_processed'):
                if type(sample.get(field)) is not bool: raise ValueError('invalid observed flag')
            if (sample['body_dynamic'] or sample['body_active'] or sample['velocity_sampled']) and not sample['body_present']:
                raise ValueError('body telemetry without a body')
            if type(sample.get('animation_uuid')) is not int: raise ValueError('missing native animation telemetry')
            for field in ('position','velocity','spine'):
                vector=sample.get(field)
                if type(vector) is not list or len(vector)!=3: raise ValueError('invalid vector sample')
                for component in vector: _number(component,-1000000,1000000)
        if samples[0]['alive'] is not True or samples[0]['health']<=0:
            raise ValueError('no live spawn control observation')
        if samples[-1]['alive'] is not False or samples[-1]['health']!=0 or previous<manifest['seconds_per_case']:
            raise ValueError('missing death observation/window')
    return {'authoritative_observations_complete':True,'visual_acceptance':False,
            'replication_acceptance':False,'feature_complete':False,'runtime_acceptance':'pending',
            'receipt_sha256':_sha(_read(path,MAX_JSON_BYTES)),'run_id':manifest['run_id']}


HOOK=r'''

// Disposable diagnostic mission only. No production class overrides.
#ifdef DIAG_DEVELOPER
class HCDeathSample
{
    float elapsed_seconds;
    bool alive;
    float health;
    bool body_present;
    bool body_dynamic;
    bool body_active;
    bool velocity_sampled;
    ref array<float> position;
    ref array<float> velocity;
    bool bone_available;
    ref array<float> spine;
    int animation_uuid;
    bool death_processed;
}

class HCDeathCase
{
    string name;
    int index;
    bool spawned;
    bool command_requested;
    bool impulse_requested;
    bool impulse_applied;
    bool dead_observed;
    bool cleanup_requested;
    bool cleanup_confirmed;
    ref array<ref HCDeathSample> samples = new array<ref HCDeathSample>();
}

class HCDeathReceipt
{
    int schema = 1;
    string kind = "native-infected-death-observations";
    string run_id = "@RUN@";
    string world;
    string engine_version;
    bool server_context;
    bool allow_observers = @OBSERVERS@;
    int max_observed_clients;
    bool complete;
    bool failed;
    string reason;
    int frames;
    int heartbeat_count;
    ref array<ref HCDeathCase> cases = new array<ref HCDeathCase>();
    bool render_observed = false;
    bool replication_observed = false;
}
#endif

class HCInfectedDeathProbeMission : CustomMission
{
#ifdef DIAG_DEVELOPER
    protected ref HCDeathReceipt m_Receipt;
    protected ref HCDeathCase m_Case;
    protected Object m_Owned;
    protected ZombieBase m_Zombie;
    protected int m_Index;
    protected int m_Phase;
    protected bool m_Done;
    protected float m_Started;
    protected float m_CaseStarted;
    protected float m_CleanupStarted;
    protected float m_LastTick;
    protected float m_LastSample;
    protected float m_LastHeartbeat;
    protected float m_NextFrameTick;
#endif

    override void OnInit()
    {
        super.OnInit();
#ifdef DIAG_DEVELOPER
        m_Receipt = new HCDeathReceipt;
        m_Receipt.server_context = GetGame().IsServer();
        GetGame().GetWorldName(m_Receipt.world);
        GetGame().GetVersion(m_Receipt.engine_version);
        m_Started = GetGame().GetTickTime();
        m_LastTick = m_Started;
        if (FileExist("$profile:hc-infected-death-result.json"))
        {
            m_Done = true;
            Print("[HC Infected Death] FAIL stale receipt; fresh external profile required");
            return;
        }
        Print("[HC Infected Death] BEGIN run=@RUN@ authoritative-only render=unobserved");
        // First spawn/sample is synchronous; no Mission.OnUpdate prerequisite.
        HCDeathTick();
        if (!m_Done)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCDeathTick, 100, true);
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCDeathFrame);
        }
#else
        Print("[HC Infected Death] FAIL DIAG_DEVELOPER required; no actors created");
#endif
    }

    override void OnMissionFinish()
    {
#ifdef DIAG_DEVELOPER
        HCDeathDetach();
        if (!m_Done && m_Receipt)
        {
            m_Receipt.failed = true;
            m_Receipt.complete = false;
            m_Receipt.reason = "mission-finished-before-completion";
            if (m_Case)
                m_Case.cleanup_requested = true;
            if (m_Owned)
                GetGame().ObjectDelete(m_Owned);
            // Shutdown is NOT an observed deletion confirmation.
            HCDeathSave();
        }
#endif
        super.OnMissionFinish();
    }

#ifdef DIAG_DEVELOPER
    void HCDeathDetach()
    {
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCDeathTick);
        GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCDeathFrame);
    }

    bool HCDeathSave()
    {
        string error;
        if (!JsonFileLoader<HCDeathReceipt>.SaveFile("$profile:hc-infected-death-result.json", m_Receipt, error))
        {
            m_Receipt.failed = true;
            m_Receipt.complete = false;
            m_Receipt.reason = "receipt-write-failed";
            return false;
        }
        return true;
    }

    void HCDeathFinish()
    {
        if (m_Done)
            return;
        m_Done = true;
        HCDeathDetach();
        m_Receipt.complete = !m_Receipt.failed && m_Receipt.cases.Count() == 5 && !m_Owned;
        bool saved = HCDeathSave();
        if (saved && m_Receipt.complete)
            Print("[HC Infected Death] COMPLETE run=@RUN@ authoritative-only render=unobserved");
        else
            Print("[HC Infected Death] FAIL run=@RUN@ reason=" + m_Receipt.reason);
    }

    array<float> HCDeathVector(vector value)
    {
        array<float> result = new array<float>();
        result.Insert(value[0]);
        result.Insert(value[1]);
        result.Insert(value[2]);
        return result;
    }

    void HCDeathSampleNow(float now)
    {
        if (!m_Zombie || !m_Case)
            return;
        if (m_Case.samples.Count() >= 32)
        {
            HCDeathCleanup("sample-budget");
            return;
        }
        HCDeathSample row = new HCDeathSample;
        row.elapsed_seconds = now - m_CaseStarted;
        row.alive = m_Zombie.IsAlive();
        row.health = m_Zombie.GetHealth("", "Health");
        row.position = HCDeathVector(m_Zombie.GetPosition());
        row.velocity = HCDeathVector(vector.Zero);
        row.spine = HCDeathVector(vector.Zero);
        row.animation_uuid = m_Zombie.GetCurrentAnimationInstanceUUID();
        row.death_processed = m_Zombie.IsDeathProcessed();
        row.body_present = dBodyIsSet(m_Zombie);
        if (row.body_present)
        {
            row.body_dynamic = dBodyIsDynamic(m_Zombie);
            row.body_active = dBodyIsActive(m_Zombie);
            row.velocity = HCDeathVector(GetVelocity(m_Zombie));
            row.velocity_sampled = true;
        }
        int bone = m_Zombie.GetBoneIndexByName("spine3");
        if (bone >= 0)
        {
            row.spine = HCDeathVector(m_Zombie.GetBonePositionWS(bone));
            row.bone_available = true;
        }
        if (!row.alive && row.health == 0)
            m_Case.dead_observed = true;
        m_Case.samples.Insert(row);
        m_LastSample = now;
    }

    void HCDeathStartCase(float now)
    {
        if (m_Owned || m_Index < 0 || m_Index >= 5)
        {
            HCDeathCleanup("actor-ownership-or-case-bound");
            return;
        }
        m_Case = new HCDeathCase;
        m_Case.index = m_Index;
        if (m_Index == 0) m_Case.name = "health-only";
        if (m_Index == 1) m_Case.name = "default-command";
        if (m_Index == 2) m_Case.name = "impulse-command";
        if (m_Index == 3) m_Case.name = "backstab-command";
        if (m_Index == 4) m_Case.name = "neckstab-command";
        m_Receipt.cases.Insert(m_Case);
        m_CaseStarted = now;
        vector position = "@X@ 0 @Z@";
        float worldSize = GetGame().GetWorld().GetWorldSize();
        if (position[0] >= worldSize || position[2] >= worldSize)
        {
            HCDeathCleanup("spawn-outside-actual-world");
            return;
        }
        position[1] = GetGame().SurfaceY(position[0], position[2]);
        if (!GetGame().ConfigIsExisting("CfgVehicles ZmbF_JournalistNormal_Blue"))
        {
            HCDeathCleanup("native-class-unavailable");
            return;
        }
        m_Owned = GetGame().CreateObjectEx("ZmbF_JournalistNormal_Blue", position, ECE_PLACE_ON_SURFACE|ECE_INITAI);
        m_Zombie = ZombieBase.Cast(m_Owned);
        if (!m_Zombie || !m_Zombie.IsAlive())
        {
            HCDeathCleanup("live-infected-spawn-failed");
            return;
        }
        m_Case.spawned = true;
        HCDeathSampleNow(now);
        int animation = DayZInfectedDeathAnims.ANIM_DEATH_DEFAULT;
        if (m_Index == 2) animation = DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;
        if (m_Index == 3) animation = DayZInfectedDeathAnims.ANIM_DEATH_BACKSTAB;
        if (m_Index == 4) animation = DayZInfectedDeathAnims.ANIM_DEATH_NECKSTAB;
        m_Zombie.m_DeathType = animation;
        m_Zombie.m_DamageHitDirection = 0;
        m_Zombie.SetHealth("", "Health", 0);
        if (m_Index > 0)
        {
            m_Case.command_requested = true;
            m_Zombie.StartCommand_Death(animation, 0);
        }
        vector impulse = "@IMPULSE@";
        if (m_Index == 2 && impulse.Length() > 0)
        {
            m_Case.impulse_requested = true;
            if (dBodyIsSet(m_Zombie) && dBodyIsDynamic(m_Zombie))
            {
                dBodyApplyImpulse(m_Zombie, impulse);
                m_Case.impulse_applied = true;
            }
        }
        m_Phase = 1;
        HCDeathSampleNow(now);
        Print("[HC Infected Death] CASE run=@RUN@ method=" + m_Case.name + " impulse_applied=" + m_Case.impulse_applied);
        if (!HCDeathSave())
            HCDeathCleanup("receipt-write-failed");
    }

    void HCDeathCleanup(string reason)
    {
        if (reason != "")
        {
            m_Receipt.failed = true;
            if (m_Receipt.reason == "") m_Receipt.reason = reason;
        }
        if (m_Phase != 2)
        {
            m_Phase = 2;
            m_CleanupStarted = GetGame().GetTickTime();
            if (m_Case) m_Case.cleanup_requested = true;
            if (m_Owned) GetGame().ObjectDelete(m_Owned);
        }
    }

    void HCDeathFrame(float timeslice)
    {
        if (m_Done)
            return;
        m_Receipt.frames++;
        float now = GetGame().GetTickTime();
        if (m_Receipt.frames > 20000)
            HCDeathCleanup("frame-budget");
        if (m_Receipt.heartbeat_count < 20)
        {
            if (m_Receipt.frames <= 3 || now - m_LastHeartbeat >= 1)
            {
                m_Receipt.heartbeat_count++;
                m_LastHeartbeat = now;
                Print("[HC Infected Death] HEARTBEAT run=@RUN@ engine_seconds=" + now + " frames=" + m_Receipt.frames);
            }
        }
        if (now < m_LastTick || now >= m_NextFrameTick)
        {
            m_NextFrameTick = now + 0.25;
            HCDeathTick();
        }
    }

    void HCDeathTick()
    {
        if (m_Done)
            return;
        float now = GetGame().GetTickTime();
        if (!m_Receipt.server_context)
            HCDeathCleanup("server-context-required");
        array<PlayerIdentity> identities = new array<PlayerIdentity>();
        GetGame().GetPlayerIndentities(identities);
        if (identities.Count() > m_Receipt.max_observed_clients)
            m_Receipt.max_observed_clients = identities.Count();
        if ((!m_Receipt.allow_observers && identities.Count() > 0) || identities.Count() > 90)
            HCDeathCleanup("unexpected-connected-clients");
        if (!(now >= 0) || now < m_LastTick || now - m_Started > 60)
            HCDeathCleanup("clock-rollback-or-internal-deadline");
        m_LastTick = now;
        if (m_Phase == 0)
            HCDeathStartCase(now);
        if (m_Phase == 1)
        {
            if (!m_Zombie)
                HCDeathCleanup("actor-disappeared-before-owned-cleanup");
            else if (now - m_LastSample >= 0.25 || now - m_CaseStarted >= @SECONDS@)
            {
                HCDeathSampleNow(now);
                if (m_Phase == 1 && now - m_CaseStarted >= @SECONDS@)
                {
                    if (!m_Case.dead_observed)
                        HCDeathCleanup("death-not-observed");
                    else
                        HCDeathCleanup("");
                }
                if (!HCDeathSave()) HCDeathCleanup("receipt-write-failed");
            }
        }
        if (m_Phase == 2)
        {
            if (!m_Owned)
            {
                if (m_Case) m_Case.cleanup_confirmed = !m_Owned;
                if (m_Receipt.failed || m_Index == 4)
                    HCDeathFinish();
                else
                {
                    m_Index++;
                    m_Phase = 0;
                    HCDeathStartCase(now);
                }
            }
            else if (now - m_CleanupStarted > 2)
            {
                m_Receipt.failed = true;
                m_Receipt.reason = "owned-deletion-unconfirmed";
                HCDeathFinish();
            }
        }
    }
#endif
}
'''


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    prepare=commands.add_parser('prepare')
    for name in ('source','out','scripts'): prepare.add_argument('--'+name,type=Path,required=True)
    prepare.add_argument('--x',type=float,required=True);prepare.add_argument('--z',type=float,required=True)
    prepare.add_argument('--seconds-per-case',type=int,default=2)
    prepare.add_argument('--impulse',nargs=3,type=float,default=(0,0,0))
    prepare.add_argument('--allow-observers',action='store_true')
    check=commands.add_parser('validate')
    check.add_argument('--receipt',type=Path,required=True);check.add_argument('--mission',type=Path,required=True)
    check.add_argument('--outer-outcome',choices=('finished','timed-out'),required=True)
    args=parser.parse_args(argv)
    try:
        if args.command=='prepare':
            result=prepare_probe(args.source,args.out,args.scripts,x=args.x,z=args.z,
                seconds_per_case=args.seconds_per_case,impulse=args.impulse,allow_observers=args.allow_observers)
            print(json.dumps({'run_id':result['run_id'],'runtime_acceptance':'pending','outer_timeout_required':True}))
        else:
            print(json.dumps(validate_result(args.receipt,args.mission,outer_timed_out=args.outer_outcome=='timed-out')))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        parser.exit(2,'Infected death probe refused: '+str(exc)+'\n')


if __name__=='__main__':
    raise SystemExit(main())
