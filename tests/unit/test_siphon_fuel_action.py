"""Execute restricted authored action guards with synthetic native boundaries.

These tests establish neither Enforce compilation nor native inventory recovery.

Actual TDD 2026-11-16:
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_siphon_fuel_action -v
RED 10 missing-action failures -> GREEN 10 diagnostic guard tests. A contract
initially confused CanFillContainer with FillContainer; narrowed to the latter.
Trusted-write follow-up RED 7 missing seam/gate failures -> GREEN 16 tests.
Further actual RED found retargeting a held reservation and accepting a receipt
after lock loss. Both fixed. One fixture incorrectly expected a full second
after 900 ms; its explicit clock was corrected. Final 26 action tests passed.
Combined action + tests.unit.test_fuel_transfer command: 36 tests passed.

API/units proof: native CAContinuousFillFuel Setup multiplies car capacity space
by 1000; CalcAndSetQuantity uses container quantity * 0.001 for native car fill.
Car.Leak takes the same car-fluid amount units, returns void. Liquid.FillContainer
sets type then AddQuantity, separately, without transactional acknowledgement.
PrintFormat supports nine arguments (1_Core/proto/EnDebug.c:108).
Native035 metadata: all 7389 supplied classes checked, 32 Car-family config
entries including templates, 22 liquid-mask fields all preserved as string
expressions/kind_variant. Live native masks are necessary, not inferred here.

Minimal coordinator-owned native experiment (NOT executed by this worker):
1. Fresh disposable server/profile and package; spawn an owned intact stopped
   CarScript, owned liquid container and owned diagnostic actor with it in hands.
   Record actual classes, build/world/package, fluid capacity/fraction, quantity,
   native liquid mask/type and the observed fuel action component/refill point.
   Establish actual reach/LOS; do not guess transforms/component indices.
2. ConfigureDiagnostic(true,500,1,500) is read-only. Create fresh action/data,
   set m_Player/m_Target/m_MainItem from those native objects; call OnStartServer.
   After one real second call OnFinishProgressServer; no balances may change.
   Read-only mode requires a real identity. A server-owned diagnostic actor
   without identity is permitted only by the explicit trusted fixture mode.
3. Fresh data, ConfigureDiagnostic(true,500,1,500,true), same observed actor/target
   validations. Start, finish after one second, then OnEndServer. Capture
   NONDURABLE logs and data fields; match measured debit in liters to credited ml.
   The permit is consumed before debit: another probe requires explicit rearm.
4. Fresh controlled cases: empty/wrong/full vessel, depleted donor, cancellation,
   two competing reservations, movement/occlusion, native readback rounding and
   restart/save-order boundaries. A rejection or ambiguous balance is a failure,
   not a reason to refund/replay or report acceptance.
5. Repeat across the justified car/container matrix. Ordinary production action
   registration, tool eligibility, crash/cross-save recovery, clients and measured
   native behavior remain pending. Read-only metadata is not full item support.
"""
from pathlib import Path
import ast
import re
from types import SimpleNamespace as NS
import unittest

try:
    from .test_crafting_completion import body
    from .test_core_lifecycle import tokens, NativeArray
    from .test_fuel_transfer import authored_policy, Binary32, f32
except ImportError:
    from test_crafting_completion import body
    from test_core_lifecycle import tokens, NativeArray
    from test_fuel_transfer import authored_policy, Binary32, f32

SOURCE = Path(__file__).resolve().parents[2] / "mods/HollowCountry/scripts/4_World/Actions/HCActionSiphonFuel.c"


class DiagnosticArray(NativeArray):
    def Find(self, item):
        return next((i for i, value in enumerate(self) if value is item), -1)


def authored(name, parameters, context, binary32=False):
    from tests.unit.test_c3_survivalcfg import config_ports
    context.update(config_ports())  # Explicit synthetic default profile.
    text = re.sub(r"//[^\n]*", "", body(str(SOURCE), name))
    def expr(value):
        value = re.sub(r"\b(?:int|float|bool|PlayerBase|CarScript|HCSiphonDiagnosticData|array<string>) (\w+) =", r"\1 =", value)
        value = value.replace("new array<string>", "NativeArray()")
        value = re.sub(r"(?<![.\w])m_Sessions\b", "self.m_Sessions", value)
        value = re.sub(r"(?<![.\w])(Purge|Owns|Release)\(", r"self.\1(", value)
        value = value.replace("&&", " and ").replace("||", " or ")
        value = re.sub(r"!(?!=)", "not ", value)
        for old, new in (("true", "True"), ("false", "False"), ("null", "None")):
            value = re.sub(r"\b" + old + r"\b", new, value)
        return value
    lines, indent = [], 1
    for token in tokens(text):
        if token == "{": indent += 1; continue
        if token == "}": indent -= 1; continue
        reverse = re.fullmatch(r"for \(int (\w+) = (.*); \1 >= 0; \1--\)", token, re.S)
        each = re.fullmatch(r"foreach \(string (\w+) : (.*)\)", token, re.S)
        if reverse:
            line = "for " + reverse[1] + " in range(" + expr(reverse[2]) + ", -1, -1):"
        elif each:
            line = "for " + each[1] + " in " + expr(each[2]) + ":"
        elif token.startswith("if ("):
            depth = 0
            for index in range(3, len(token)):
                if token[index] == "(": depth += 1
                if token[index] == ")": depth -= 1
                if depth == 0:
                    line = "if " + expr(token[4:index]) + ": " + expr(token[index + 1:].strip())
                    break
            else: raise AssertionError("unsupported conditional")
        elif token == "else":
            line = "else:"
        else:
            if re.search(r"\b(for|while|foreach|catch|switch)\b", token):
                raise AssertionError("unsupported authored control flow")
            line = expr(token)
        lines.append("    " * indent + line.replace("\n", " "))
    namespace = context
    statics = sorted(set(re.findall(r"(?<![.\w])s_\w+", text)))
    globals_line = ["    global " + ",".join(statics)] if statics else []
    tree = ast.parse("def actual(self," + parameters + "):\n" + "\n".join(globals_line + lines))
    if binary32:
        tree = Binary32().visit(tree)
    exec(compile(ast.fix_missing_locations(tree), "authored-siphon:" + name, "exec"), namespace)
    return namespace["actual"]


def session(actor=None, donor=None, vessel=None):
    return NS(m_Player=actor or object(), Donor=donor or object(),
              Vessel=vessel or object(), LockHeld=False, StartedMs=0)


class SiphonFuelActionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), "missing diagnostic siphon action")
        self.source = SOURCE.read_text()
        constants = {k: int(v) for k, v in re.findall(r"static const int (\w+) = (\d+);", self.source)}
        self.context = {**constants, "NativeArray": DiagnosticArray,
                        "HCFuelTransferPolicy": NS(**authored_policy())}
        lease = authored("LeaseLive", "startedMs,nowMs", self.context)
        self.context["LeaseLive"] = lambda started, now: lease(None, started, now)
        self.locks = NS(m_Sessions=DiagnosticArray())
        for name, args in (("Purge", "nowMs"), ("Acquire", "data,nowMs"),
                           ("Owns", "data,nowMs"), ("Release", "data"), ("Clear", "")):
            fn = authored(name, args, self.context)
            setattr(self.locks, name, lambda *a, fn=fn: fn(self.locks, *a))

    def test_given_same_actor_car_or_container_then_reservation_is_rejected(self):
        first = session()
        self.assertTrue(self.locks.Acquire(first, 100))
        for second in (first, session(actor=first.m_Player), session(donor=first.Donor),
                       session(vessel=first.Vessel)):
            self.assertFalse(self.locks.Acquire(second, 101))
        self.assertEqual(len(self.locks.m_Sessions), 1)
        self.assertTrue(self.locks.Acquire(session(), 101))

    def test_given_cancellation_then_release_is_idempotent_and_retry_is_fresh(self):
        first, other = session(), session()
        self.assertTrue(self.locks.Acquire(first, 100))
        self.assertTrue(self.locks.Acquire(other, 100))
        self.locks.Release(first); self.locks.Release(first)
        self.assertFalse(first.LockHeld)
        self.assertTrue(self.locks.Owns(other, 101))
        self.assertTrue(self.locks.Acquire(session(donor=first.Donor), 101))

    def test_aborted_callback_without_end_expires_and_cannot_later_own_lock(self):
        first = session(); self.locks.Acquire(first, 100)
        self.assertFalse(self.locks.Owns(first, 10101))
        replacement = session(donor=first.Donor)
        self.assertTrue(self.locks.Acquire(replacement, 10101))
        self.assertFalse(first.LockHeld)
        self.locks.Release(first)
        self.assertTrue(self.locks.Owns(replacement, 10102))

    def test_backwards_clock_and_deleted_endpoints_expire_fail_closed(self):
        for change in ("clock", "m_Player", "Donor", "Vessel"):
            first = session(); self.locks.Acquire(first, 100)
            if change != "clock": setattr(first, change, None)
            self.locks.Purge(99 if change == "clock" else 101)
            self.assertFalse(first.LockHeld)
            self.assertEqual(self.locks.m_Sessions, [])

    def test_reservations_are_bounded_and_clear_invalidates_every_owner(self):
        entries = [session() for _ in range(self.context["MAX_SESSIONS"])]
        for data in entries: self.assertTrue(self.locks.Acquire(data, 100))
        self.assertFalse(self.locks.Acquire(session(), 100))
        self.locks.Clear()
        self.assertFalse(any(data.LockHeld for data in entries))
        self.assertEqual(self.locks.m_Sessions, [])

    def live_fixture(self):
        state = NS(server=True, enabled=True, alive=True, unconscious=False,
                   restrained=False, in_vehicle=False, ruined=False, engine=False,
                   speed=0., quantity=1000., maximum=20000., fuel=.5, capacity=60.,
                   can_fill=True, liquid=8192, visible=True, open=True, component=0,
                   selections=["refill"], held=True, parent=None)
        vessel = NS(IsDamageDestroyed=lambda: state.ruined, IsOpen=lambda: state.open,
                    HasQuantity=lambda: True, IsLiquidContainer=lambda: True,
                    GetQuantity=lambda: state.quantity, GetQuantityMax=lambda: state.maximum,
                    GetLiquidType=lambda: state.liquid)
        car = NS(IsDamageDestroyed=lambda: state.ruined, EngineIsOn=lambda: state.engine,
                 GetSpeedometerAbsolute=lambda: state.speed,
                 GetFluidCapacity=lambda _: state.capacity,
                 GetFluidFraction=lambda _: state.fuel, GetActionCompNameFuel=lambda: "refill",
                 GetActionComponentNameList=lambda _, a: a.extend(state.selections))
        player = NS(IsAlive=lambda: state.alive, IsUnconscious=lambda: state.unconscious,
                    IsRestrained=lambda: state.restrained, IsInVehicle=lambda: state.in_vehicle,
                    GetIdentity=lambda: object(), GetItemInHands=lambda: vessel if state.held else None)
        target = NS(GetObject=lambda: car, GetParent=lambda: state.parent,
                    GetComponentIndex=lambda: state.component)
        ctx = {**self.context, "GetGame": lambda: NS(IsServer=lambda: state.server),
               "s_DiagnosticEnabled": state.enabled, "LIQUID_GASOLINE": 8192,
               "CarFluid": NS(FUEL=0), "CarScript": NS(Cast=lambda v: v),
               "Liquid": NS(CanFillContainer=lambda v, liquid: state.can_fill),
               "ReachAndVisible": lambda p, c, t: state.visible}
        fn = authored("ValidateLive", "player,target,vessel", ctx)
        state.objects, state.context = NS(player=player, target=target, vessel=vessel, car=car), ctx
        return state, lambda: fn(None, player, target, vessel)

    def test_live_gate_rejects_wrong_liquid_capacity_actor_range_and_car_state(self):
        state, valid = self.live_fixture()
        self.assertTrue(valid())
        for key, value in (("server", False), ("alive", False), ("unconscious", True),
                           ("restrained", True), ("in_vehicle", True), ("ruined", True),
                           ("engine", True), ("speed", 1.), ("speed", float("nan")),
                           ("quantity", -1.), ("quantity", 20000.), ("liquid", 512),
                           ("can_fill", False), ("visible", False), ("open", False),
                           ("capacity", 0.), ("fuel", 0.), ("fuel", 1.1),
                           ("fuel", float("nan")), ("component", -1),
                           ("selections", ["wheel"]), ("held", False), ("parent", object())):
            state, valid = self.live_fixture()
            setattr(state, key, value)
            self.assertFalse(valid(), (key, value))

    def test_empty_container_can_be_examined_without_changing_liquid_type(self):
        state, valid = self.live_fixture()
        state.quantity, state.liquid = 0., 0
        self.assertTrue(valid())

    def test_no_identity_actor_requires_explicit_trusted_disposable_probe(self):
        state, valid = self.live_fixture()
        state.objects.player.GetIdentity = lambda: None
        state.context["s_TrustedTransferEnabled"] = False
        self.assertFalse(valid())
        state.context["s_TrustedTransferEnabled"] = True
        self.assertTrue(valid())
        state.server = False
        self.assertFalse(valid())

    def test_native_selection_list_is_bounded_and_recipient_checks_allow_empty_donor(self):
        state, valid = self.live_fixture()
        state.selections = ["refill"] * 65
        self.assertFalse(valid())
        state.selections, state.fuel = ["refill"], 0.
        data = session(actor=state.objects.player, donor=state.objects.car, vessel=state.objects.vessel)
        data.m_Target, data.m_MainItem = state.objects.target, data.Vessel
        recipient = authored("RecipientReady", "data", state.context)
        self.assertTrue(recipient(None, data))
        state.held = False
        self.assertFalse(recipient(None, data))

    def test_configure_resets_live_leases_and_bad_configuration_disarms(self):
        state, data, events, ctx, run = self.transfer_fixture()
        limits = authored("DiagnosticLimits", "rateMl,maxStepSeconds,capMl", ctx)
        ctx["DiagnosticLimits"] = lambda *args: limits(None, *args)
        arm = authored("ConfigureDiagnostic", "enabled,rateMl,maxStepSeconds,capMl,trustedTransfer", ctx)
        self.assertTrue(arm(None, True, 500., 1., 1000., False))
        self.assertFalse(data.LockHeld)
        self.assertFalse(ctx["s_TrustedTransferEnabled"])
        self.assertTrue(arm(None, True, 500., 1., 1000., True))
        self.assertTrue(ctx["s_TrustedTransferEnabled"])
        self.assertFalse(arm(None, True, float("nan"), 1., 1000., True))
        self.assertFalse(ctx["s_DiagnosticEnabled"])
        self.assertFalse(ctx["s_TrustedTransferEnabled"])

    def test_diagnostic_is_unregistered_disabled_and_mutations_require_trusted_gate(self):
        code = re.sub(r"//[^\n]*", "", self.source)
        for forbidden in ("modded class", "RegisterActions", "AddAction(",
                          ".Fill(", "SetQuantity(", "AddQuantity(",
                          "SetLiquidType(", "CreateObject", "RPC", "SaveFile"):
            self.assertNotIn(forbidden, code)
        self.assertIn("s_DiagnosticEnabled = false", self.source)
        self.assertIn("s_TrustedTransferEnabled = false", self.source)
        transfer = body(str(SOURCE), "TransferDiagnostic")
        self.assertLess(transfer.index("s_TrustedTransferEnabled"), transfer.index(".Leak("))
        self.assertLess(transfer.index(".Leak("), transfer.index("CreditQuantum"))
        self.assertLess(transfer.index("CreditQuantum"), transfer.index("Liquid.FillContainer("))
        self.assertIn("VerifyDiagnosticReceipt", transfer)
        self.assertIn("ReceiptConserves", body(str(SOURCE), "VerifyDiagnosticReceipt"))
        self.assertEqual(code.count(".Leak("), 1)
        self.assertEqual(code.count("Liquid.FillContainer("), 1)
        self.assertIn("new CAContinuousTime(HCFuelSiphonConfig.Get().DiagnosticStepSeconds)", body(str(SOURCE), "CreateActionComponent"))
        self.assertIn("HCFuelTransferPolicy.PlanQuantum", body(str(SOURCE), "OnFinishProgressServer"))
        finish = body(str(SOURCE), "OnFinishProgressServer")
        self.assertLess(finish.index("ValidateLive"), finish.index("PlanQuantum"))
        self.assertLess(finish.index("data.Sampled = true"), finish.index("PlanQuantum"))
        end = body(str(SOURCE), "OnEndServer")
        self.assertLess(end.index("Release"), end.index("super.OnEndServer"))

    def test_reach_uses_native_refill_point_and_both_view_and_fire_occlusion(self):
        method = body(str(SOURCE), "ReachAndVisible")
        for term in ("GetRefillPointPosWS", "GetActionDistanceFuel", "GetPlayerHeadPosition",
                     "vector.DistanceSq", "ObjIntersectView", "ObjIntersectFire"):
            self.assertIn(term, method)
        ray = body(str(SOURCE), "ClearRay")
        self.assertIn("DayZPhysics.RaycastRV", ray)
        self.assertIn("hits[0] != donor", ray)
        self.assertIn("vector.DistanceSq(contact, endpoint)", ray)
        self.assertNotIn("GetCursorHitPos", method + ray)

    def test_configuration_limits_and_server_only_gate(self):
        valid = authored("DiagnosticLimits", "rateMl,maxStepSeconds,capMl", self.context)
        self.assertTrue(valid(None, 500., 1., 1000.))
        for args in ((0., 1., 1.), (500., 0., 1.), (500., 1., 0.),
                     (10001., 1., 1.), (1., 2., 1.), (1., 1., 1001.),
                     (float("inf"), 1., 1.), (float("nan"), 1., 1.)):
            self.assertFalse(valid(None, *args))
        arm = body(str(SOURCE), "ConfigureDiagnostic")
        self.assertLess(arm.index("IsServer"), arm.index("s_DiagnosticEnabled = false"))
        self.assertLess(arm.index("s_Locks.Clear"), arm.index("s_DiagnosticEnabled = enabled"))

    def transfer_fixture(self, **changes):
        state = NS(server=True, ready=True, liters=f32(30.), quantity=f32(1000.),
                   maximum=f32(20000.), liquid=8192, now=1000, leak_mode="normal",
                   fill_mode="normal", after_debit=None, after_credit=None)
        for key, value in changes.items(): setattr(state, key, value)
        events = []
        def leak(fluid, amount):
            events.append(("debit", f32(amount)))
            if state.leak_mode == "none": return
            state.liters = f32(max(0., f32(state.liters - f32(amount))))
            if state.after_debit: state.after_debit()
            if state.leak_mode == "abort": raise RuntimeError("synthetic native abort")
        def fill(vessel, liquid, amount):
            events.append(("credit", f32(amount)))
            if state.fill_mode == "none": return
            if state.fill_mode == "abort": raise RuntimeError("synthetic native abort")
            amount = f32(amount / 2) if state.fill_mode == "partial" else f32(amount)
            if state.fill_mode == "excess": amount = f32(amount + 1)
            state.quantity = f32(min(state.maximum, f32(state.quantity + amount)))
            state.liquid = liquid
            if state.after_credit: state.after_credit()
        donor = NS(GetFluidCapacity=lambda _: f32(60.),
                   GetFluidFraction=lambda _: f32(state.liters / f32(60.)), Leak=leak)
        vessel = NS(GetQuantity=lambda: state.quantity, GetQuantityMax=lambda: state.maximum,
                    GetLiquidType=lambda: state.liquid)
        data = session(donor=donor, vessel=vessel)
        data.m_Target, data.m_MainItem = NS(GetObject=lambda: donor), vessel
        data.Sampled, data.TransferAttempted, data.PlannedMl = True, False, f32(500.)
        data.ObservedDonorLiters, data.ObservedVesselMl = f32(30.), state.quantity
        self.locks.Acquire(data, 100)
        ctx = {**self.context, "f32": f32, "s_DiagnosticEnabled": True,
               "s_TrustedTransferEnabled": True, "s_Locks": self.locks,
               "s_RateMl": 500., "s_MaxStepSeconds": 1., "s_CapMl": 1000.,
               "GetGame": lambda: NS(IsServer=lambda: state.server, GetTime=lambda: state.now),
               "CarFluid": NS(FUEL=0), "LIQUID_GASOLINE": 8192,
               "Liquid": NS(FillContainer=fill),
               "HCSiphonDiagnosticData": NS(Cast=lambda v: v), "CarScript": NS(Cast=lambda v: v),
               "super": NS(OnStartServer=lambda d: None, OnEndServer=lambda d: None),
               "ValidateLive": lambda *args: state.ready,
               "RecipientReady": lambda d: state.ready and state.liquid in (0, 8192)
                                          and state.quantity < state.maximum,
               "ReportDiagnostic": lambda d: events.append(("report", d.DiagnosticStatus))}
        # Execute the shared helper too; native status/log outputs are explicit synthetic ports.
        from tests.unit.test_refusal_report import install_refusal
        state.messages, state.refusal_lines = [], []
        data.m_Player = NS(MessageStatus=state.messages.append)
        donor.GetType = lambda: 'SyntheticDonor'
        ctx['GetGame'] = lambda: NS(IsServer=lambda:state.server, GetTime=lambda:state.now,
                                   GetTickTime=lambda:state.now / 1000.)
        ctx['Print'] = state.refusal_lines.append
        install_refusal(ctx)
        stop = authored("StopTransfer", "data,reason", ctx)
        ctx["StopTransfer"] = lambda d, reason: stop(None, d, reason)
        receipt = authored("VerifyDiagnosticReceipt", "data", ctx, binary32=True)
        ctx["VerifyDiagnosticReceipt"] = lambda d: receipt(None, d)
        transfer = authored("TransferDiagnostic", "data", ctx, binary32=True)
        ctx["TransferDiagnostic"] = lambda d: transfer(None, d)
        return state, data, events, ctx, lambda: transfer(None, data)

    def test_default_readonly_and_explicit_write_hooks_release_and_never_replay(self):
        for trusted in (False, True):
            state, data, events, ctx, run = self.transfer_fixture()
            state.now = 1100  # One synthetic second after reservation at 100 ms.
            ctx["s_TrustedTransferEnabled"], data.Sampled = trusted, False
            finish = authored("OnFinishProgressServer", "action_data", ctx)
            finish(None, data)
            writes = [e for e in events if e[0] != "report"]
            self.assertEqual(len(writes), 2 if trusted else 0)
            self.assertEqual(data.PlannedMl, f32(500.))
            self.assertFalse(data.LockHeld)
            count = len(events); finish(None, data)
            self.assertEqual(len(events), count)

    def test_repeated_start_cannot_retarget_an_existing_reservation(self):
        state, data, events, ctx, run = self.transfer_fixture()
        original = data.Donor
        replacement = NS(**vars(original))
        data.Sampled, data.m_Target = False, NS(GetObject=lambda: replacement)
        start = authored("OnStartServer", "action_data", ctx)
        start(None, data)
        self.assertIs(data.Donor, original)

    def test_cancel_hook_releases_before_late_finish(self):
        state, data, events, ctx, run = self.transfer_fixture()
        data.Sampled = False
        authored("OnEndServer", "action_data", ctx)(None, data)
        authored("OnFinishProgressServer", "action_data", ctx)(None, data)
        self.assertFalse(data.LockHeld)
        self.assertFalse(any(e[0] in ("debit", "credit") for e in events))

    def test_lost_reservation_during_credit_cannot_report_success(self):
        state, data, events, ctx, run = self.transfer_fixture()
        state.after_credit = lambda: self.locks.Release(data)
        self.assertFalse(run())

    def test_source_debit_precedes_bounded_credit_and_no_replay(self):
        state, data, events, ctx, run = self.transfer_fixture()
        self.assertTrue(run())
        writes = [event for event in events if event[0] != "report"]
        self.assertEqual([x[0] for x in writes], ["debit", "credit"])
        self.assertEqual(writes[0][1], f32(.5))
        self.assertEqual(state.liters, f32(29.5))
        self.assertEqual(state.quantity, f32(1500.))
        self.assertEqual(state.liquid, 8192)
        self.assertFalse(ctx["s_TrustedTransferEnabled"])
        count = len(events)
        self.assertFalse(run())
        self.assertEqual(len(events), count)

    def test_unarmed_client_cancelled_expired_or_changed_pair_never_writes(self):
        for fault in ("unarmed", "client", "cancel", "expired", "wrong_pair", "invalid"):
            state, data, events, ctx, run = self.transfer_fixture()
            if fault == "unarmed": ctx["s_TrustedTransferEnabled"] = False
            if fault == "client": state.server = False
            if fault == "cancel": self.locks.Release(data)
            if fault == "expired": state.now = 10101
            if fault == "wrong_pair": data.m_MainItem = object()
            if fault == "invalid": state.ready = False
            self.assertFalse(run(), fault)
            self.assertFalse(any(event[0] in ("debit", "credit") for event in events), fault)
            self.locks.Clear()

    def test_missing_debit_never_credits_and_trips_until_explicit_rearm(self):
        state, data, events, ctx, run = self.transfer_fixture(leak_mode="none")
        self.assertFalse(run())
        self.assertEqual(state.quantity, f32(1000.))
        self.assertFalse(ctx["s_TrustedTransferEnabled"])
        self.assertEqual([e[0] for e in events if e[0] != "report"], ["debit"])
        count = len(events)
        self.assertFalse(run())
        self.assertEqual(len(events), count)

    def test_credit_failures_stop_without_refund_or_repeated_grant(self):
        for mode in ("none", "partial", "excess"):
            state, data, events, ctx, run = self.transfer_fixture(fill_mode=mode)
            self.assertFalse(run(), mode)
            self.assertEqual(state.liters, f32(29.5))
            self.assertFalse(ctx["s_TrustedTransferEnabled"])
            self.assertEqual([e[0] for e in events if e[0] != "report"], ["debit", "credit"])
            count = len(events)
            self.assertFalse(run())
            self.assertEqual(len(events), count)

    def test_abort_between_native_writes_is_not_retried_or_rolled_back(self):
        for mode in ("debit", "credit"):
            state, data, events, ctx, run = self.transfer_fixture(
                **({"leak_mode": "abort"} if mode == "debit" else {"fill_mode": "abort"}))
            with self.assertRaises(RuntimeError): run()
            self.assertTrue(data.TransferAttempted)
            self.assertFalse(ctx["s_TrustedTransferEnabled"])
            self.assertFalse(run())
            self.assertEqual(state.quantity, f32(1000.))
            self.assertEqual(state.liters, f32(29.5))
            self.locks.Purge(10101)
            self.assertFalse(data.LockHeld)

    def test_destination_changes_and_native_rounding_fail_closed(self):
        state, data, events, ctx, run = self.transfer_fixture()
        state.after_debit = lambda: setattr(state, "quantity", f32(1250.))
        self.assertFalse(run())
        self.assertEqual([e[0] for e in events if e[0] != "report"], ["debit"])
        self.assertEqual(state.quantity, f32(1250.))
        self.locks.Clear()
        state, data, events, ctx, run = self.transfer_fixture()
        data.PlannedMl = f32(.01)
        self.assertFalse(run())
        self.assertFalse(any(e[0] == "credit" for e in events))

    def test_fresh_destination_capacity_bounds_credit_without_refunding_loss(self):
        state, data, events, ctx, run = self.transfer_fixture()
        state.after_debit = lambda: setattr(state, "maximum", f32(1025.))
        self.assertFalse(run())
        self.assertEqual(data.RequestedCreditMl, f32(25.))
        self.assertEqual(state.quantity, f32(1025.))
        self.assertEqual(state.liters, f32(29.5))

    def test_debit_can_empty_finite_source_and_never_uses_decorative_wreck(self):
        state, data, events, ctx, run = self.transfer_fixture(liters=f32(.5))
        self.assertTrue(run())
        self.assertEqual(state.liters, f32(0.))
        self.assertEqual(state.quantity, f32(1500.))
        self.assertIn("CarScript.Cast", body(str(SOURCE), "ValidateLive"))

    def test_wrong_liquid_excess_debit_or_expired_lease_after_debit_never_credits(self):
        for name in ("liquid", "debit", "lease"):
            state, data, events, ctx, run = self.transfer_fixture()
            if name == "liquid": state.after_debit = lambda: setattr(state, "liquid", 512)
            if name == "debit": state.after_debit = lambda: setattr(state, "liters", f32(28.))
            if name == "lease": state.after_debit = lambda: setattr(state, "now", 12000)
            self.assertFalse(run())
            self.assertFalse(any(e[0] == "credit" for e in events), name)
            self.locks.Clear()
