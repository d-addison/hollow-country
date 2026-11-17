"""Synthetic source-census behaviors; never native action/inventory evidence."""
import hashlib
import importlib
import io
import json
from pathlib import Path
import stat
import unittest
from unittest.mock import patch

from tests.unit.test_crafting_audit import MemoryTree


BASE = '''
class ActionBase {};
class ActionContinuousBase: ActionBase {};
class ActionInteractBase: ActionBase {};
class ItemBase {
 void AddAction(typename action);
 void RemoveAction(typename action);
 void SetActions() {};
};
class Unrelated {};
'''
ACTIONS = '''
class SyntheticUse: ActionContinuousBase {
 override bool ActionCondition(PlayerBase player) { return Allowed(player); }
};
class SyntheticUnused: ActionInteractBase {};
class ActionLookingName: Unrelated {};
'''
ITEMS = '''
class SyntheticTool: ItemBase {
 override void SetActions() {
  super.SetActions();
  AddAction(SyntheticUse);
#ifdef SYNTHETIC_FEATURE
  if (Allowed()) RemoveAction(SyntheticUse);
#endif
  AddAction(dynamicAction);
  other.AddAction(SyntheticUse);
  // AddAction(SyntheticUnused);
 }
 bool CanRepair(ItemBase kit) { return false; }
 void EEItemAttached(EntityAI item, string slot) {};
};
class SyntheticChild: SyntheticTool {};
'''


class ActionAuditTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('tools.audit.action_audit')
        self.fs = MemoryTree()
        self.tree = Path(__file__).resolve().parents[2] / '__synthetic_actions__'
        for boundary in (
            patch.object(Path, 'mkdir', lambda p,*a,**kw:self.fs.directory(p)),
            patch.object(Path, 'stat', lambda p,**kw:self.fs.metadata(p,**kw)),
            patch.object(Path, 'lstat', lambda p:self.fs.metadata(p,follow_symlinks=False)),
            patch.object(Path, 'resolve', lambda p,**kw:p.absolute()),
            patch.object(Path, 'open', lambda p,*a,**kw:self.fs.open(p,*a,**kw)),
            patch.object(self.module.crafting.os, 'scandir', self.fs.scandir),
            patch.object(self.module.crafting.os, 'fstat', lambda fd:self.fs.metadata(self.fs.handles[fd]))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.tree.mkdir()
        self.write('Base.c', BASE)
        self.write('Elsewhere/Actions.C', ACTIONS)
        self.write('Items.c', ITEMS)

    def write(self, name, value):
        p = self.tree / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value.encode() if isinstance(value,str) else value)
        return p

    def audit(self, **kwargs):
        return self.module.audit_tree(self.tree, **kwargs)

    def test_all_paths_declared_actions_and_inherited_paths_without_name_heuristics(self):
        r=self.audit(); self.assertTrue(r['valid'],r['diagnostics'])
        self.assertEqual([s['path'] for s in r['sources']],['Base.c','Elsewhere/Actions.C','Items.c'])
        actions={a['class']:a for a in r['actions']}
        self.assertIn('SyntheticUse', actions)
        self.assertNotIn('ActionLookingName',actions)
        self.assertEqual(actions['SyntheticUse']['path_kinds'],['continuous'])
        self.assertEqual(actions['SyntheticUnused']['path_kinds'],['interact'])
        self.assertEqual(actions['SyntheticUnused']['source_status'],'comment-disabled-only')
        self.assertTrue(all(a['runtime_status']=='UNKNOWN' for a in actions.values()))
        child=next(c for c in r['classes'] if c['class']=='SyntheticChild')
        self.assertIn('SyntheticTool',child['inherited_registration_sources'])
        self.assertEqual(child['effective_actions'],'UNKNOWN_NOT_EXECUTED')

    def test_registration_context_excludes_declarations_and_qualified_receivers(self):
        r=self.audit(); calls=r['bindings']
        self.assertEqual(len(calls),6)
        direct=next(b for b in calls if b['call']=='AddAction' and not b['disabled']
                    and b['receiver']=='implicit' and b['candidate']=='SyntheticUse')
        self.assertEqual(direct['owner_class'],'SyntheticTool')
        self.assertEqual(direct['action_resolution'],'declared')
        qualified=next(b for b in calls if b['receiver']=='qualified_unresolved')
        self.assertIsNone(qualified['owner_class'])
        self.assertEqual(qualified['enclosing_class'],'SyntheticTool')
        self.assertIn('receiver_not_resolved',qualified['unresolved'])
        dynamic=next(b for b in calls if b['candidate']=='dynamicAction')
        self.assertEqual(dynamic['action_resolution'],'missing_or_dynamic_identifier')
        self.assertIsNone(dynamic['action_class'])

    def test_preprocessor_runtime_controls_and_super_calls_are_retained_not_executed(self):
        r=self.audit(); remove=next(b for b in r['bindings'] if b['call']=='RemoveAction')
        self.assertEqual(remove['conditions'],['#ifdef SYNTHETIC_FEATURE'])
        method=next(m for m in r['methods'] if m['id']==remove['method_id'])
        self.assertIn('if',[c['kind'] for c in method['runtime_control_flow']])
        self.assertEqual(remove['runtime_conditions'],'NOT_EVALUATED')
        self.assertEqual(sum(b['call']=='SetActions' and b['receiver']=='super'
                             for b in r['bindings']),1)

    def test_native_callback_categories_and_declaration_only_surfaces_are_observations(self):
        self.write('Callbacks.c','''class Service {
          void OnConsume(); void OnFoodStageChange(int a,int b) {};
          int CookWithEquipment(ItemBase pot) { return 0; }
          void OnWasDetached(EntityAI parent,int slot) {};
        };''')
        r=self.audit(); methods=r['callbacks']
        self.assertEqual({c['category'] for c in methods},
                         {'repair','consume','cooking','attachment'})
        consume=next(c for c in methods if c['name']=='OnConsume')
        self.assertTrue(consume['declaration_only'])
        self.assertEqual(consume['owner_class'],'Service')

    def test_duplicates_cycles_and_missing_bases_remain_explicit(self):
        self.write('Ambiguous.c','''class Conflict:ActionBase {};
          class Conflict:Unrelated {}; class CycleA:CycleB {}; class CycleB:CycleA {};
          class MissingChild:Absent {}; class Holder:ItemBase {
            void SetActions(){AddAction(Conflict);AddAction(AbsentAction);}
          };''')
        r=self.audit(); classes={c['class']:c for c in r['classes']}
        self.assertIn('ambiguous_definition',classes['Conflict']['ancestry']['unresolved'])
        self.assertIn('cycle',classes['CycleA']['ancestry']['unresolved'])
        self.assertIn('missing_parent',classes['MissingChild']['ancestry']['unresolved'])
        conflict=next(b for b in r['bindings'] if b['candidate']=='Conflict')
        self.assertEqual(conflict['action_resolution'],'ambiguous')
        missing=next(b for b in r['bindings'] if b['candidate']=='AbsentAction')
        self.assertEqual(missing['action_resolution'],'missing_or_dynamic_identifier')

    def test_typename_shadow_and_dynamic_expressions_do_not_create_item_action_links(self):
        self.write('Shadow.c','''class Shadow:ItemBase {
          void Bind(typename SyntheticUse){AddAction(SyntheticUse);AddAction(Choose());}
        };''')
        r=self.audit(); bindings=[b for b in r['bindings'] if b['enclosing_class']=='Shadow']
        self.assertEqual(len(bindings),2)
        self.assertTrue(all(b['action_class'] is None for b in bindings))
        self.assertIn('identifier_shadowed',bindings[0]['unresolved'])
        self.assertEqual(bindings[1]['action_resolution'],'dynamic_expression')

    def test_manifest_matches_shared_crafting_source_contract_and_detects_drift(self):
        first=self.audit()
        shared=self.module.crafting.audit_tree(self.tree)
        self.assertEqual(first['manifest_sha256'],shared['manifest_sha256'])
        self.assertTrue(self.audit(expected_manifest_sha256=first['manifest_sha256'])['valid'])
        self.write('Added.C','class Unused {};')
        changed=self.audit(expected_manifest_sha256=first['manifest_sha256'])
        self.assertFalse(changed['valid'])
        self.assertIn('manifest_mismatch',{d['code'] for d in changed['diagnostics']})

    def test_deterministic_outputs_no_input_mutation_and_no_acceptance_claim(self):
        before=dict(self.fs.nodes)
        first=self.audit();second=self.audit()
        self.assertEqual(first,second)
        self.assertEqual(before,self.fs.nodes)
        self.assertFalse(first['full_effective_behavior_coverage'])
        self.assertEqual(first['runtime_acceptance'],'NOT_EVALUATED')
        self.assertEqual(first['coverage']['source_files'],3)
        self.assertEqual(first['coverage']['emitted_bindings'],len(first['bindings']))
        json.dumps(first,allow_nan=False)

    def test_malformed_sources_and_explicit_legacy_encoding_fail_closed(self):
        self.write('Broken.c','class Broken { void Go() {')
        r=self.audit(); self.assertFalse(r['valid']);self.assertFalse(r['inputs_complete'])
        self.assertIn('invalid_source',{d['code'] for d in r['diagnostics']})
        self.fs.nodes.pop(str(self.tree/'Broken.c'))
        self.write('Legacy.c',b'// legacy \x96 comment\nclass Legacy {};')
        self.assertFalse(self.audit()['valid'])
        r=self.audit(fallback_encoding='cp1252');self.assertTrue(r['valid'],r['diagnostics'])
        self.assertEqual(next(s['encoding'] for s in r['sources'] if s['path']=='Legacy.c'),'cp1252')

    def test_symlinks_and_resource_bounds_cannot_claim_complete_census(self):
        self.fs.nodes[str(self.tree/'Escape.c')]=(stat.S_IFLNK|0o777,'/outside.c')
        r=self.audit();self.assertFalse(r['valid'])
        self.assertIn('unsafe_source_path',{d['code'] for d in r['diagnostics']})
        self.fs.nodes.pop(str(self.tree/'Escape.c'))
        for constant,value in (('MAX_BINDINGS',1),('MAX_METHODS',1),
                               ('MAX_CONTROLS',0),('MAX_CLASSES',1),
                               ('MAX_OUTPUT_BYTES',100)):
            with self.subTest(constant=constant),patch.object(self.module,constant,value):
                r=self.audit();self.assertFalse(r['valid'])
                self.assertIn('resource_limit',{d['code'] for d in r['diagnostics']})
        with patch.object(self.module.crafting,'MAX_FILE_BYTES',16):
            self.assertFalse(self.audit()['valid'])

    def test_expression_truncation_keeps_hash_and_explicit_unknown(self):
        self.write('Long.c','class Long:ItemBase {void SetActions(){AddAction(Choose("'+
                   'x'*100+'"));}};')
        with patch.object(self.module,'MAX_EXPRESSION',32):
            r=self.audit()
        row=next(b for b in r['bindings'] if b['enclosing_class']=='Long')
        self.assertTrue(row['expression_truncated'])
        self.assertLessEqual(len(row['expression']),32)
        self.assertEqual(row['expression_sha256'],hashlib.sha256(
            ('Choose("'+'x'*100+'")').encode()).hexdigest())
        self.assertEqual(row['action_resolution'],'dynamic_expression')

    def test_cli_emits_only_json_and_nonzero_for_invalid_census(self):
        output=io.StringIO()
        with patch('sys.stdout',output):
            code=self.module.main(['--root',str(self.tree)])
        self.assertEqual(code,0);self.assertTrue(json.loads(output.getvalue())['valid'])
        output=io.StringIO()
        with patch('sys.stdout',output):
            code=self.module.main(['--root',str(self.tree),'--expect-manifest-sha256','0'*64])
        self.assertEqual(code,1);self.assertFalse(json.loads(output.getvalue())['valid'])

    def test_native_typedef_and_constructor_candidates_are_separate_from_item_bindings(self):
        self.write('Aliases.c','''typedef ItemBase InventoryItemSuper;
          class Weapon:InventoryItemSuper {};
          class Constructor {void RegisterActions(array<typename> actions) {
            actions.Insert(SyntheticUse); // actions.Insert(SyntheticUnused);
          }};''')
        r=self.audit(); weapon=next(c for c in r['classes'] if c['class']=='Weapon')
        self.assertIn('ItemBase',weapon['ancestry']['observed_classes'])
        registry=[b for b in r['bindings'] if b['kind']=='constructor_registry_candidate']
        self.assertEqual(len(registry),2)
        self.assertTrue(all(b['owner_class'] is None for b in registry))
        self.assertEqual({b['disabled'] for b in registry},{False,True})
        self.assertEqual(r['aliases'][0]['target'],'ItemBase')

    def test_multiple_arguments_are_not_silently_reduced_to_a_class_link(self):
        self.write('Arity.c','class Arity:ItemBase {void Bind(){AddAction(SyntheticUse, Other);}};')
        r=self.audit(); row=next(b for b in r['bindings'] if b['enclosing_class']=='Arity')
        self.assertIsNone(row['action_class'])
        self.assertIn('argument_arity',row['unresolved'])
        self.assertIn('SyntheticUse',row['expression'])

    def test_analysis_work_alias_and_ancestry_budgets_fail_closed(self):
        self.write('Aliases.c','typedef ItemBase InventoryItemSuper;')
        for constant,maximum in (('MAX_ANALYSIS_WORK',0),('MAX_ALIASES',0),('MAX_ANCESTRY',1)):
            with self.subTest(constant=constant),patch.object(self.module,constant,maximum):
                report=self.audit()
                self.assertFalse(report['valid'])
                self.assertIn('resource_limit',{d['code'] for d in report['diagnostics']})

    def test_unresolved_parent_is_retained_as_unknown_not_a_confirmed_exclusion(self):
        self.write('Missing.c','class PossibleAction:NotSupplied {};')
        r=self.audit(); row=next(c for c in r['classes'] if c['class']=='PossibleAction')
        self.assertEqual(row['action_candidate_status'],'UNKNOWN-unresolved-ancestry')
        self.assertIsNone(row['action_exclusion'])

    def test_duplicate_and_alias_ancestry_fanout_spends_shared_work_budget(self):
        fixtures = (
            'class Hub {};\n'*64,
            'typedef ItemBase Hub;\n'*64,
        )
        for hub in fixtures:
            with self.subTest(hub=hub.splitlines()[0]):
                self.write('Fanout.c', hub+''.join(
                    'class Child%d:Hub {};\n'%i for i in range(64)))
                with patch.object(self.module,'MAX_ANALYSIS_WORK',5000):
                    r=self.audit()
                self.assertFalse(r['valid'])
                self.assertFalse(r['coverage']['source_census_complete'])
                self.assertIsNone(r['manifest_sha256'])
                self.assertIn('resource_limit',{d['code'] for d in r['diagnostics']})

    def test_parent_edges_spend_shared_work_budget_below_depth_limit(self):
        self.write('Chain.c','class Chain0 {};\n'+''.join(
            'class Chain%d:Chain%d {};\n'%(i,i-1) for i in range(1,48)))
        with patch.object(self.module,'MAX_ANALYSIS_WORK',3000):
            r=self.audit()
        self.assertFalse(r['valid'])
        self.assertIn('resource_limit',{d['code'] for d in r['diagnostics']})

    def test_global_functions_callbacks_controls_and_comments_keep_null_owner(self):
        body='{\n if (Allowed()) AddAction(SyntheticUse);\n // AddAction(SyntheticUnused);\n}'
        self.write('Global.c','#ifdef GLOBAL_FEATURE\nvoid OnConsume() '+body+
                   '\nproto native void Repair(ItemBase item);\n#endif\n'
                   'int Helper(){return 1;}\nclass Tail {void Member(){}};')
        r=self.audit(); self.assertTrue(r['valid'],r['diagnostics'])
        rows={m['name']:m for m in r['methods'] if m['source']=='Global.c'}
        self.assertEqual(set(rows),{'OnConsume','Repair','Helper','Member'})
        for name in ('OnConsume','Repair','Helper'):
            self.assertIsNone(rows[name]['owner_class'])
            self.assertIsNone(rows[name]['owner_definition'])
        self.assertEqual(rows['Member']['owner_class'],'Tail')
        self.assertTrue(rows['Repair']['declaration_only'])
        consume=rows['OnConsume']
        self.assertEqual(consume['line'],2)
        self.assertEqual(consume['conditions'],['#ifdef GLOBAL_FEATURE'])
        self.assertEqual(consume['sha256'],hashlib.sha256(body.encode()).hexdigest())
        self.assertEqual([c['kind'] for c in consume['runtime_control_flow']],['if'])
        bindings=[b for b in r['bindings'] if b['source']=='Global.c']
        self.assertEqual(len(bindings),2)
        self.assertEqual({b['disabled'] for b in bindings},{True,False})
        self.assertTrue(all(b['method_id']==consume['id'] for b in bindings))
        self.assertTrue(all(b['owner_class'] is None for b in bindings))
        callbacks={m['name']:m for m in r['callbacks'] if m['source']=='Global.c'}
        self.assertEqual({n:m['category'] for n,m in callbacks.items()},
                         {'OnConsume':'consume','Repair':'repair'})

    def test_global_prototypes_and_initializers_are_not_action_invocations(self):
        self.write('Global.c','''int cached = Compute();
          ref Thing singleton = new Thing();
          proto native void AddAction(typename action);
          void RegisterActions(array<typename> actions) {
            actions.Insert(SyntheticUse);
          }''')
        r=self.audit(); self.assertTrue(r['valid'],r['diagnostics'])
        methods=[m for m in r['methods'] if m['source']=='Global.c']
        self.assertEqual({m['name'] for m in methods},{'AddAction','RegisterActions'})
        rows=[b for b in r['bindings'] if b['source']=='Global.c']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['call'],'Insert')
        self.assertEqual(rows[0]['method_id'],
                         next(m['id'] for m in methods if m['name']=='RegisterActions'))
        self.assertIsNone(rows[0]['enclosing_class'])

    def test_global_typename_shadow_remains_unresolved(self):
        self.write('Global.c','void Bind(typename SyntheticUse){AddAction(SyntheticUse);}')
        r=self.audit()
        row=next(b for b in r['bindings'] if b['source']=='Global.c')
        self.assertIsNone(row['action_class'])
        self.assertIn('identifier_shadowed',row['unresolved'])

    def test_global_facts_share_method_and_control_limits(self):
        baseline=self.audit()['coverage']['method_declarations']
        self.write('Global.c','void One(){if(Allowed()) Work();}\nvoid Two(){}')
        for name,maximum in (('MAX_METHODS',baseline+1),('MAX_CONTROLS',1)):
            with self.subTest(name=name),patch.object(self.module,name,maximum):
                r=self.audit()
                self.assertFalse(r['valid'])
                self.assertIn('resource_limit',{d['code'] for d in r['diagnostics']})


if __name__=='__main__':
    unittest.main()
