"""C06: execute restricted authored methods using explicit synthetic native DTOs.

This is not an Enforce compiler, inventory engine or native acceptance evidence.
"""
from pathlib import Path
import re
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "mods/HollowCountry/scripts/4_World/Crafting"
PILOTS = (
    ("HCSalvageCamoNet", "CamoNet", "KitchenKnife", "Netting", 1, 5),
    ("HCSalvageCableReel", "CableReel", "Pliers", "MetalWire", 1, 5),

)


def body(filename, method, owner=None):
    source = (SRC / filename).read_text()
    if owner:
        source = re.split(r'^(?:modded )?class '+re.escape(owner)+r'\b',source,flags=re.M)[1]
        source = re.split(r'^class ',source,flags=re.M)[0]
    match = re.search(r"^\s*(?:(?:static|override|protected)\s+)*\w+\s+" + method + r"\([^;\n]*\)\s*\{", source, re.M)
    if not match:
        raise AssertionError("missing authored method: " + method)
    start = match.end()
    end, depth = start, 1
    while depth:
        if source[end] == "{": depth += 1
        if source[end] == "}": depth -= 1
        end += 1
    return source[start:end - 1]


def execute_flat(filename, method, params, context):
    """Admit only the flat if/return/assignment method subset used by these checks."""
    source = re.sub(r"//[^\n]*", "", body(filename, method))
    if "{" in source or "}" in source:
        raise AssertionError("unsupported nested control flow: " + method)
    lines = []
    for statement in source.split(";"):
        statement = statement.strip()
        if not statement: continue
        statement = re.sub(r"\bnew (\w+)\b", r"\1()", statement)
        statement = re.sub(r"\b\w+ (\w+) =", r"\1 =", statement)
        statement = re.sub(r"([\w.]+(?:\[[^\]\n]+\])?)\.Count\(\)", r"len(\1)", statement)
        statement = statement.replace("&&", " and ").replace("||", " or ")
        statement = re.sub(r"!(?!=)", "not ", statement)
        for original, translated in (("true", "True"), ("false", "False"), ("null", "None")):
            statement = re.sub(r"\b" + original + r"\b", translated, statement)
        statement = re.sub(r"^if \((.*)\)\s+(.*)$", r"if \1: \2", statement, flags=re.S)
        lines.append("    " + statement.replace("\n", " "))
    code = "def actual(" + params + "):\n" + "\n".join(lines)
    namespace = dict(context)
    exec(compile(code, "authored-enforce-crafting:" + method, "exec"), namespace)
    return namespace["actual"]


def recipe(pilot, recipe_id=0):
    try:
        from tests.legacy.test_salvage_tools import tool_policy, NativeArray
    except ImportError:
        from tests.legacy.test_salvage_tools import tool_policy, NativeArray
    name, material, tool, result, quantity, wear = pilot
    from tests.legacy.test_crafting_families import FAMILIES
    family = FAMILIES.get(name)
    sources = family[0] if family else [material]
    outputs = family[2] if family else [(result,quantity)]
    animation = family[4] if family else 2
    ruined = family[5] if family else False
    policy = tool_policy()
    tools = NativeArray(policy.ToolAt(tool, i) for i in range(policy.ToolCount(tool)))
    return SimpleNamespace(
        m_NumberOfResults=len(outputs), m_ItemsToCreate=[n for n,q in outputs],
        m_Ingredients=[NativeArray(sources), tools], m_IngredientDestroy=[True, False],
        m_IngredientAddHealth=[0, -wear], m_ResultSetQuantity=[q for n,q in outputs],
        m_ResultToInventory=[-1]*len(outputs), m_ResultInheritsHealth=[0]*len(outputs),
        m_ResultSetFullQuantity=[False]*len(outputs), m_ResultReplacesIngredient=[-1]*len(outputs),
        m_ResultInheritsColor=[-1]*len(outputs), m_ResultSetHealth=[-1]*len(outputs),
        m_IngredientAddQuantity=[0, 0], m_IngredientSetHealth=[-1, -1],
        IsInstaRecipe=lambda: False, IsRepeatable=lambda: False,
        IsRecipeAnywhere=lambda: False, GetLengthInSecs=lambda: animation*4, GetSpecialty=lambda:0,
        m_ResultUseSoftSkills=[False]*len(outputs),m_IngredientUseSoftSkills=[False,False],
        m_MinDamageIngredient=[4 if ruined else -1,-1],m_MaxDamageIngredient=[4 if ruined else 3,3],
        ClassName=lambda: name, GetID=lambda: recipe_id,
    )


def audit_context():
    try:
        from tests.legacy.test_salvage_tools import tool_policy
    except ImportError:
        from tests.legacy.test_salvage_tools import tool_policy
    from tests.legacy.test_crafting_families import FAMILIES, source_policy
    from tests.legacy.test_salvage_tools import authored, NativeArray
    all_definitions = PILOTS + tuple((n,n,t,o[0][0],o[0][1],w) for n,(sources,t,o,w,a,r) in FAMILIES.items())
    cached = [recipe(pilot, index) for index, pilot in enumerate(all_definitions)]
    names = {pilot[0]: index for index, pilot in enumerate(all_definitions)}
    plugin = SimpleNamespace(RecipeIDFromClassname=lambda name: names.get(name, -1), Cast=lambda value: value)
    game = SimpleNamespace(ConfigIsExisting=lambda path: True, ConfigGetInt=lambda path: 2,
                           ConfigGetFloat=lambda path: 8)
    context = {"GetGame": lambda: game, "PluginRecipesManager": plugin,
               "HCSalvageTools": tool_policy(game), "HCSalvageSources":source_policy(),
               "CheckCompletionGuard": lambda: True,
               "m_RecipeList": cached, "RecipeIDFromClassname": plugin.RecipeIDFromClassname}
    manager = SimpleNamespace()
    lookup = SRC / "HCCraftingRegistryAudit.c"
    if lookup.exists():
        manager.HCGetRegisteredSalvage = execute_flat(lookup.name, "HCGetRegisteredSalvage", "className", context)
    context["GetPlugin"] = lambda kind: manager
    for pilot in PILOTS:
        context[pilot[0]] = lambda p=pilot: recipe(p)
    context["CheckDefinition"] = execute_flat("HCCraftingNativeChecks.c", "CheckDefinition", "recipe,className,inputType,toolType,outputType,quantity,wear", context)
    recovery = authored('CheckRecovery','recipe,className,toolType,firstOutput,firstQuantity,secondOutput,secondQuantity,wear,animationUnits,ruinedOnly',context,'HCCraftingNativeChecks.c')
    context['CheckRecovery']=lambda *args:recovery(None,*args)
    context["run"] = execute_flat("HCCraftingNativeChecks.c", "Run", "", context)
    return cached, names, manager, context


class CraftingCompletionTests(unittest.TestCase):
    def test_core_startup_failure_cannot_leave_salvage_admitted(self):
        core = SimpleNamespace(IsStarted=lambda: False, GetSettings=lambda: SimpleNamespace(EnableCrafting=True))
        game = SimpleNamespace(IsServer=lambda: True)
        call = execute_flat("HCCraftingModule.c", "CanPreviewOrCraft", "", {
            "GetGame": lambda: game, "HCServer": SimpleNamespace(Get=lambda: core),
            "m_Started": True, "m_Validated": True,
        })
        self.assertFalse(call(), "module admission must not outlive failed or stopped core startup")

    def test_live_core_setting_and_module_admission_are_all_required(self):
        for core_started in (False, True):
            for module_started in (False, True):
                for validated in (False, True):
                    for enabled in (False, True):
                        core = SimpleNamespace(IsStarted=lambda: core_started, GetSettings=lambda: SimpleNamespace(EnableCrafting=enabled))
                        call = execute_flat("HCCraftingModule.c", "CanPreviewOrCraft", "", {
                            "GetGame": lambda: SimpleNamespace(IsServer=lambda: True),
                            "HCServer": SimpleNamespace(Get=lambda: core),
                            "m_Started": module_started, "m_Validated": validated,
                        })
                        self.assertEqual(call(), core_started and module_started and validated and enabled)

    def test_client_preview_does_not_require_server_profile_or_core(self):
        def forbidden(): raise AssertionError("client preview touched server core")
        call = execute_flat("HCCraftingModule.c", "CanPreviewOrCraft", "", {
            "GetGame": lambda: SimpleNamespace(IsServer=lambda: False),
            "HCServer": SimpleNamespace(Get=forbidden), "m_Started": False, "m_Validated": False,
        })
        self.assertTrue(call())

    def test_audit_checks_mutated_cached_recipe_instead_of_new_pristine_instance(self):
        cached, names, manager, context = audit_context()
        self.assertTrue(context["run"]())
        cached[0].m_ResultSetQuantity[0] = 200
        self.assertFalse(context["run"](), "fresh defaults must not hide an incompatible cached recipe")

    def test_registry_lookup_rejects_missing_and_out_of_bounds_ids(self):
        cached, names, manager, context = audit_context()
        self.assertTrue(hasattr(manager, "HCGetRegisteredSalvage"), "bounded registered-instance lookup required")
        self.assertIs(manager.HCGetRegisteredSalvage(PILOTS[1][0]), cached[1])
        for value in (-1, 8, 2048, 2147483647):
            names[PILOTS[0][0]] = value
            self.assertIsNone(manager.HCGetRegisteredSalvage(PILOTS[0][0]))

    def test_registry_lookup_rejects_name_id_and_pointer_mismatches(self):
        cached, names, manager, context = audit_context()
        self.assertTrue(hasattr(manager, "HCGetRegisteredSalvage"))
        cached[0] = None
        self.assertIsNone(manager.HCGetRegisteredSalvage(PILOTS[0][0]))
        cached[0] = recipe(PILOTS[1], 0)
        self.assertIsNone(manager.HCGetRegisteredSalvage(PILOTS[0][0]))
        cached[0] = recipe(PILOTS[0], 2)
        self.assertIsNone(manager.HCGetRegisteredSalvage(PILOTS[0][0]))

    def test_missing_recipe_manager_disables_native_admission(self):
        cached, names, manager, context = audit_context()
        context["GetPlugin"] = lambda kind: None
        call = execute_flat("HCCraftingNativeChecks.c", "Run", "", context)
        self.assertFalse(call())

    def assert_cached_mutation_rejected(self, field, index, value):
        for pilot_index, pilot in enumerate(PILOTS):
            with self.subTest(recipe=pilot[0], field=field, value=value):
                cached, names, manager, context = audit_context()
                self.assertTrue(context["run"]())
                getattr(cached[pilot_index], field)[index] = value
                self.assertFalse(context["run"](), "native override admitted: " + field)

    def test_cached_full_quantity_cannot_override_fixed_output_yield(self):
        self.assert_cached_mutation_rejected("m_ResultSetFullQuantity", 0, True)

    def test_cached_replacement_cannot_transfer_quantity_over_fixed_yield(self):
        for ingredient in (0, 1):
            self.assert_cached_mutation_rejected("m_ResultReplacesIngredient", 0, ingredient)

    def test_cached_inherited_color_cannot_change_spawn_class(self):
        for ingredient in (0, 1):
            self.assert_cached_mutation_rejected("m_ResultInheritsColor", 0, ingredient)

    def test_cached_tool_quantity_mutation_cannot_follow_health_wear(self):
        for delta in (-1, 1):
            self.assert_cached_mutation_rejected("m_IngredientAddQuantity", 1, delta)

    def test_native_destroy_precedence_still_requires_source_only_consumption(self):
        self.assert_cached_mutation_rejected("m_IngredientDestroy", 0, False)
        self.assert_cached_mutation_rejected("m_IngredientDestroy", 1, True)

    def test_source_health_inheritance_cannot_be_replaced_or_averaged(self):
        for source in (-2, -1, 1):
            self.assert_cached_mutation_rejected("m_ResultInheritsHealth", 0, source)

    def test_shadowed_native_health_and_destroyed_source_modifiers_are_inactive(self):
        cached, names, manager, context = audit_context()
        # Native inherited source health follows SetHealth; salvage Do then applies
        # its 0.75 source factor. AddHealth wins over tool SetHealth. Destroy wins
        # over all source health/quantity modifiers. These are not active overrides.
        for registered in cached:
            registered.m_ResultSetHealth[0] = 100
            registered.m_IngredientSetHealth[:] = [100, 100]
            registered.m_IngredientAddHealth[0] = 100
            registered.m_IngredientAddQuantity[0] = 100
        self.assertTrue(context["run"]())


if __name__ == "__main__":
    unittest.main()
