"""V1 policy execution with explicit synthetic inventory; never engine proof."""
from types import SimpleNamespace as NS
import unittest

from tests.legacy.test_crafting_families import source_policy, state_for
from tests.legacy.test_salvage_tools import SyntheticItem


class V1LeatherTests(unittest.TestCase):
    def test_all_small_garment_colours_share_one_panel_policy_and_retain_containers(self):
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        policy = source_policy()
        for kind in tuple(f'{item}_{colour}' for item in ('LeatherGloves', 'LeatherHat')
                          for colour in ('Beige', 'Black', 'Brown', 'Natural')):
            with self.subTest(kind=kind):
                from tests.legacy.test_salvage_tools import authored
                configured_args=[]
                authored('Init','',{},owner='HCRecoverMediumLeather')(
                    NS(Configure=lambda *args:configured_args.append(args)))
                self.assertEqual(('TannedLeather',1,5),configured_args[0][3:6])
                self.assertTrue(policy.AllowsSource('HCRecoverMediumLeather', kind))
                state = state_for('HCRecoverMediumLeather')
                material, tool = SyntheticItem(kind, actor, 50), SyntheticItem('KitchenKnife', actor, 6)
                pair = [material, tool]
                original_health = tool.health
                self.assertTrue(state.CanDo(pair, actor))
                self.assertIs(pair[1], tool)
                self.assertEqual(original_health, tool.health)
                self.assertEqual(['TannedLeather'], state.m_ItemsToCreate)
                self.assertEqual([1], state.m_ResultSetQuantity)
                self.assertEqual([0, -5], state.m_IngredientAddHealth)
                for cargo, attachments, worn in ((1, 0, False), (0, 1, False), (0, 0, True)):
                    material.inventory = NS(IsAttachment=lambda: worn,
                                            AttachmentCount=lambda: attachments,
                                            GetCargo=lambda: NS(GetItemCount=lambda: cargo))
                    self.assertFalse(state.CanDo(pair, actor))
                    self.assertIs(pair[1], tool)
                    self.assertEqual(original_health, tool.health)
                    self.assertFalse(material.deleted)



class V1CommitAuthorityTests(unittest.TestCase):
    def test_non_server_perform_recipe_never_calls_native_or_mutates_ingredients(self):
        from tests.legacy.test_salvage_tools import authored
        for server in (False, True):
            actor=object(); material=SyntheticItem('LeatherHat_Black',actor,50)
            tool=SyntheticItem('KitchenKnife',actor,10);events=[]
            state=NS(m_HCOutputReady=True,
                     m_HCCommitGuard=NS(TryEnter=lambda:events.append('enter') or True,
                                        Release=lambda:events.append('release')))
            def perform(source, cutter, player):
                events.append('native')
                self.assertIs(material,source);self.assertIs(tool,cutter);self.assertIs(actor,player)
                source.deleted=True;cutter.health-=5
            state.native=NS(PerformRecipe=perform)
            call=authored('PerformRecipe','item1,item2,player',{'GetGame':lambda:NS(IsServer=lambda:server)})
            call(state,material,tool,actor)
            self.assertEqual(['enter','native','release'] if server else [],events)
            self.assertEqual(server,material.deleted)
            self.assertEqual(5 if server else 10,tool.health)
            self.assertEqual(not server,state.m_HCOutputReady)


class V1DecisionTableTests(unittest.TestCase):
    def audit(self, rows):
        from tools.audit.item_utility import build_audit
        from tests.unit.test_item_utility import censuses
        craft,actions=censuses()
        return build_audit(rows,craft,actions,{'fixture':'SYNTHETIC crafting decision test'})['decision_table']

    def test_every_exact_recovery_source_has_implemented_recipe_and_evidence(self):
        import json
        from tests.legacy.test_crafting_contract import FIXTURE
        from tests.legacy.test_crafting_families import FAMILIES
        from tests.unit.test_item_utility import row
        fixture=json.loads(FIXTURE.read_text())
        expected={}
        policy=source_policy()
        for recipe in fixture['pilots']:
            sources=[policy.SourceAt(recipe['input'],i)
                     for i in range(policy.SourceCount(recipe['input']))]
            self.assertTrue(sources)
            for source in sources:expected.setdefault(source,set()).add(recipe['class'])
        table=self.audit([row(name) for name in expected] + [row('Unknown'),row('LeatherHat_Black','CfgAmmo')])
        by_id={r['id']:r for r in table['config_classes']}
        for source,recipes in expected.items():
            with self.subTest(source=source):
                record=by_id['CfgVehicles:'+source]
                self.assertEqual('hc-recovery',record['material_conversion'])
                implemented=[d for d in record['hc_decisions'] if d['status']=='implemented']
                self.assertEqual(recipes,{d['recipe'] for d in implemented})
                self.assertEqual(len(recipes),len(implemented))
                for decision in implemented:
                    self.assertIn(decision['evidence_id'],fixture['v1_decision_evidence'])
                    self.assertEqual('pending',decision['runtime_acceptance'])
                self.assertEqual('NOT_EVALUATED',record['inventory_eligibility'])
        for identity in ('CfgVehicles:Unknown','CfgAmmo:LeatherHat_Black'):
            self.assertEqual('UNKNOWN',by_id[identity]['material_conversion'])
            self.assertEqual([],by_id[identity]['hc_decisions'])
        self.assertFalse(table['runtime_qualified']);self.assertFalse(table['production_enablement'])

    def test_single_unit_ruined_exclusions_are_exact_and_evidence_backed(self):
        from tests.legacy.test_crafting_families import MEDIUM
        from tests.unit.test_item_utility import row
        table=self.audit([row(name) for name in MEDIUM+['BarbedBaseballBat']])
        for record in table['config_classes']:
            exclusions=[d for d in record['hc_decisions'] if d['status']=='excluded']
            self.assertEqual(1,len(exclusions))
            self.assertEqual('ruined-only',exclusions[0]['condition'])
            self.assertIn('single-unit',exclusions[0]['reason'])
            self.assertTrue(exclusions[0]['evidence_id'])

    def test_empty_and_nonpositive_repair_cohorts_are_excluded_from_extension(self):
        from tests.unit.test_item_utility import row,field
        table=self.audit([row('Empty',fields=[field('repairableWithKits')]),
                          row('Nonpositive',fields=[field('repairableWithKits',[0,-1])])])
        self.assertEqual(['exclude-regular-kit-extension']*2,[r['repair'] for r in table['config_classes']])


if __name__ == '__main__':
    unittest.main()
