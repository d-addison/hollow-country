"""Prepare disposable diagnostic harness or direct-actor missions; never launch DayZ.

The generated server adapter starts the installed AutotestRunner synchronously
and ticks it on the SYSTEM queue; the stock -autotest tick is in MissionGameplay.
Two registered
native cases must execute. Null-identity actor creation/controller movement are
experiments, not guaranteed capabilities or clients. All game files stay external.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

from tools.setup import diagnostic_mission as staging

SUITE = "HCNativeAutotestSuite"
CASES = ("HCNativeServerContext", "HCNativeActorMovement")
MARKER = ".hc-native-autotest.json"
MAX_INTERFACE_BYTES = 1024 * 1024
MAX_XML_BYTES = 2 * 1024 * 1024
INTERFACES = {
    "2_GameLib/tests/TestingFramework.c": (
        "class TestHarness", "class TestSuite", "class TestBase", "class Step",
        "GetNSuites()", "GetNTests()", "GetResult()", "timeoutS", "TearDown"),
    "2_GameLib/tools.c": ("class ScriptCallQueue", "CallLater", "Remove"),
    "3_Game/Autotest/AutotestRunner.c": (
        "class AutotestRunner", "TestHarness.Begin()", "TestHarness.Run()",
        "TestHarness.End()", "class CustomResult"),
    "3_Game/Autotest/AutotestConfigJson.c": ("class AutotestConfigJson", "TestSuites"),
    "3_Game/Autotest/AutotestConfigHandler.c": ("class AutotestConfigHandler", "LoadData(string path)"),
    "3_Game/Autotest/AutoTestFixture.c": ("SaveXMLReport", "$mission:Autotest_%1.xml"),
    "3_Game/human.c": ("OverrideMovementSpeed", "OverrideMovementAngle", "GetInputController()", "StartCommand_Move()"),
    "3_Game/Global/Game.c": ("CreatePlayer(PlayerIdentity identity", "SurfaceY(float x", "ObjectDelete(", "GetTime()"),
    "3_Game/Systems/Inventory/HumanInventory.c": ("CreateInHands(string typeName)",),
    "3_Game/Entities/EntityAI.c": ("GetHierarchyRootPlayer()",),
    "5_Mission/mission/missionServer.c": ("override void OnUpdate(float timeslice)",),
    "3_Game/DayZGame.c": ("if (doSim && mission)", "GetCallQueue(CALL_CATEGORY_SYSTEM).Tick(timeslice)"),
}

HOOK = r'''

// Disposable HC native TestHarness experiment, not a connected player or AI acceptance.
#ifdef DIAG_DEVELOPER
class HCNativeAutotestState
{
    static PlayerBase Actor;
    static EntityAI Item;
    static bool ContextPassed;
    static bool ActorPassed;

    static void Cleanup()
    {
        if (Actor)
        {
            HumanInputController input = Actor.GetInputController();
            if (input)
            {
                input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
                input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
            }
        }
        if (Item)
            GetGame().ObjectDelete(Item);
        Item = null;
        if (Actor)
            GetGame().ObjectDelete(Actor);
        Actor = null;
        Print("[HC Native Autotest] owned actor/item cleanup requested");
    }
}

class HCNativeAutotestSuite : TestSuite {}

[Test("HCNativeAutotestSuite", 5, 0, 0)]
class HCNativeServerContext : TestBase
{
    [Step(EStage.Main)]
    void CheckContext()
    {
        if (!GetGame().IsServer())
        {
            SetResult(new CustomResult(false, "Diagnostic server required"));
            return;
        }
        array<Man> connected = new array<Man>();
        GetGame().GetPlayers(connected);
        if (connected.Count() != 0)
        {
            SetResult(new CustomResult(false, "Fresh zero-player runtime required"));
            return;
        }
        HCNativeAutotestState.ContextPassed = true;
        Print("[HC Native Autotest] server context assertion PASS; real_clients=0");
        SetResult(new CustomResult(true));
    }
}

[Test("HCNativeAutotestSuite", 12, 0, 1)]
class HCNativeActorMovement : TestBase
{
    protected int m_Phase;
    protected int m_Started;
    protected vector m_Start;

    // Main-stage failures unwind TearDown; Setup failures would not.
    [Step(EStage.Main)]
    void SpawnOwnedActor()
    {
        if (!HCNativeAutotestState.ContextPassed)
        {
            SetResult(new CustomResult(false, "Context case did not pass"));
            return;
        }
        vector position = Vector(@X@, 0, @Z@);
        position[1] = GetGame().SurfaceY(position[0], position[2]) + 0.2;
        HCNativeAutotestState.Actor = PlayerBase.Cast(GetGame().CreatePlayer(null, "SurvivorM_Mirek", position, 0, "NONE"));
        if (!HCNativeAutotestState.Actor)
        {
            SetResult(new CustomResult(false, "Null-identity CreatePlayer unsupported or failed"));
            return;
        }
        if (HCNativeAutotestState.Actor.GetIdentity())
        {
            SetResult(new CustomResult(false, "Unexpected network identity on owned actor"));
            return;
        }
        HCNativeAutotestState.Item = HCNativeAutotestState.Actor.GetHumanInventory().CreateInHands("Rag");
        if (!HCNativeAutotestState.Item)
        {
            SetResult(new CustomResult(false, "Native inventory CreateInHands failed"));
            return;
        }
        if (HCNativeAutotestState.Item.GetHierarchyRootPlayer() != HCNativeAutotestState.Actor)
        {
            SetResult(new CustomResult(false, "Native item ownership assertion failed"));
            return;
        }
        Print("[HC Native Autotest] native actor and owned inventory item created");
        m_Started = GetGame().GetTime();
    }

    [Step(EStage.Main)]
    bool MeasureNativeMovement()
    {
        PlayerBase actor = HCNativeAutotestState.Actor;
        if (!actor || !actor.IsAlive())
        {
            SetResult(new CustomResult(false, "Owned actor missing or dead"));
            return true;
        }
        HumanInputController input = actor.GetInputController();
        if (!input)
        {
            SetResult(new CustomResult(false, "Native input controller unavailable"));
            return true;
        }
        int elapsed = GetGame().GetTime() - m_Started;
        if (elapsed < 0)
        {
            SetResult(new CustomResult(false, "Clock discontinuity"));
            return true;
        }
        if (m_Phase == 0)
        {
            if (elapsed < 1000)
                return false;
            if (!actor.GetCommand_Move())
                actor.StartCommand_Move();
            m_Start = actor.GetPosition();
            input.OverrideMovementAngle(HumanInputControllerOverrideType.ENABLED, 0);
            input.OverrideMovementSpeed(HumanInputControllerOverrideType.ENABLED, 1);
            m_Started = GetGame().GetTime();
            m_Phase = 1;
            return false;
        }
        if (elapsed < @DURATION_MS@)
            return false;
        input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
        input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
        vector delta = actor.GetPosition() - m_Start;
        float distance = Math.Sqrt(delta[0] * delta[0] + delta[2] * delta[2]);
        float vertical = Math.AbsFloat(delta[1]);
        Print("[HC Native Autotest] measured planar_m=" + distance + " vertical_m=" + vertical + " elapsed_ms=" + elapsed);
        if (distance < 0.5 || distance > 20 || vertical > 2)
        {
            SetResult(new CustomResult(false, "Native walking displacement/grounding assertion failed"));
            return true;
        }
        HCNativeAutotestState.ActorPassed = true;
        Print("[HC Native Autotest] actor inventory and physical movement assertion PASS");
        SetResult(new CustomResult(true));
        return true;
    }

    [Step(EStage.TearDown)]
    void RemoveOwnedObjects()
    {
        HCNativeAutotestState.Cleanup();
    }
}
#endif

class HCNativeAutotestMission : CustomMission
{
    protected int m_HCStarted;
    protected bool m_HCRunning;
    protected bool m_HCDone;

    override void OnInit()
    {
        super.OnInit();
#ifdef DIAG_DEVELOPER
        m_HCStarted = GetGame().GetTime();
        if (!GetGame().IsServer())
        {
            Print("[HC Native Autotest] FAIL diagnostic server required");
            GetGame().RequestExit(1);
            return;
        }
        if (!AutotestConfigHandler.LoadData("$mission:hc-autotest.json"))
        {
            Print("[HC Native Autotest] FAIL native config load");
            GetGame().RequestExit(1);
            return;
        }
        int selected;
        int count = TestHarness.GetNSuites();
        Print("[HC Native Autotest] registration suites=" + count);
        for (int i = 0; i < count; i++)
        {
            TestSuite suite = TestHarness.GetSuite(i);
            Print("[HC Native Autotest] suite index=" + i + " name=" + suite.GetName() + " cases=" + suite.GetNTests());
            if (suite.GetName() == "HCNativeAutotestSuite")
            {
                selected++;
                if (suite.GetNTests() != 2)
                {
                    Print("[HC Native Autotest] FAIL exact registered case count");
                    GetGame().RequestExit(1);
                    return;
                }
                suite.SetEnabled(true);
            }
            else
                suite.SetEnabled(false);
        }
        if (selected != 1)
        {
            Print("[HC Native Autotest] FAIL no exact registered native suite");
            GetGame().RequestExit(1);
            return;
        }
        Print("[HC Native Autotest] BEGIN registered_suites=1 registered_cases=2 real_clients=0");
        m_HCRunning = true;
        HCAutotestTick();
        if (!m_HCDone)
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCAutotestTick, 100, true);
#else
        Print("[HC Native Autotest] FAIL DIAG_DEVELOPER required");
        GetGame().RequestExit(1);
#endif
    }

    void HCAutotestTick()
    {
#ifdef DIAG_DEVELOPER
        if (!m_HCRunning || m_HCDone)
            return;
        int elapsed = GetGame().GetTime() - m_HCStarted;
        if (elapsed < 0 || elapsed > 45000)
        {
            m_HCDone = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCAutotestTick);
            HCNativeAutotestState.Cleanup();
            Print("[HC Native Autotest] FAIL native watchdog");
            GetGame().RequestExit(1);
            return;
        }
        if (!AutotestRunner.IsRunning() && !AutotestRunner.IsDone())
            AutotestRunner.Start();
        AutotestRunner.Update(0.1);
        if (AutotestRunner.IsDone())
        {
            m_HCDone = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCAutotestTick);
            bool passed = HCNativeAutotestState.ContextPassed && HCNativeAutotestState.ActorPassed;
            for (int i = 0; i < TestHarness.GetNSuites(); i++)
            {
                TestSuite suite = TestHarness.GetSuite(i);
                if (suite.GetName() != "HCNativeAutotestSuite")
                    continue;
                for (int j = 0; j < suite.GetNTests(); j++)
                {
                    TestResultBase result = suite.GetTest(j).GetResult();
                    if (!result || result.Failure())
                        passed = false;
                }
            }
            HCNativeAutotestState.Cleanup();
            if (passed)
            {
                Print("[HC Native Autotest] PASS; XML and logs still require verification");
                GetGame().RequestExit(0);
            }
            else
            {
                Print("[HC Native Autotest] FAIL native assertions");
                GetGame().RequestExit(1);
            }
        }
#endif
    }
}
'''

DIRECT_INTERFACES = {
    "3_Game/tools/JsonFileLoader.c": ("class JsonFileLoader<Class T>", "static bool SaveFile("),
    "3_Game/Global/Game.c": ("GetTickTime()", "GetUpdateQueue(int call_category)"),
    "3_Game/DayZGame.c": ("GetUpdateQueue(CALL_CATEGORY_SYSTEM).Invoke(timeslice)",),
    "3_Game/Hive/Hive.c": ("IsIdleMode()", "proto native Hive GetHive()"),
}

# A separate authored runner. No native test registration or TestBase results.
DIRECT_HOOK = r'''

// Disposable direct native actor experiment; no connected client or AI acceptance.
#ifdef DIAG_DEVELOPER
class HCNativeActorReceipt
{
    int schema = 1;
    string kind = "native-diagnostic-direct-actor";
    int real_clients;
    bool passed;
    bool server_context;
    bool no_clients;
    bool actor_spawned;
    bool inventory_owned;
    bool controller_requested;
    bool movement_passed;
    bool cleanup_requested;
    bool cleanup_confirmed;
    float planar_m;
    float vertical_m;
    int elapsed_ms;
    string reason;
    int system_frames;
    int heartbeat_count;
    int mission_ms;
    float engine_seconds;
    float last_timeslice;
    bool economy_idle;
}
#endif

class HCNativeAutotestMission : CustomMission
{
#ifdef DIAG_DEVELOPER
    protected ref HCNativeActorReceipt m_Receipt;
    protected PlayerBase m_Actor;
    protected EntityAI m_Item;
    protected int m_Started;
    protected int m_PhaseStarted;
    protected int m_Phase;
    protected vector m_Start;
    protected bool m_Done;
    protected float m_LastHeartbeat;
    protected float m_NextFrameTick;
#endif

    override void OnInit()
    {
        super.OnInit();
#ifdef DIAG_DEVELOPER
        m_Receipt = new HCNativeActorReceipt();
        m_Started = GetGame().GetTickTime() * 1000;
        m_PhaseStarted = m_Started;
        Print("[HC Native Actor] BEGIN authored_direct_runner real_clients=0");
        HCActorInitialize();
        HCActorTick();
        if (!m_Done)
        {
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCActorTick, 100, true);
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Insert(HCActorFrame);
        }
#else
        Print("[HC Native Actor] FAIL DIAG_DEVELOPER required");
        GetGame().RequestExit(1);
#endif
    }

#ifdef DIAG_DEVELOPER
    void HCActorFrame(float timeslice)
    {
        if (m_Done)
            return;
        m_Receipt.system_frames++;
        m_Receipt.last_timeslice = timeslice;
        m_Receipt.mission_ms = GetGame().GetTime();
        float now = GetGame().GetTickTime();
        m_Receipt.engine_seconds = now;
        Hive hive = GetHive();
        if (hive)
            m_Receipt.economy_idle = hive.IsIdleMode();
        // First frames expose zero dt/frozen clocks; cap all heartbeat output.
        if (m_Receipt.heartbeat_count < 20 && (m_Receipt.system_frames <= 3 || now - m_LastHeartbeat >= 1))
        {
            Print("[HC Native Actor] frame=" + m_Receipt.system_frames + " mission_ms=" + m_Receipt.mission_ms + " engine_s=" + now + " dt=" + timeslice + " idle=" + m_Receipt.economy_idle);
            m_Receipt.heartbeat_count++;
            m_LastHeartbeat = now;
        }
        // This invoker does not wait for CallLater's timeslice accumulator.
        if (now >= m_NextFrameTick)
        {
            m_NextFrameTick = now + 0.1;
            HCActorTick();
        }
    }

    void HCActorInitialize()
    {
        m_Receipt.server_context = GetGame().IsServer();
        if (!m_Receipt.server_context)
        {
            HCActorCleanup("Diagnostic server required");
            return;
        }
        array<Man> players = new array<Man>();
        GetGame().GetPlayers(players);
        m_Receipt.real_clients = players.Count();
        m_Receipt.no_clients = players.Count() == 0;
        if (!m_Receipt.no_clients)
        {
            HCActorCleanup("Fresh zero-player runtime required");
            return;
        }
        vector position = Vector(@X@, 0, @Z@);
        position[1] = GetGame().SurfaceY(position[0], position[2]) + 0.2;
        m_Actor = PlayerBase.Cast(GetGame().CreatePlayer(null, "SurvivorM_Mirek", position, 0, "NONE"));
        if (!m_Actor || m_Actor.GetIdentity())
        {
            HCActorCleanup("Null-identity native actor unavailable");
            return;
        }
        m_Receipt.actor_spawned = true;
        Print("[HC Native Actor] assertion actor_spawned=true");
        m_Item = m_Actor.GetHumanInventory().CreateInHands("Rag");
        if (!m_Item || m_Item.GetHierarchyRootPlayer() != m_Actor)
        {
            HCActorCleanup("Native inventory ownership failed");
            return;
        }
        m_Receipt.inventory_owned = true;
        Print("[HC Native Actor] assertion inventory_owned=true");
    }

    void HCActorCleanup(string reason)
    {
        if (m_Receipt.cleanup_requested)
            return;
        m_Receipt.reason = reason;
        m_Receipt.cleanup_requested = true;
        if (m_Actor)
        {
            HumanInputController input = m_Actor.GetInputController();
            if (input)
            {
                input.OverrideMovementSpeed(HumanInputControllerOverrideType.DISABLED, 0);
                input.OverrideMovementAngle(HumanInputControllerOverrideType.DISABLED, 0);
            }
        }
        if (m_Item)
            GetGame().ObjectDelete(m_Item);
        if (m_Actor)
            GetGame().ObjectDelete(m_Actor);
        // Retain references until engine deletion invalidates them; no forced null.
        m_Phase = 2;
        m_PhaseStarted = GetGame().GetTickTime() * 1000;
        Print("[HC Native Actor] owned actor/item cleanup requested reason=" + reason);
    }

    void HCActorTick()
    {
        if (m_Done)
            return;
        int now = GetGame().GetTickTime() * 1000;
        int elapsed = now - m_PhaseStarted;
        if (m_Phase == 2)
        {
            m_Receipt.cleanup_confirmed = !m_Item && !m_Actor;
            if (!m_Receipt.cleanup_confirmed && elapsed >= 0 && elapsed < 2000)
                return;
            m_Done = true;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).Remove(HCActorTick);
            GetGame().GetUpdateQueue(CALL_CATEGORY_SYSTEM).Remove(HCActorFrame);
            m_Receipt.passed = m_Receipt.server_context && m_Receipt.no_clients && m_Receipt.actor_spawned && m_Receipt.inventory_owned && m_Receipt.controller_requested && m_Receipt.movement_passed && m_Receipt.cleanup_confirmed && m_Receipt.reason == "";
            string error;
            bool saved = JsonFileLoader<HCNativeActorReceipt>.SaveFile("$mission:hc-native-actor-result.json", m_Receipt, error);
            if (m_Receipt.passed && saved)
            {
                Print("[HC Native Actor] PASS authored assertions; not native harness acceptance");
                GetGame().RequestExit(0);
            }
            else
            {
                Print("[HC Native Actor] FAIL reason=" + m_Receipt.reason + " cleanup_confirmed=" + m_Receipt.cleanup_confirmed + " receipt_saved=" + saved);
                GetGame().RequestExit(1);
            }
            return;
        }
        int total = now - m_Started;
        if (elapsed < 0 || total < 0 || total > 15000)
        {
            HCActorCleanup("Native watchdog/clock failure");
            return;
        }
        if (!m_Actor || !m_Actor.IsAlive())
        {
            HCActorCleanup("Native actor absent or dead");
            return;
        }
        HumanInputController input = m_Actor.GetInputController();
        if (!input)
        {
            HCActorCleanup("Native controller unavailable");
            return;
        }
        if (m_Phase == 0)
        {
            if (elapsed < 1000)
                return;
            if (!m_Actor.GetCommand_Move())
                m_Actor.StartCommand_Move();
            m_Start = m_Actor.GetPosition();
            input.OverrideMovementAngle(HumanInputControllerOverrideType.ENABLED, 0);
            input.OverrideMovementSpeed(HumanInputControllerOverrideType.ENABLED, 1);
            m_Receipt.controller_requested = true;
            m_PhaseStarted = now;
            m_Phase = 1;
            Print("[HC Native Actor] controller movement requested");
            return;
        }
        if (elapsed < @DURATION_MS@)
            return;
        vector delta = m_Actor.GetPosition() - m_Start;
        m_Receipt.planar_m = Math.Sqrt(delta[0] * delta[0] + delta[2] * delta[2]);
        m_Receipt.vertical_m = Math.AbsFloat(delta[1]);
        m_Receipt.elapsed_ms = elapsed;
        Print("[HC Native Actor] measured planar_m=" + m_Receipt.planar_m + " vertical_m=" + m_Receipt.vertical_m + " elapsed_ms=" + elapsed);
        m_Receipt.movement_passed = m_Receipt.planar_m >= 0.5 && m_Receipt.planar_m <= 20 && m_Receipt.vertical_m <= 2;
        if (m_Receipt.movement_passed)
            HCActorCleanup("");
        else
            HCActorCleanup("Native walking displacement/grounding failed");
    }
#endif
}
'''


def _read(path, limit):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("linked input forbidden")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
        raise ValueError("bounded regular input required")
    with path.open("rb") as stream:
        data = stream.read(before.st_size + 1)
    if len(data) != before.st_size or staging._identity(path.stat()) != staging._identity(before):
        raise ValueError("input changed")
    return data


def inspect_interfaces(root, *, direct=False):
    root = Path(root)
    records = {}
    contracts = dict(INTERFACES)
    if direct:
        for relative, tokens in DIRECT_INTERFACES.items():
            contracts[relative] = contracts.get(relative, ()) + tokens
    for relative, tokens in contracts.items():
        try:
            data = _read(root / relative, MAX_INTERFACE_BYTES)
            text = " ".join(data.decode("utf-8-sig").split())
        except (OSError, UnicodeError) as exc:
            raise ValueError("required installed interface unavailable") from exc
        if any(" ".join(token.split()) not in text for token in tokens):
            raise ValueError("installed interface contract mismatch: " + relative)
        records[relative] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return records


def prepare_autotest(source, destination, scripts_root, *, x, z, duration=3, mode="harness"):
    """Copy stock-shaped external mission and append authored native tests.

    Caller owns actual Diag launch with -server -mission=<mission_path>, a fresh
    profile/BE path, unchanged PBO and outer process timeout <=90 seconds.
    Harness registration with/without -autotest remains an engine experiment. Coordinates
    are caller-selected experimental terrain, not validated building anchors.
    """
    if mode not in ("harness", "direct-actor"):
        raise ValueError("explicit harness or direct-actor mode required")
    direct = mode == "direct-actor"
    for coordinate in (x, z):
        if (type(coordinate) not in (int, float) or not math.isfinite(coordinate)
                or not 1 <= coordinate <= 15359):
            raise ValueError("finite ChernarusPlus interior coordinate required")
    if type(duration) is not int or not 1 <= duration <= 8:
        raise ValueError("integer movement duration 1..8 seconds required")
    source, destination = staging._safe_path(source), staging._safe_path(destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("overlapping missions forbidden")
    if destination.exists() or destination.is_symlink():
        raise ValueError("fresh destination required")
    interfaces = inspect_interfaces(scripts_root, direct=direct)
    files, directories, _ = staging._inventory(source)
    if any(name.name in {MARKER, "hc-autotest.json", "hc-native-actor-result.json"} or name.parts[0].startswith("storage_")
           for name, _ in files):
        raise ValueError("previous instrumentation or runtime state forbidden")
    original = _read(source / "init.c", staging.MAX_INIT_BYTES)
    if b"HCNativeAutotest" in original or b"HCDisposableDiagnosticMission" in original:
        raise ValueError("previous instrumentation forbidden")
    if len(re.findall(rb"class\s+CustomMission\s*:\s*MissionServer\b", original)) != 1:
        raise ValueError("stock MissionServer factory required")
    replaced, count = staging._FACTORY.subn(rb"\g<1>HCNativeAutotestMission\g<2>", original)
    if count != 1 or len(re.findall(rb"\bCreateCustomMission\s*\(", original)) != 1:
        raise ValueError("exact stock factory required")
    hook = (DIRECT_HOOK if direct else HOOK).replace("@X@", format(x, ".6f")).replace("@Z@", format(z, ".6f"))
    hook = hook.replace("@DURATION_MS@", str(duration * 1000)).encode("utf-8")
    configuration = {"mode": mode} if direct else {"TestSuites": [SUITE]}
    config = (json.dumps(configuration, sort_keys=True, indent=2) + "\n").encode()
    generated = {"init.c": replaced + hook, "hc-autotest.json": config}
    destination.mkdir(parents=True, exist_ok=False)
    for relative in directories:
        (destination / relative).mkdir(exist_ok=False)
    provenance = {"schema": 1, "kind": "native-diagnostic-direct-actor" if direct else "native-diagnostic-autotest", "suite": None if direct else SUITE,
                  "mode": mode, "cases": [] if direct else list(CASES), "real_clients": 0, "runtime_acceptance": "pending",
                  "mission_path": str(destination), "interfaces": interfaces, "files": {},
                  "spawn_xz": [x, z], "movement_seconds": duration, "watchdog_seconds": 17 if direct else 45,
                  "launch_options": ["-server", "-mission=" + str(destination)],
                  "limits": "single unconnected native actor; not two clients or gameplay acceptance"}
    for relative, info in files:
        src, dst = source / relative, destination / relative
        staging._unchanged(src, info)
        digest = hashlib.sha256()
        with src.open("rb") as stream, dst.open("xb") as output:
            remaining = info.st_size
            while remaining:
                data = stream.read(min(65536, remaining))
                if not data:
                    raise ValueError("source truncated")
                digest.update(data)
                if relative.as_posix() not in generated:
                    output.write(data)
                remaining -= len(data)
            if stream.read(1):
                raise ValueError("source grew")
            if relative.as_posix() in generated:
                output.write(generated[relative.as_posix()])
        staging._unchanged(src, info)
        provenance["files"][relative.as_posix()] = {"source_sha256": digest.hexdigest(),
            "staged_sha256": hashlib.sha256(generated[relative.as_posix()]).hexdigest()
            if relative.as_posix() in generated else digest.hexdigest()}
    with (destination / "hc-autotest.json").open("xb") as stream:
        stream.write(config)
    provenance["generated"] = {name: hashlib.sha256(data).hexdigest() for name, data in generated.items()}
    with (destination / MARKER).open("x", encoding="utf-8") as stream:
        json.dump(provenance, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return provenance


def verify_result(xml_path, bundle):
    """Admit exact nonempty native JUnit cases; no authenticity/network claims."""
    result = {"valid": False, "cases": 0, "multiplayer_acceptance": False,
              "runtime_acceptance": "pending", "errors": []}
    try:
        root = Path(bundle)
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate marker key")
                value[key] = item
            return value
        provenance = json.loads(_read(root / MARKER, MAX_XML_BYTES), object_pairs_hook=unique_object)
        if (type(provenance) is not dict or type(provenance.get("schema")) is not int
                or provenance.get("schema") != 1
                or provenance.get("kind") != "native-diagnostic-autotest"):
            raise ValueError("invalid bundle marker")
        generated = provenance.get("generated")
        if type(generated) is not dict or set(generated) != {"init.c", "hc-autotest.json"}:
            raise ValueError("invalid generated inputs")
        if any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in generated.values()):
            raise ValueError("invalid generated input digest")
        for name in ("init.c", "hc-autotest.json"):
            data = _read(root / name, 256 * 1024)
            if hashlib.sha256(data).hexdigest() != provenance["generated"].get(name):
                raise ValueError("generated input drift")
        data = _read(xml_path, MAX_XML_BYTES)
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = data.decode("utf-16")
        else:
            text = data.decode("utf-8-sig")
        if "\0" in text or "<!doctype" in text.lower() or "<!entity" in text.lower():
            raise ValueError("XML declarations forbidden")
        tree = ET.fromstring(text)
        suites = [node for node in tree.iter("testsuite") if node.get("name") == SUITE]
        cases = list(tree.iter("testcase"))
        if len(suites) != 1 or len(cases) != len(CASES):
            raise ValueError("exact nonempty suite/cases required")
        owned = list(suites[0].iter("testcase"))
        if sorted(c.get("name", "") for c in owned) != sorted(CASES):
            raise ValueError("case identity mismatch")
        if any(node.tag in {"failure", "error", "skipped"} for node in tree.iter()):
            raise ValueError("native assertion failed or skipped")
        for node in tree.iter():
            for attribute in ("failures", "errors", "skipped", "disabled"):
                if attribute in node.attrib and not re.fullmatch(r"0+", node.get(attribute)):
                    raise ValueError("failed native summary")
        for case in cases:
            if case.get("status", "run") not in {"run", "passed", "success", "completed"}:
                raise ValueError("unexecuted native case")
        result.update(valid=True, cases=len(cases), xml_sha256=hashlib.sha256(data).hexdigest())
    except (OSError, ValueError, KeyError, TypeError, RecursionError, ET.ParseError):
        result["errors"].append("native result or bound bundle rejected")
    return result


def verify_direct_result(receipt_path, bundle):
    """Structurally admit authored actor evidence; never TestHarness/run proof."""
    result = {"valid": False, "testharness_acceptance": False,
              "multiplayer_acceptance": False, "runtime_acceptance": "pending", "errors": []}
    try:
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON key")
                value[key] = item
            return value
        root = Path(bundle)
        marker = json.loads(_read(root / MARKER, MAX_XML_BYTES), object_pairs_hook=unique_object)
        if (type(marker) is not dict or type(marker.get("schema")) is not int
                or marker.get("schema") != 1 or marker.get("kind") != "native-diagnostic-direct-actor"
                or marker.get("mode") != "direct-actor"):
            raise ValueError("wrong direct bundle")
        duration = marker.get("movement_seconds")
        if type(duration) is not int or not 1 <= duration <= 8:
            raise ValueError("invalid movement duration")
        generated = marker.get("generated")
        if type(generated) is not dict or set(generated) != {"init.c", "hc-autotest.json"}:
            raise ValueError("invalid generated inputs")
        for name, digest in generated.items():
            if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid digest")
            if hashlib.sha256(_read(root / name, 256 * 1024)).hexdigest() != digest:
                raise ValueError("direct input drift")
        data = _read(receipt_path, 16384)
        receipt = json.loads(data, object_pairs_hook=unique_object)
        if (type(receipt) is not dict or type(receipt.get("schema")) is not int
                or receipt.get("schema") != 1 or receipt.get("kind") != marker["kind"]
                or type(receipt.get("real_clients")) is not int or receipt["real_clients"] != 0
                or receipt.get("reason") != ""):
            raise ValueError("wrong receipt context")
        for flag in ("passed", "server_context", "no_clients", "actor_spawned", "inventory_owned",
                     "controller_requested", "movement_passed", "cleanup_requested", "cleanup_confirmed"):
            if receipt.get(flag) is not True:
                raise ValueError("failed/unobserved native assertion")
        for metric, low, high in (("planar_m", 0.5, 20), ("vertical_m", 0, 2)):
            value = receipt.get(metric)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("invalid native motion")
        elapsed = receipt.get("elapsed_ms")
        if type(elapsed) is not int or not duration * 1000 <= elapsed <= 15000:
            raise ValueError("invalid native duration")
        result.update(valid=True, receipt_sha256=hashlib.sha256(data).hexdigest())
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        result["errors"].append("authored actor receipt or bound bundle rejected")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    for name in ("source", "out", "scripts"):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--x", type=float, required=True)
    prepare.add_argument("--z", type=float, required=True)
    prepare.add_argument("--duration", type=int, default=3)
    prepare.add_argument("--mode", choices=("harness", "direct-actor"), default="harness")
    verify = sub.add_parser("verify")
    verify.add_argument("--xml", type=Path, required=True)
    verify.add_argument("--bundle", type=Path, required=True)
    direct = sub.add_parser("verify-direct")
    direct.add_argument("--receipt", type=Path, required=True)
    direct.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_autotest(args.source, args.out, args.scripts, x=args.x, z=args.z, duration=args.duration, mode=args.mode)
        elif args.command == "verify-direct":
            result = verify_direct_result(args.receipt, args.bundle)
        else:
            result = verify_result(args.xml, args.bundle)
    except (OSError, ValueError):
        result = {"valid": False, "errors": ["preparation refused; preserve any partial output"]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return int(result.get("valid") is False)


if __name__ == "__main__":
    raise SystemExit(main())
