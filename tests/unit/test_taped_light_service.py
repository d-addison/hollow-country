"""Synthetic collaborators; not native gameplay or host/slot qualification."""
import copy
import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from tests.unit.build_identity_support import translate as build_identity
from tests.unit.test_group_server import EArray, body, translated_rules

ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts"


def service_rules():
    adapter = inspect.getsource(translated_rules)
    for old, new in (
        ("3_Game/Groups/HCGroupData.c", "3_Game/Survival/HCTapedLightData.c"),
        ("3_Game/Groups/HCGroupProtocol.c", "3_Game/Survival/HCTapedLightData.c"),
        ("4_World/Groups/HCGroupRules.c", "4_World/Survival/HCTapedLightService.c"),
    ):
        adapter = adapter.replace(old, new)
    adapter = adapter.replace("HCGroup", "HCTapedLight")
    marker = "            token = token.replace('&&', ' and ').replace('||', ' or ')"
    substring = (
        "            token = re.sub("
        "r'([\\w.]+)\\.Substring\\(([^,()]+),\\s*([^()]+)\\)', "
        "r'\\1[\\2:\\2+\\3]', token)\n"
    )
    assert marker in adapter
    adapter = adapter.replace(marker, substring + marker)
    scope = dict(globals(), SimpleNamespace=NS)
    exec(compile(adapter, "synthetic-taped-light-adapter", "exec"), scope)
    env = scope["translated_rules"]()
    env["HCBuildIdentity"] = build_identity()
    env["HCTapedLightService"] = NS(**env.copy())
    return env


class SyntheticPort:
    def __init__(self, env):
        self.binding = env["HCTapedLightBinding"]()
        fields = dict(
            ManifestDigest="a"*64, MeasurementDigest="b"*64,
            GameBuild="synthetic-build", HostConfigRoot="CfgVehicles",
            HostClass="SurveyedHost", LightClass="SurveyedLight",
            SlotName="SurveyedSlot", TapeUnits=1, MaxDistance=2)
        for field, value in fields.items():
            setattr(self.binding, field, value)
        self.sample = env["HCTapedLightSnapshot"]()
        fields = dict(
            ActorId="alice", HostId="host", LightId="light",
            TapeId="tape", BatteryId="battery", HostHealth=.9,
            LightHealth=.8, TapeHealth=.6, BatteryHealth=.7, BatteryEnergy=50,
            TapeQuantity=10)
        for field, value in fields.items():
            setattr(self.sample, field, value)
        self.authorized = self.qualified = self.near = self.los = True
        self.available = self.lease = self.move_result = True
        self.drift = False
        self.fail_phase = 0
        self.consumptions, self.moves, self.writes = [], [], []
        self.releases = 0

    def ActorAllowed(self):
        return self.authorized

    def ActorKey(self):
        return self.sample.ActorId

    def Resolve(self):
        return self.binding if self.qualified else None

    def CurrentBuild(self):
        return "synthetic-build"

    def CustodyAvailable(self):
        return self.available

    def InRange(self, binding):
        return self.near

    def HasLOS(self, binding):
        return self.los

    def Acquire(self, mounting):
        return self.lease

    def Release(self):
        self.releases += 1
        return True

    def Load(self, state):
        return True

    def Observe(self, binding):
        return copy.deepcopy(self.sample)

    def CanTransfer(self, binding, mounting):
        if mounting:
            return self.sample.Place != 1
        return self.sample.Place == 1

    def ConsumeTape(self, units):
        self.consumptions.append(units)
        self.sample.TapeQuantity -= units

    def Transfer(self, binding, mounting):
        self.moves.append(mounting)
        self.sample.Place = 1 if mounting else 2
        if self.drift:
            self.sample.BatteryEnergy = 100
        return self.move_result

    def Write(self, record, phase):
        self.writes.append((phase, copy.deepcopy(record)))
        return phase != self.fail_phase


class TapedLightTests(unittest.TestCase):
    def setUp(self):
        self.e = service_rules()
        self.port = SyntheticPort(self.e)
        self.state = self.e["HCTapedLightState"]()
        self.code = self.e["HCTapedLightCode"]
        self.phase = self.e["HCTapedLightPhase"]
        self.assertEqual(self.code.OK, self.e["Open"](self.state, self.port))

    def run_op(self, key="mount-1", mounting=True):
        return self.e["Run"](self.state, self.port, key, mounting)

    def test_mount_spends_once_preserving_light_and_battery(self):
        before = copy.deepcopy(self.port.sample)
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True], self.port.moves)
        self.assertEqual(9, self.port.sample.TapeQuantity)
        for field in ("LightId", "BatteryId", "LightHealth",
                      "BatteryHealth", "BatteryEnergy"):
            self.assertEqual(getattr(before, field),
                             getattr(self.port.sample, field))

    def test_hand_removal_and_remount_requires_fresh_tape(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.port.sample.TapeId = ""
        self.assertEqual(self.code.OK, self.run_op("remove-1", False))
        self.assertEqual([1], self.port.consumptions)
        self.port.sample.TapeId = "fresh-roll"
        self.assertEqual(self.code.OK, self.run_op("mount-2"))
        self.assertEqual([1, 1], self.port.consumptions)
        self.assertEqual([True, False, True], self.port.moves)

    def test_missing_observed_prerequisites_never_spends(self):
        for field in ("authorized", "qualified", "near", "los",
                      "available", "lease"):
            with self.subTest(field=field):
                setattr(self.port, field, False)
                self.assertNotEqual(self.code.OK, self.run_op())
                setattr(self.port, field, True)
        self.assertEqual([], self.port.consumptions)
        self.assertEqual([], self.port.moves)

    def test_reused_key_cannot_become_different_operation(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual(self.code.CONFLICT, self.run_op("mount-1", False))
        self.assertEqual([True], self.port.moves)

    def test_unproven_native_attachment_cannot_be_removed(self):
        self.port.sample.Place = 1
        self.assertNotEqual(self.code.OK, self.run_op("remove", False))
        self.assertEqual([], self.port.moves)

    def test_intent_write_failure_never_spends(self):
        self.port.fail_phase = self.phase.INTENT
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual([], self.port.consumptions)
        self.assertEqual([], self.port.moves)

    def test_spent_tape_journal_failure_has_no_refund_or_retry(self):
        self.port.fail_phase = self.phase.TAPE_SPENT
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual(9, self.port.sample.TapeQuantity)
        self.assertEqual([], self.port.moves)
        self.assertEqual(self.code.QUARANTINED, self.run_op("retry"))
        self.assertEqual([1], self.port.consumptions)

    def test_false_move_even_after_arrival_is_quarantined(self):
        self.port.move_result = False
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual(1, self.port.sample.Place)
        self.assertEqual(9, self.port.sample.TapeQuantity)

    def test_battery_drift_is_not_repaired_or_refilled(self):
        self.port.drift = True
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual(100, self.port.sample.BatteryEnergy)
        self.assertTrue(self.state.Quarantined)

    def test_ruined_host_or_light_and_missing_tape_never_spends(self):
        for field, value in (("HostHealth", 0), ("LightHealth", 0),
                             ("TapeQuantity", 0), ("TapeId", "")):
            old = getattr(self.port.sample, field)
            setattr(self.port.sample, field, value)
            self.assertNotEqual(self.code.OK, self.run_op())
            setattr(self.port.sample, field, old)
        self.assertEqual([], self.port.consumptions)

    def test_recovery_of_unfinished_intent_is_quarantined(self):
        self.assertEqual(self.code.OK, self.run_op())
        unfinished = copy.deepcopy(self.port.writes[0][1])
        unfinished.Phase = self.phase.INTENT
        recovered = self.e["HCTapedLightState"]()
        def load(state):
            state.Records.Insert(unfinished)
            return True
        self.port.Load = load
        self.assertEqual(self.code.QUARANTINED,
                         self.e["Open"](recovered, self.port))
        self.assertTrue(recovered.Quarantined)


def journal_call(name, state, env, *args):
    """Adapt native output parameters only; execute the authored journal body."""
    import tests.unit.test_group_ui as ui
    implementation = inspect.getsource(ui.execute_member)
    implementation = implementation.replace(
        "if token.startswith('if ('): token='if '+token[4:-1]+':'",
        "if token.startswith(('if (', 'while (')):\n"
        "            prefix, expression = token.split(' (', 1)\n"
        "            token = prefix + ' ' + expression[:-1] + ':'")
    language = dict(vars(ui))
    exec(compile(implementation, "journal-output-adapter", "exec"), language)
    exec(compile(inspect.getsource(ui.ui_member),
                 "journal-receiver-adapter", "exec"), language)
    ui_member = language["ui_member"]
    full = (ROOT / "4_World/Survival/HCTapedLightService.c").read_text()
    start = re.search(r"class HCTapedLightJournal\s*\{", full)
    source = body(full, start.end())
    source = source.replace("FileAttr attr;", "int attr = 0;")
    source = source.replace("name.IndexOf(prefix)", "name.find(prefix)")
    source = source.replace(
        "name.Substring(prefix.Length(), length).ToInt()",
        "NativeInt(NativeSubstring(name, prefix.Length(), length))")
    env["NativeInt"] = int
    env["NativeSubstring"] = lambda text, start, count: text[start:start+count]
    source = source.replace("HCTapedLightState loaded;",
                            "HCGroupNative loaded;")
    source = re.sub(
        r"FindFileHandle handle = FindFile\(([^;]+)\);",
        r"handle, filename, attr = FindFile(\1);", source)
    source = source.replace(
        "found = FindNextFile(handle, filename, attr);",
        "found, filename, attr = FindNextFile(handle, filename, attr);")
    source = re.sub(
        r"if \(!Read\((\w+), (\d+), (\w+)\)\)",
        r"readOK, \3 = Read(\1, \2, \3); if (!readOK)", source)
    source = source.replace(
        "if (!JsonFileLoader<HCTapedLightState>.LoadData(text, loaded, error))",
        "jsonOK, loaded, error = Decode(text); if (!jsonOK)")
    source = source.replace(
        "if (!JsonFileLoader<HCTapedLightState>.MakeData(mHCState, text, error))",
        "jsonOK, text, error = Encode(mHCState); if (!jsonOK)")
    source = re.sub(r"(\w+)\.ToString\(\)", r"str(\1)", source)
    return ui_member(source, name, state, env, *args)


class TapedJournalTests(unittest.TestCase):
    def setUp(self):
        self.e = service_rules()

    def load_fixture(self, marker="1", build="synthetic-build",
                     omit_image=False, live="synthetic-build"):
        # Explicit synthetic native filesystem. No temporary files or engine.
        root = "synthetic/journal"
        files = {
            root + "/build.txt": build,
            root + "/intent_1.txt": marker,
            root + "/state_1.json": json.dumps({
                "Version": 1, "Records": [], "Quarantined": False})}
        if omit_image:
            del files[root + "/state_1.json"]
        names = iter(path.rsplit("/", 1)[1] for path in files)
        reads, closes = [], []

        def find(*args):
            return 1, next(names), 0

        def next_file(*args):
            name = next(names, "")
            return bool(name), name, 0

        def read(path, limit, output):
            reads.append(path)
            text = files.get(path, "")
            return 0 < len(text) <= limit, text

        def decode(text):
            data = json.loads(text)
            loaded = self.e["HCTapedLightState"]()
            loaded.Version = data["Version"]
            loaded.Records = EArray(data["Records"])
            loaded.Quarantined = data["Quarantined"]
            return True, loaded, ""

        journal = NS(mHCRoot=root, mHCFault=False, mHCState=None,
                     mHCSequence=0, Read=read,
                     Build=lambda: live)
        env = dict(
            FindFile=find, FindNextFile=next_file,
            CloseFindFile=lambda handle: closes.append(handle),
            FindFileFlags=NS(DIRECTORIES=1), FileAttr=NS(DIRECTORY=1),
            Math=NS(Max=max), Decode=decode,
            HCTapedLightService=self.e["HCTapedLightService"],
            HCBuildIdentity=self.e["HCBuildIdentity"])
        journal.Number = lambda *args: journal_call(
            "Number", journal, env, *args)
        state = self.e["HCTapedLightState"]()
        result = journal_call("Load", journal, env, state)
        self.assertEqual([1], closes)
        return result, journal, reads

    def test_valid_highest_pair_loads(self):
        result, journal, reads = self.load_fixture()
        self.assertTrue(result)
        self.assertEqual(1, journal.mHCSequence)

    def test_corrupt_highest_intent_cannot_load_payload(self):
        for marker in ("", "0", "2", "01", "1\n", "corrupt"):
            with self.subTest(marker=marker):
                result, journal, reads = self.load_fixture(marker=marker)
                self.assertFalse(result)
                self.assertIsNone(journal.mHCState)

    def test_highest_intent_without_payload_blocks(self):
        result, journal, reads = self.load_fixture(omit_image=True)
        self.assertFalse(result)
        self.assertIsNone(journal.mHCState)

    def test_changed_build_header_blocks_load(self):
        result, journal, reads = self.load_fixture(build="other-build")
        self.assertFalse(result)
        self.assertIsNone(journal.mHCState)

    def test_native_full_and_canonical_build_headers_are_the_same_build(self):
        # Real engine GetVersion is 1.30.164289.70; older journals may carry either text.
        for stored in ("1.30.164289.70", "1.30.164289"):
            for live in ("1.30.164289.70", "1.30.164289"):
                with self.subTest(stored=stored, live=live):
                    result, journal, reads = self.load_fixture(build=stored, live=live)
                    self.assertTrue(result)

    def test_other_build_headers_still_block_load(self):
        for stored, live in (("1.30.164289.7x", "1.30.164289.70"), ("1.30.164289.70", "1.30.164289.7x"),
                             ("", "1.30.164289.70"), (" 1.30.164289", "1.30.164289"),
                             ("1.30.164289.70", "1.30.1642890")):
            with self.subTest(stored=stored, live=live):
                result, journal, reads = self.load_fixture(build=stored, live=live)
                self.assertFalse(result)


class TapedPendingGuardTests(unittest.TestCase):
    setUp = TapedLightTests.setUp
    run_op = TapedLightTests.run_op

    def test_binding_admits_the_native_full_build_against_a_canonical_binding(self):
        self.port.CurrentBuild = lambda: "1.30.164289.70"
        self.port.binding.GameBuild = "1.30.164289"
        self.assertEqual(self.code.OK, self.run_op())
        for live in ("1.30.164289.7x", "1.30.1642890", " 1.30.164289"):
            self.setUp()
            self.port.CurrentBuild = lambda live=live: live
            self.port.binding.GameBuild = "1.30.164289"
            self.assertEqual(self.code.BLOCKED, self.run_op(), live)

    def test_pending_history_blocks_new_key_before_any_custody(self):
        for phase in (self.phase.INTENT, self.phase.TAPE_SPENT,
                      self.phase.MOVE_INTENT, self.phase.QUARANTINE):
            with self.subTest(phase=phase):
                self.setUp()
                self.assertEqual(self.code.OK, self.run_op())
                self.state.Records[0].Phase = phase
                self.port.sample.LightId = "another-light"
                self.port.sample.Place = 0
                calls = []
                self.port.CustodyAvailable = lambda: calls.append("custody") or True
                before = (list(self.port.moves), list(self.port.consumptions))
                self.assertEqual(self.code.QUARANTINED,
                                 self.run_op("different-key"))
                self.assertEqual([], calls)
                self.assertEqual(before, (self.port.moves, self.port.consumptions))

    def test_failed_intent_ack_never_acquires_custody(self):
        calls = []
        self.port.Acquire = lambda mounting: calls.append("acquire") or True
        self.port.fail_phase = self.phase.INTENT
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual([], calls)
        self.assertEqual([], self.port.moves)
        self.assertEqual([], self.port.consumptions)


def port_member(name, port, env, *args):
    from tests.unit.test_group_ui import ui_member
    full = (ROOT / "4_World/Survival/HCTapedLightService.c").read_text()
    start = re.search(r"class HCTapedLightPort\s*\{", full)
    # Explicit synthetic equivalents of the native fields' zero defaults.
    if not hasattr(port, "mHCMoveRecord"):
        port.mHCMoveRecord = None
    if not hasattr(port, "mHCReleaseConfirmed"):
        port.mHCReleaseConfirmed = False
    return ui_member(body(full, start.end()), name, port, env, *args)


def port_write(port, env, record, phase):
    return port_member("Write", port, env, record, phase)


class TapedCustodyJournalTests(unittest.TestCase):
    def recovery_case(self, failure=None, mode="absent", release=False,
                      changed_snapshot=True):
        # Synthetic native files/JSON/custody only; Save, Load, Write, Open and
        # Run all execute authored bodies. No filesystem, native or fsync proof.
        e = service_rules()
        root = "synthetic/journal"
        files = {root + "/build.txt": "synthetic-build"}
        events = []
        failed_quarantine_intents = []
        def dto(value):
            if isinstance(value, dict):
                return NS(**{k:dto(v) for k,v in value.items()})
            if isinstance(value, list):
                return EArray(dto(v) for v in value)
            return value
        def decode(text):
            try:
                return True, dto(json.loads(text)), ""
            except ValueError:
                return False, None, "synthetic invalid JSON"
        def encode(state):
            return True, json.dumps(state, default=vars, allow_nan=False), ""
        def read(path, limit, output):
            text = files.get(path, "")
            return 0 < len(text) <= limit, text
        def write(path, text):
            events.append(path.rsplit("/", 1)[1])
            if path in files or len(text) > 262144:
                return False
            # Fail before creating the quarantine intent. Match the phase,
            # not its sequence number: the protocol fix may reorder writes.
            if (failure == "quarantine-intent"
                and path.rsplit("/", 1)[1].startswith("intent_")
                and j.mHCState.Records[-1].Phase ==
                    e["HCTapedLightPhase"].QUARANTINE):
                failed_quarantine_intents.append(path)
                return False
            if failure and path.endswith("/" + failure):
                if mode == "partial":
                    files[path] = "{"
                elif mode == "complete":
                    files[path] = text
                return False
            files[path] = text
            return True
        names = [None]
        def find(*args):
            names[0] = iter(p.rsplit("/", 1)[1] for p in files)
            return 1, next(names[0]), 0
        def next_file(*args):
            name = next(names[0], "")
            return bool(name), name, 0
        env = dict(HCTapedLightService=e["HCTapedLightService"],
                   HCBuildIdentity=e["HCBuildIdentity"],
                   HCTapedLightPhase=e["HCTapedLightPhase"],
                   GetGame=lambda:NS(IsServer=lambda:True),
                   FindFile=find, FindNextFile=next_file,
                   CloseFindFile=lambda handle:None,
                   FindFileFlags=NS(DIRECTORIES=1), FileAttr=NS(DIRECTORY=1),
                   Math=NS(Max=max), Decode=decode, Encode=encode)
        def journal():
            j = NS(mHCRoot=root, mHCFault=False, mHCState=None,
                   mHCSequence=0, Read=read, WriteNew=write,
                   Build=lambda:"synthetic-build")
            j.Number = lambda *args:journal_call("Number", j, env, *args)
            j.Save = lambda *args:journal_call("Save", j, env, *args)
            return j
        j = journal()
        native = NS(mHCJournal=j, mHCHeld=False)
        port = SyntheticPort(e)
        port.Load = lambda state:journal_call("Load", j, env, state)
        port.Write = lambda record, phase:port_write(native, env, record, phase)
        def acquire(mounting):
            events.append("acquire")
            native.mHCHeld = True
            return True
        native.mHCCustody = NS(Release=lambda:release)
        port.Acquire = acquire
        port.Release = lambda:port_member("Release", native, env)
        observe = port.Observe
        reads = [0]
        def drift(binding):
            reads[0] += 1
            sample = observe(binding)
            if changed_snapshot and reads[0] == 2:
                sample.HostHealth = .8
            return sample
        port.Observe = drift
        state = e["HCTapedLightState"]()
        self.assertEqual(e["HCTapedLightCode"].OK, e["Open"](state, port))
        result = e["Run"](state, port, "custody-failure", True)
        self.assertEqual(e["HCTapedLightCode"].QUARANTINED, result)
        self.assertEqual([] if changed_snapshot else [True], port.moves)
        self.assertEqual([] if changed_snapshot else [1], port.consumptions)
        if failure == "quarantine-intent":
            self.assertEqual(1, len(failed_quarantine_intents))
        reopened = e["HCTapedLightState"]()
        recovered_journal = journal()
        port.Load = lambda s:journal_call("Load", recovered_journal, env, s)
        code = e["Open"](reopened, port)
        self.assertFalse(reopened.Ready)
        self.assertIn(code, (e["HCTapedLightCode"].QUARANTINED,
                             e["HCTapedLightCode"].BLOCKED))
        return files, events, reopened, code, e

    def test_failed_release_quarantine_survives_authored_journal_load(self):
        files, events, recovered, code, e = self.recovery_case()
        self.assertEqual(e["HCTapedLightCode"].QUARANTINED, code)
        self.assertTrue(recovered.Quarantined)
        self.assertLess(events.index("state_1.json"), events.index("acquire"))
        self.assertTrue(files["synthetic/journal/state_1.json"])

    def test_partial_or_unacknowledged_fault_write_cannot_recover_ready(self):
        for failure, mode in (("intent_2.txt", "absent"),
                              ("state_2.json", "partial"),
                              ("state_2.json", "complete")):
            with self.subTest(failure=failure, mode=mode):
                self.recovery_case(failure, mode)

    def test_positive_release_after_changed_snapshot_keeps_intent_quarantined(self):
        self.recovery_case(release=True)

    def test_terminal_release_failure_with_failed_quarantine_intent(self):
        files, events, recovered, code, e = self.recovery_case(
            failure="quarantine-intent", changed_snapshot=False)
        self.assertEqual(e["HCTapedLightCode"].QUARANTINED, code)
        self.assertTrue(recovered.Quarantined)

    def test_native_port_allows_only_intent_before_custody(self):
        e = service_rules()
        calls = []
        p = NS(mHCHeld=False,
               mHCJournal=NS(Save=lambda *args:calls.append(args) or True))
        env = dict(HCTapedLightPhase=e["HCTapedLightPhase"],
                   GetGame=lambda:NS(IsServer=lambda:True))
        phase = e["HCTapedLightPhase"]
        self.assertTrue(port_write(p, env, None, phase.INTENT))
        for value in (phase.TAPE_SPENT, phase.MOVE_INTENT,
                      phase.MOUNTED, phase.REMOVED, phase.QUARANTINE):
            self.assertFalse(port_write(p, env, None, value))
        self.assertEqual(1, len(calls))
        p.mHCHeld = True
        self.assertTrue(port_write(p, env, None, phase.QUARANTINE))
        env["GetGame"] = lambda:NS(IsServer=lambda:False)
        self.assertFalse(port_write(p, env, None, phase.INTENT))


class TapedTerminalReceiptTests(unittest.TestCase):
    def setUp(self):
        self.phase = service_rules()["HCTapedLightPhase"]
        self.calls = []
        self.ack = True
        self.released = True
        def save(record, phase):
            self.calls.append((record, phase))
            return self.ack
        self.p = NS(mHCHeld=True, mHCJournal=NS(Save=save),
                    mHCCustody=NS(Release=lambda:self.released))
        self.env = dict(HCTapedLightPhase=self.phase,
                        GetGame=lambda:NS(IsServer=lambda:True))
        self.record = NS(RecordKey="synthetic-one")
        self.other = NS(RecordKey="synthetic-other")

    def write(self, phase, record=None):
        return port_write(self.p, self.env,
                          self.record if record is None else record, phase)

    def release(self):
        return port_member("Release", self.p, self.env)

    def test_terminal_needs_release_and_exact_move_record(self):
        self.assertTrue(self.write(self.phase.MOVE_INTENT))
        self.assertFalse(self.write(self.phase.MOUNTED))
        self.assertTrue(self.release())
        self.assertFalse(self.write(self.phase.MOUNTED, self.other))
        self.assertEqual(1, len(self.calls))
        self.assertTrue(self.write(self.phase.MOUNTED))
        self.assertEqual(2, len(self.calls))

    def test_terminal_receipt_is_single_use_for_both_operations(self):
        for terminal in (self.phase.MOUNTED, self.phase.REMOVED):
            with self.subTest(terminal=terminal):
                self.setUp()
                self.assertTrue(self.write(self.phase.MOVE_INTENT))
                self.assertTrue(self.release())
                self.assertTrue(self.write(terminal))
                self.assertFalse(self.write(terminal))
                self.assertEqual(2, len(self.calls))

    def test_failed_terminal_write_consumes_permission(self):
        self.assertTrue(self.write(self.phase.MOVE_INTENT))
        self.assertTrue(self.release())
        self.ack = False
        self.assertFalse(self.write(self.phase.MOUNTED))
        self.ack = True
        self.assertFalse(self.write(self.phase.MOUNTED))
        self.assertEqual(2, len(self.calls))

    def test_failed_move_or_release_never_arms_terminal_permission(self):
        self.ack = False
        self.assertFalse(self.write(self.phase.MOVE_INTENT))
        self.ack = True
        self.assertTrue(self.release())
        self.assertFalse(self.write(self.phase.MOUNTED))
        self.setUp()
        self.assertTrue(self.write(self.phase.MOVE_INTENT))
        self.released = False
        self.assertFalse(self.release())
        self.assertTrue(self.p.mHCHeld)
        self.assertFalse(self.write(self.phase.MOUNTED))


class TapedHistoryTests(unittest.TestCase):
    setUp = TapedLightTests.setUp
    run_op = TapedLightTests.run_op

    def test_mount_source_and_cost_are_validated_on_recovery(self):
        self.assertEqual(self.code.OK, self.run_op())
        record = self.state.Records[0]
        for field, value in (("Place", 1), ("TapeQuantity", .5)):
            with self.subTest(field=field):
                original = getattr(record.BeforeData, field)
                setattr(record.BeforeData, field, value)
                self.assertFalse(self.e["StateValid"](self.state))
                setattr(record.BeforeData, field, original)

    def test_orphan_removal_is_not_a_committed_history(self):
        self.assertEqual(self.code.OK, self.run_op())
        record = self.state.Records[0]
        record.Mounting = False
        record.Phase = self.phase.REMOVED
        record.BeforeData.Place = 1
        self.assertFalse(self.e["StateValid"](self.state))

    def test_duplicate_active_mount_is_not_a_committed_history(self):
        self.assertEqual(self.code.OK, self.run_op())
        duplicate = copy.deepcopy(self.state.Records[0])
        duplicate.RecordKey = "different-key"
        self.state.Records.Insert(duplicate)
        self.assertFalse(self.e["StateValid"](self.state))

    def test_removal_cannot_have_tape_spent_phase_or_free_source(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual(self.code.OK, self.run_op("remove", False))
        record = self.state.Records[1]
        record.Phase = self.phase.TAPE_SPENT
        self.assertFalse(self.e["StateValid"](self.state))
        record.Phase = self.phase.REMOVED
        record.BeforeData.Place = 0
        self.assertFalse(self.e["StateValid"](self.state))

    def test_pending_history_cannot_have_later_operations(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual(self.code.OK, self.run_op("remove", False))
        self.state.Records[0].Phase = self.phase.MOVE_INTENT
        self.assertFalse(self.e["StateValid"](self.state))

    def test_replay_rejects_changed_qualified_binding(self):
        self.assertEqual(self.code.OK, self.run_op())
        for field, value in (("MeasurementDigest", "c"*64),
                             ("ManifestDigest", "d"*64),
                             ("SlotName", "OtherSlot"), ("TapeUnits", 2)):
            with self.subTest(field=field):
                original = getattr(self.port.binding, field)
                setattr(self.port.binding, field, value)
                self.assertEqual(self.code.CONFLICT, self.run_op())
                setattr(self.port.binding, field, original)
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True], self.port.moves)

    def test_removal_rejects_changed_qualified_binding(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.port.binding.SlotName = "OtherSlot"
        self.assertEqual(self.code.BLOCKED, self.run_op("remove", False))
        self.assertEqual([True], self.port.moves)

    def test_terminal_record_budget_is_not_recycled(self):
        self.port.sample.TapeQuantity = 1000
        for index in range(128):
            self.assertEqual(self.code.OK, self.run_op(
                "operation-" + str(index), index % 2 == 0))
        self.assertEqual(self.code.LIMIT, self.run_op("over-budget"))
        self.assertEqual(128, len(self.state.Records))
        self.assertEqual(128, len(self.port.moves))
        self.assertEqual(64, len(self.port.consumptions))

    def test_pending_key_is_never_acknowledged_as_committed(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.state.Records[0].Phase = self.phase.MOVE_INTENT
        self.assertEqual(self.code.QUARANTINED, self.run_op())
        self.assertEqual([1], self.port.consumptions)
        self.assertEqual([True], self.port.moves)

    def test_recovered_removal_preserves_mount_binding_identity(self):
        self.assertEqual(self.code.OK, self.run_op())
        self.assertEqual(self.code.OK, self.run_op("remove", False))
        self.state.Records[1].BindingData.SlotName = "OtherSlot"
        self.assertFalse(self.e["StateValid"](self.state))
