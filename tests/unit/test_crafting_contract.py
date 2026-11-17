"""Offline source contracts and synthetic graph algebra. Never native proof."""
from collections import Counter, deque
from copy import deepcopy
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CRAFTING = ROOT / "mods/HollowCountry/scripts/4_World/Crafting"
FIXTURE = ROOT / "tests/fixtures/runtime/crafting-contract.json"


def declarations(source):
    pattern = (r'class (HCSalvage\w+) extends HCSalvageRecipe\s*\{\s*'
               r'override void Init\(\)\s*\{\s*'
               r'Configure\("[^"]+", "([^"]+)", "([^"]+)", "([^"]+)", '
               r'(\d+), ([\d.]+), ([\d.]+)\);')
    keys = ("class", "input", "tool", "output", "quantity", "wear", "animation_units")
    return [dict(zip(keys, (cls, inp, tool, out, int(q), float(w), float(t))))
            for cls, inp, tool, out, q, w, t in re.findall(pattern, source)]


def ledger(items, weights):
    total = Counter()
    for item, count in items.items():
        if count < 0:
            raise ValueError("negative count")
        for material, weight in weights[item].items():
            total[material] += count * weight
    return total


def validate_graph(recipes, weights):
    for r in recipes:
        before, after = ledger(r["inputs"], weights), ledger(r["outputs"], weights)
        if any(after[k] > before[k] for k in after):
            raise ValueError("resource-positive conversion: " + r["name"])


class CraftingContractTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text())
        self.source = "\n".join(p.read_text() for p in sorted(CRAFTING.glob("*.c")))
        self.pilots = declarations(self.source)

    def graph(self):
        self.assertEqual(3, len(self.pilots), "three concrete native salvage recipes required")
        graph = deepcopy(self.fixture["native_boundary"])
        for recipe in graph:
            for field in ("inputs", "outputs"):
                recipe[field] = {self.fixture["aliases"].get(k, k):v for k,v in recipe[field].items()}
        graph.extend({"name":p["class"], "inputs":{p["input"]:1},
                      "outputs":{p["output"]:p["quantity"]}} for p in self.pilots)
        return graph

    def test_three_distinct_useful_pilots(self):
        self.assertEqual(self.fixture["pilots"], self.pilots)
        self.assertEqual(3, len({p["input"] for p in self.pilots}))
        self.assertEqual(3, len({p["output"] for p in self.pilots}))

    def test_typed_conservation_and_loss(self):
        validate_graph(self.graph(), self.fixture["materials"])
        for p in self.pilots:
            before = ledger({p["input"]:1}, self.fixture["materials"])
            after = ledger({p["output"]:p["quantity"]}, self.fixture["materials"])
            self.assertTrue(any(after[k] < before[k] for k in before))
            self.assertGreater(p["wear"], 0)
            self.assertGreater(p["animation_units"], 0)

    def test_audit_rejects_free_product_and_cross_material_alchemy(self):
        graph = self.graph()
        for mutation in ({"Netting":5}, {"MetalWire":1}, {"Netting":2,"BurlapStrip":1}):
            broken = deepcopy(graph)
            broken[-3]["outputs"] = mutation
            with self.assertRaises(ValueError):
                validate_graph(broken, self.fixture["materials"])
        broken = deepcopy(graph)
        broken[-1]["inputs"] = {}
        with self.assertRaises(ValueError):
            validate_graph(broken, self.fixture["materials"])

    def test_all_reachable_chains_in_boundary_graph_conserve_material(self):
        graph = self.graph()
        start = Counter(CamoNet=1, CableReel=1, LeatherBelt_ColorBase=1, LizardPelt=1, BurlapStrip=6)
        ceiling = ledger(start, self.fixture["materials"])
        freeze = lambda state: tuple(sorted((k,v) for k,v in state.items() if v))
        queue, seen = deque([start]), {freeze(start)}
        while queue:
            state = queue.popleft()
            current = ledger(state, self.fixture["materials"])
            self.assertTrue(all(current[k] <= ceiling[k] for k in current))
            for r in graph:
                if all(state[k] >= v for k,v in r["inputs"].items()):
                    nxt = state.copy()
                    nxt.subtract(r["inputs"])
                    nxt.update(r["outputs"])
                    key = freeze(nxt)
                    if key not in seen:
                        seen.add(key)
                        queue.append(nxt)
        self.assertGreater(len(seen), 50)

    def test_registration_is_identical_and_unconditional_on_both_peers(self):
        path = CRAFTING / "HCRecipeRegistration.c"
        self.assertTrue(path.exists(), "native client/server registration required")
        source = path.read_text()
        self.assertIn("modded class PluginRecipesManager", source)
        self.assertIn("override void RegisterRecipies()", source)
        self.assertNotRegex(source, r'\bif\s*\(')
        positions = [source.index("super.RegisterRecipies();")]
        positions += [source.index("RegisterRecipe(new " + p["class"] + ");") for p in self.fixture["pilots"]]
        self.assertEqual(sorted(positions), positions)

    def test_native_server_only_commit_and_explicit_recipe_fields(self):
        self.graph()
        for fragment in ("class HCSalvageRecipe extends RecipeBase", "if (!GetGame().IsServer())",
                         "super.PerformRecipe(item1, item2, player);",
                         "super.SpawnItems(ingredients, player, spawned_objects);",
                         "super.ApplyModificationsIngredients(sorted, player);",
                         "m_IngredientDestroy[0] = true;", "m_IngredientAddHealth[1] = -wear;",
                         "m_ResultSetQuantity[0] = quantity;", "m_ResultToInventory[0] = -1;",
                         "m_ResultInheritsHealth[0] = 0;", "m_ResultInheritsColor[0] = -1;",
                         "m_ResultReplacesIngredient[0] = -1;", "m_IngredientUseSoftSkills[i] = false;",
                         "m_ResultUseSoftSkills[0] = false;"):
            self.assertIn(fragment, self.source)
        self.assertNotRegex(self.source, r'\b(AddQuantity|CreateInInventory|CreateObjectEx|ObjectDelete|Delete|RPCSingleParam)\s*\(')

    def test_fail_closed_conditions_and_null_spawn_does_not_consume(self):
        self.graph()
        for fragment in ("!player.IsAlive()", "player.IsUnconscious()", "ingredients[0] == ingredients[1]",
                         "item.GetHierarchyRootPlayer() != player", "item.GetInventory().IsAttachment()",
                         "item.IsSetForDeletion()",
                         "item.GetInventory().AttachmentCount()", "cargo.GetItemCount()",
                         "ingredients[0].IsKindOf(m_HCInputType)",
                         'ingredients[1].GetHealth("", "") <= m_HCWear', "GetCompEM().IsPlugged()",
                         "GetCompEM().GetPluggedDevicesCount()", "super.CanDo(ingredients, player)"):
            self.assertIn(fragment, self.source)
        guard = re.search(r'override void ApplyModificationsIngredients\([^)]*\)\s*\{(.*?)\n    \}', self.source, re.S)
        self.assertIsNotNone(guard)
        self.assertLess(guard[1].index("!m_HCOutputReady"), guard[1].index("super.ApplyModificationsIngredients"))

    def test_server_setting_gates_completion_not_client_preview(self):
        self.graph()
        gate = re.search(r'static bool CanPreviewOrCraft\(\)\s*\{(.*?)\n    \}', self.source, re.S)
        self.assertIsNotNone(gate)
        self.assertRegex(gate[1], r'if \(!GetGame\(\).IsServer\(\)\)\s*return true;')
        for fragment in ("HCServer.Get().GetSettings()", "settings.EnableCrafting", "m_Started && m_Validated"):
            self.assertIn(fragment, gate[1])
        for fragment in ("class HCCraftingModule extends HCModule", "super.RegisterModules();",
                         "Register(new HCCraftingModule);", "HCCraftingNativeChecks.Run()"):
            self.assertIn(fragment, self.source)

    def test_condition_and_wear_cannot_be_positive_in_synthetic_chains(self):
        self.graph()
        match = re.search(r'GetHealth01\("", ""\) \* ([0-9.]+);', self.source)
        self.assertIsNotNone(match)
        factor = float(match[1])
        self.assertGreater(factor, 0)
        self.assertLess(factor, 1)
        for health in (0.01, 0.25, 0.5, 0.75, 1.0):
            current = health
            for _ in range(20):
                after = current * factor
                self.assertLess(after, current)
                current = after
        for pilot in self.pilots:
            for available in (pilot["wear"] + 0.01, 20, 100):
                self.assertGreater(available - pilot["wear"], 0)
                self.assertLess(available - pilot["wear"], available)

    def test_native_completion_guard_rejects_reentry_before_spawn(self):
        source = (CRAFTING / "HCSalvageRecipe.c").read_text()
        guard = re.search(r'override void PerformRecipe\([^)]*\)\s*\{(.*?)\n    \}', source, re.S)
        self.assertIsNotNone(guard)
        body = guard[1]
        self.assertIn("if (!m_HCCommitGuard.TryEnter())", body)
        self.assertLess(body.index("TryEnter()"), body.index("super.PerformRecipe"))
        self.assertLess(body.index("super.PerformRecipe"), body.index("m_HCCommitGuard.Release();"))
        checks = (CRAFTING / "HCCraftingNativeChecks.c").read_text()
        self.assertIn("if (!guard.TryEnter() || guard.TryEnter())", checks)
        self.assertIn("guard.Release();", checks)
        self.assertIn("CheckCompletionGuard()", checks)

    def test_acceptance_stays_pending(self):
        self.assertEqual("pending", self.fixture["runtime_acceptance"])
        self.assertIn("SYNTHETIC", self.fixture["evidence"])
        self.assertEqual(8, len(self.fixture["pending_scenarios"]))


if __name__ == "__main__":
    unittest.main()
