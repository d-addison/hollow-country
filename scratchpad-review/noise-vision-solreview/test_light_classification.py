"""Synthetic regression, executing the authored LitItem body with native-shape stubs.

Class ancestry and IsLightSource defaults are taken from the pinned native cache.
No rendered light, DayZ object, perception or runtime behaviour is simulated as proof.
The default run should FAIL on two omitted native light classes. --fixed tests a
minimal candidate change written only to scratch, and should pass.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tests.unit.test_crafting_completion import execute_flat
from tests.unit.test_v1_native_noise_vision import VISION


class SyntheticItem:
    def __init__(self, kind, working, native_light_source=False):
        self.kind = kind
        self.working = working
        self.native_light_source = native_light_source

    def IsLightSource(self):
        return self.native_light_source

    def IsIgnited(self):
        return self.working


class SyntheticCast:
    def __init__(self, kind):
        self.kind = kind

    def Cast(self, item):
        return item if item and item.kind == self.kind else None


source = VISION
if "--fixed" in sys.argv:
    sys.argv.remove("--fixed")
    source = OUT / "candidate_fix" / VISION.name
    source.parent.mkdir(exist_ok=True)
    old = "Flashlight.Cast(item) != null || Roadflare.Cast(item) != null || FlammableBase.Cast(item) != null"
    new = old + " || Chemlight_ColorBase.Cast(item) != null || PortableGasLamp.Cast(item) != null"
    content = VISION.read_text()
    assert content.count(old) == 1
    source.write_text(content.replace(old, new))

context = {kind: SyntheticCast(kind) for kind in (
    "Flashlight", "Roadflare", "FlammableBase", "Chemlight_ColorBase", "PortableGasLamp")}
lit_item = execute_flat(str(source), "LitItem", "item", context)


class NativeLightClassification(unittest.TestCase):
    def test_working_chemlight_is_lit(self):
        self.assertTrue(lit_item(SyntheticItem("Chemlight_ColorBase", True)))

    def test_working_gas_lamp_is_lit(self):
        self.assertTrue(lit_item(SyntheticItem("PortableGasLamp", True)))

    def test_existing_light_kinds_and_dark_items(self):
        self.assertFalse(lit_item(None))
        for kind, native in (("Flashlight", False), ("Roadflare", False),
                             ("FlammableBase", False), ("Headtorch_ColorBase", True),
                             ("UniversalLight", True), ("TLRLight", True)):
            self.assertTrue(lit_item(SyntheticItem(kind, True, native)), kind)
            self.assertFalse(lit_item(SyntheticItem(kind, False, native)), kind)
        self.assertFalse(lit_item(SyntheticItem("NonLight", True)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
