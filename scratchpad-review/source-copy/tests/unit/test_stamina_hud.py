"""Synthetic execution of authored HUD methods; not DayZ UI acceptance."""
from pathlib import Path
from types import SimpleNamespace as NS
import re
import math
import unittest
from tests.unit.test_group_ui import ui_member

ROOT = Path(__file__).resolve().parents[2] / "mods/HollowCountry"
SOURCE = ROOT / "scripts/5_Mission/Survival/HCStaminaHUD.c"


class StaminaHUDTests(unittest.TestCase):
    def test_layout_matches_authored_widget_bindings(self):
        layout = (ROOT / "gui/layouts/hc_stamina.layout").read_text()
        pairs = re.findall(
            r'(TextWidget|ProgressBarWidget)\.Cast\(mHCRoot\.FindAnyWidget\("([^"]+)"\)\)',
            SOURCE.read_text())
        self.assertEqual(len(pairs), 6)
        for kind, name in pairs:
            self.assertRegex(
                layout, r"\b" + kind + r"Class\s+" + re.escape(name) + r"\s*\{")

    def setUp(self):
        self.source = SOURCE.read_text()
        self.source = self.source.replace("float Percent(", "int Percent(")
        self.source = re.sub(
            r"\b(?:StaminaHandler|ProgressBarWidget|Mission|IngameHud|IngameHudVisibility)\s+(?=\w+\s*[=;])",
            "HCGroupNative ", self.source)
        self.reads, self.shown, self.bars, self.labels = [], [], [], {}
        self.weight_bars = []
        self.enabled, self.menu, self.alive, self.awake = True, None, True, True
        self.hud_flags = 0
        self.hud_visibility = NS(
            IsContextFlagActive=lambda flags: bool(self.hud_flags & flags))
        self.hud = NS(GetHudVisibility=lambda: self.hud_visibility)
        self.mission = NS(GetHud=lambda: self.hud)
        handler = NS(GetSyncedStamina=lambda: 40,
                     GetSyncedStaminaCap=lambda: 80, GetStaminaMax=lambda: 100)
        self.player = NS(
            IsAlive=lambda: self.alive, IsUnconscious=lambda: not self.awake,
            GetStaminaHandler=lambda: handler,
            GetPlayerLoad=lambda: self.reads.append("load") or 25000)
        self.unlinked = []
        self.state = NS(mHCViewer=self.player, mHCElapsed=0.25,
                        mHCRoot=NS(Show=self.shown.append,
                                   Unlink=lambda: self.unlinked.append(True)),
                        mHCBar=NS(SetCurrent=self.bars.append),
                        mHCWeightBar=NS(SetCurrent=self.weight_bars.append))
        for field in ("Load", "Stamina", "Penalty", "WeightScale"):
            setattr(self.state, "mHC" + field, NS(
                SetText=lambda text, key=field: self.labels.update({key: text})))
        def format_text(template, *values):
            for index, value in enumerate(values, 1):
                template = template.replace("%" + str(index), str(value))
            return template
        self.env = {
            "GetGame": lambda: NS(
                IsServer=lambda: False, GetPlayer=lambda: self.player,
                GetMission=lambda: self.mission,
                GetUIManager=lambda: NS(GetMenu=lambda: self.menu)),
            "PlayerBase": NS(Cast=lambda value: value),
            "IngameHud": NS(Cast=lambda value: value),
            "IngameHudVisibility": NS(HUD_HIDE_FLAGS=1 | 2 | 32 | 2048),
            "HCStaminaIntegration": NS(Enabled=lambda: self.enabled),
            "Math": NS(Clamp=lambda v, a, b: max(a, min(b, v)),
                       Round=round, Floor=math.floor),
            "string": NS(Format=format_text),
            "CfgGameplayHandler": NS(
                GetStaminaMinCap=lambda: 5,
                GetStaminaWeightLimitThreshold=lambda: 6000,
                GetStaminaKgToStaminaPercentPenalty=lambda: 1.75)}
        for name in ("Percent", "Hide", "Reset", "Update"):
            setattr(self.state, name, lambda *args, n=name: ui_member(
                self.source, n, self.state, self.env, *args))
        self.env["HCStaminaHUD"] = NS(Percent=self.state.Percent)
        self.state.Prepare = lambda: True

    def test_native_cached_units_and_bar(self):
        self.state.Update(0)
        self.assertEqual(self.reads, ["load"])
        self.assertEqual(self.bars, [50])
        self.assertIn("25", self.labels["Load"])
        self.assertIn("kg", self.labels["Load"])
        self.assertIn("units", self.labels["Stamina"])
        self.assertIn("6", self.labels["Penalty"])

    def test_updates_are_bounded_without_catchup(self):
        for delta in (0, .1, .1, .1, 30):
            self.state.Update(delta)
        self.assertEqual(len(self.reads), 3)

    def test_weight_bar_uses_native_capacity_floor(self):
        self.state.Update(0)
        self.assertEqual(len(self.weight_bars), 1)
        self.assertAlmostEqual(self.weight_bars[0], 2500 / 60.285714285714285)
        self.assertIn("minimum stamina capacity", self.labels["WeightScale"])
        self.assertNotIn("cached", self.labels["Load"])

    def test_zero_penalty_has_explicit_display_scale(self):
        cfg = self.env["CfgGameplayHandler"]
        cfg.GetStaminaKgToStaminaPercentPenalty = lambda: 0
        cfg.GetStaminaWeightLimitThreshold = lambda: 0
        self.state.Update(0)
        self.assertEqual(len(self.weight_bars), 1)
        self.assertAlmostEqual(self.weight_bars[0], 2500 / 30)
        self.assertIn("disabled", self.labels["WeightScale"])
        self.assertIn("display scale", self.labels["WeightScale"])

    def test_zero_floor_reference_uses_labeled_display_scale(self):
        cfg = self.env["CfgGameplayHandler"]
        cfg.GetStaminaMinCap = lambda: 100
        cfg.GetStaminaWeightLimitThreshold = lambda: 0
        self.state.Update(0)
        self.assertAlmostEqual(self.weight_bars[0], 2500 / 30)
        self.assertIn("minimum", self.labels["WeightScale"])
        self.assertIn("display scale", self.labels["WeightScale"])

    def test_large_valid_floor_reference_keeps_nonzero_weight_bar(self):
        self.env["CfgGameplayHandler"].GetStaminaKgToStaminaPercentPenalty = lambda: .05
        self.state.Update(0)
        self.assertAlmostEqual(self.weight_bars[-1], 25000 / 1906000 * 100)
        self.assertIn("1906", self.labels["WeightScale"])

    def test_adaptive_reference_handles_maximum_permitted_load(self):
        self.env["CfgGameplayHandler"].GetStaminaKgToStaminaPercentPenalty = lambda: 0
        self.player.GetPlayerLoad = lambda: 1000000
        self.state.Update(0)
        self.assertAlmostEqual(self.weight_bars[-1], 1000000 / 1010000 * 100)

    def test_native_hud_hide_and_disable_do_not_sample(self):
        for flag in (2, 1):  # Installed EHudContextFlags.HUD_HIDE / HUD_DISABLE.
            with self.subTest(flag=flag):
                self.hud_flags = flag
                self.state.Update(0)
                self.assertFalse(self.shown[-1])
                self.assertEqual(self.reads, [])

    def test_oversized_reference_does_not_claim_capacity_is_at_floor(self):
        self.env["CfgGameplayHandler"].GetStaminaKgToStaminaPercentPenalty = lambda: 1e-8
        self.state.Update(0)
        self.assertNotIn("Capacity already at minimum", self.labels["WeightScale"])
        self.assertIn("reference exceeds display range", self.labels["WeightScale"])
        self.assertAlmostEqual(self.weight_bars[-1], 25000 / 30000 * 100)

    def test_percent_preserves_distinct_load_and_reference_guards(self):
        self.assertAlmostEqual(self.state.Percent(1000000, 1000000000), .1)
        self.assertEqual(self.state.Percent(1000000, 1), 100)
        for current, reference in (
                (1000001, 1000000000), (1, 1000000001), (-1, 100),
                (1, 0), (1, -1), (float("nan"), 100),
                (1, float("nan")), (float("inf"), 100),
                (1, float("inf"))):
            with self.subTest(current=current, reference=reference):
                self.assertEqual(self.state.Percent(current, reference), 0)

    def test_native_hiding_is_immediate_and_resume_refreshes(self):
        self.state.Update(0)
        self.assertEqual(self.reads, ["load"])
        self.hud_flags = 2
        self.state.Update(.01)  # Gate must run even before next sample is due.
        self.assertFalse(self.shown[-1])
        self.assertEqual(self.reads, ["load"])
        self.hud_flags = 0
        self.player.GetPlayerLoad = lambda: self.reads.append("load") or 35000
        self.state.Update(0)
        self.assertTrue(self.shown[-1])
        self.assertEqual(self.reads, ["load", "load"])
        self.assertIn("35", self.labels["Load"])

    def test_unavailable_native_hud_context_hides_without_sampling(self):
        for field in ("mission", "hud", "hud_visibility"):
            with self.subTest(field=field):
                previous = getattr(self, field)
                setattr(self, field, None)
                self.state.Update(0)
                self.assertFalse(self.shown[-1])
                self.assertEqual(self.reads, [])
                setattr(self, field, previous)

    def test_quickbar_hide_alone_does_not_hide_stamina(self):
        self.hud_flags = 256  # EHudContextFlags.QUICKBAR_HIDE is independent.
        self.state.Update(0)
        self.assertTrue(self.shown[-1])
        self.assertEqual(self.reads, ["load"])

    def test_visibility_gates_do_not_sample(self):
        for field, value in (("enabled", False), ("menu", object()),
                             ("alive", False), ("awake", False),
                             ("player", None)):
            old = getattr(self, field)
            setattr(self, field, value)
            self.state.Update(1)
            self.assertFalse(self.shown[-1])
            setattr(self, field, old)
        self.assertEqual(self.reads, [])

    def test_reset_releases_widget_and_player(self):
        self.state.Reset()
        self.assertEqual(self.unlinked, [True])
        self.assertIsNone(self.state.mHCRoot)
        self.assertIsNone(self.state.mHCViewer)
