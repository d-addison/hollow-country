"""Native binding contracts plus authored admission decisions, not engine proof."""
import re
import unittest
from tests.legacy.test_ecology_runtime import ROOT, environment

class EcologyNativeTests(unittest.TestCase):
    def test_stock_hooks_chain_and_unregister(self):
        source=(ROOT/"4_World/Ecology/HCEcologyHooks.c").read_text()
        # Infected are not ecology actors: they would consume the shared actor cap.
        self.assertNotIn("modded class ZombieBase",source)
        for name in ("AnimalBase","ItemBase","Well"):
            match=re.search(r"modded class "+name+r"\s*\{([\s\S]*?)(?=\nmodded class|\Z)",source)
            self.assertIsNotNone(match,name)
            block=match[0]
            self.assertIn("super.EEInit();",block)
            self.assertIn("super.EEDelete(parent);",block)
            self.assertIn("HCEcologyRuntime.Register(this",block)
            self.assertIn("HCEcologyRuntime.Unregister(this)",block)
    def test_native_resource_reads_fresh_object_and_inventory_parent(self):
        source=(ROOT/"4_World/Ecology/HCEcologyNative.c").read_text()
        for call in ("GetHierarchyParent()","IsRuined()","GetQuantity()","GetLiquidType()",
                     "GetWaterSourceObjectType()","GetPosition()","GetType()"):
            self.assertIn(call,source)
        self.assertNotIn("GetNetworkID",source)
    def test_path_uses_inspected_world_filter_and_real_result(self):
        source=(ROOT/"4_World/Ecology/HCEcologyNative.c").read_text()
        for call in ("GetAIWorld()","SampleNavmeshPosition(","FindPath(","PGFilter",
                     "path.Count() > 64","vector.Distance(","PGPolyFlags.WALK"):
            self.assertIn(call,source)
        self.assertIn("HCEcologyRuntimeRules.PositionValid",source)
    def test_adapter_never_steals_group_or_claims_unsupported_animal_route(self):
        source=(ROOT/"4_World/Ecology/HCEcologyNative.c").read_text()
        for forbidden in ("AddAgent(","RemoveAgent(","StartCommand_","OverrideMovement",
                          "SetWaypoints(","DestroyAIAgent(","SetKeepInIdle("):
            self.assertNotIn(forbidden,source)
        self.assertIn("capabilities.SupportsAnimalNavigation = false",source)
        self.assertIn("capabilities.SupportsInfectedNavigation = false",source)
        self.assertIn("return false;",source[source.index("static bool Submit("):])
    def test_path_endpoint_and_length_checks(self):
        e=environment();r=e["HCEcologyRuntimeRules"]
        self.assertTrue(r.PathSummaryValid(2,10.,0.,120.))
        for count,length,gap in ((1,10.,0.),(65,10.,0.),(2,241.,0.),
                                 (2,10.,5.),(2,float("nan"),0.),(2,10.,float("inf"))):
            self.assertFalse(r.PathSummaryValid(count,length,gap,120.))
    def test_resource_registry_explicit_overflow_not_full_world_claim(self):
        text=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        self.assertIn("coverage partial",text)
        self.assertIn("registration overflow",text)
        self.assertNotIn("GetObjectsAtPosition",text)
        self.assertIn("SurfaceIsPond",text)
    def test_native_metadata_never_promotes_path_to_acceptance(self):
        data=(ROOT/"3_Game/Ecology/HCEcologyRuntimeData.c").read_text()
        self.assertIn("bool MovementAccepted = false;",data)
        source=(ROOT/"4_World/Ecology/HCEcologyRuntime.c").read_text()
        self.assertNotIn("MovementAccepted = true",source)
        self.assertIn("resource presence is not sensory eligibility",source)


class EcologyNativeResourceBehaviorTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        from tests.legacy.test_ecology_runtime import translated
        self.e=environment()
        class Handle:
            def __init__(self):
                self.quantity=5.;self.parent=None;self.ruined=False;self.position=[0.,0.,0.]
                self.food=True;self.liquid=0;self.well=0;self.deleted=False
            def IsPendingDeletion(self):return self.deleted
            def GetPosition(self):return self.position
            def GetHierarchyParent(self):return self.parent
            def IsRuined(self):return self.ruined
            def GetWaterSourceObjectType(self):return self.well
            def IsLiquidContainer(self):return bool(self.liquid)
            def GetLiquidType(self):return self.liquid
            def IsFood(self):return self.food
            def HasQuantity(self):return True
            def GetQuantity(self):return self.quantity
        self.handle=Handle()
        self.e["ItemBase"]=SimpleNamespace(Cast=lambda h:h)
        self.e["Edible_Base"]=SimpleNamespace(Cast=lambda h:None)
        self.e["EWaterSourceObjectType"]=SimpleNamespace(WELL=1)
        self.e["LIQUID_WATER"]=512;self.e["LIQUID_CLEANWATER"]=4194304
        self.authority=True
        self.e["HCEcologyNative"]=SimpleNamespace(Authority=lambda:self.authority)
        text=(ROOT/"4_World/Ecology/HCEcologyNative.c").read_text()
        self.sample=translated(text,"SampleResource",self.e,"HCEcologyNative")
    def test_reads_current_quantity_and_parent_on_every_observation(self):
        self.assertEqual(1,self.sample(self.handle))
        self.handle.quantity=0.
        self.assertEqual(0,self.sample(self.handle))
        self.handle.quantity=5.;self.handle.parent=object()
        self.assertEqual(0,self.sample(self.handle))
        self.handle.parent=None
        self.assertEqual(1,self.sample(self.handle))
    def test_clean_and_base_water_are_observations_not_consumed(self):
        self.handle.food=False
        for liquid in (512,4194304):
            self.handle.liquid=liquid
            self.assertEqual(2,self.sample(self.handle))
            self.assertEqual(5.,self.handle.quantity)
        self.handle.liquid=123
        self.assertEqual(0,self.sample(self.handle))
    def test_no_client_ruined_deleted_or_nonfinite_resource_observation(self):
        self.authority=False;self.assertEqual(0,self.sample(self.handle));self.authority=True
        self.handle.ruined=True;self.assertEqual(0,self.sample(self.handle));self.handle.ruined=False
        self.handle.deleted=True;self.assertEqual(0,self.sample(self.handle));self.handle.deleted=False
        self.handle.position=[0.,float("nan"),0.]
        self.assertEqual(0,self.sample(self.handle))

    def test_actor_death_hook_retires_registration_without_waiting_for_corpse_delete(self):
        from tests.legacy.test_ecology_runtime import translated
        from types import SimpleNamespace
        text=(ROOT/"4_World/Ecology/HCEcologyHooks.c").read_text()
        for name in ("AnimalBase",):
            fragment=re.search(r"modded class "+name+r"\s*\{([\s\S]*?)(?=\nmodded class|\Z)",text)[0]
            self.assertIn("super.EEKilled(killer);",fragment)
            self.assertIn("override void EEKilled(Object killer)",fragment)
            trace=[]
            actor=SimpleNamespace(m_HCEcoRegistered=True)
            env=environment()
            env["super"]=SimpleNamespace(EEKilled=lambda killer:trace.append(("native",killer)))
            env["HCEcologyRuntime"]=SimpleNamespace(Unregister=lambda entity:trace.append(("unregister",entity)))
            executed=translated(fragment,"EEKilled",env,"HCEcologyHooks",True)
            executed(actor,"synthetic-killer")
            self.assertEqual([("unregister",actor),("native","synthetic-killer")],trace)
            # Unbound (never admitted) entities skip the registry walk entirely.
            trace.clear(); executed(actor,"again")
            self.assertEqual([("native","again")],trace)

    def test_hooks_bind_once_and_only_bound_entities_unregister(self):
        from tests.legacy.test_ecology_runtime import translated
        from types import SimpleNamespace
        text=(ROOT/"4_World/Ecology/HCEcologyHooks.c").read_text()
        for name,actor in (("AnimalBase",True),("ItemBase",False),("Well",False)):
            fragment=re.search(r"modded class "+name+r"\s*\{([\s\S]*?)(?=\nmodded class|\Z)",text)[0]
            trace=[]; accept=[True]
            env=environment()
            env["super"]=SimpleNamespace(EEInit=lambda:trace.append("native-init"),
                                         EEDelete=lambda parent:trace.append("native-delete"))
            env["HCEcologyRuntime"]=SimpleNamespace(
                Register=lambda entity,kind:trace.append(("register",kind)) or accept[0],
                Unregister=lambda entity:trace.append("unregister"))
            # Synthetic HC-15 observation registry; its own tests cover it.
            env["HCWildlifeObservation"]=SimpleNamespace(HCRegister=lambda entity:True,
                                                         HCUnregister=lambda entity:None)
            init=translated(fragment,"EEInit",env,"HCEcologyHooks",True)
            delete=translated(fragment,"EEDelete",env,"HCEcologyHooks",True)
            entity=SimpleNamespace(m_HCEcoRegistered=False)
            init(entity); init(entity)
            self.assertEqual(["native-init",("register",actor),"native-init"],trace,name)
            delete(entity,None); delete(entity,None)
            self.assertEqual(["unregister","native-delete","native-delete"],trace[3:],name)
            # A refused (full/ineligible) registration leaves deletes walk-free.
            trace.clear(); accept[0]=False
            other=SimpleNamespace(m_HCEcoRegistered=False)
            init(other); delete(other,None)
            self.assertEqual(["native-init",("register",actor),"native-delete"],trace,name)
