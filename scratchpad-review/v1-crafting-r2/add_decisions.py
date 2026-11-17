from pathlib import Path
import json
from tests.unit.test_crafting_families import FAMILIES
p=Path('tools/audit/item_utility.py');s=p.read_text();i=s.index('\ndef _decisions(')
rows=[]
for name,sources,condition,evidence in [
 ('HCSalvageCamoNet',['CamoNet'],'non-ruined','C1'),
 ('HCSalvageCableReel',['CableReel'],'non-ruined','C1')]+[(n,data[0],'ruined-only' if data[5] else 'non-ruined', 'LARGE' if 'LargeLeather' in n else 'MEDIUM' if 'MediumLeather' in n else 'C1' if 'Crate' in n else 'B1') for n,data in FAMILIES.items()]:
 rows.append('    ('+repr(name)+', '+repr(tuple(sources))+', '+repr(condition)+', '+repr('crafting-v1:'+evidence)+'),')
addition='''
# Authored V1 balance decisions over exact identities, never ancestry/prefix rules.
# Evidence IDs resolve in tests/fixtures/runtime/crafting-contract.json. Config
# establishes material identity only; output quantities are whole-unit policy.
HC_RECOVERY_ROWS = (
'''+ '\n'.join(rows)+'''
)
HC_RUINED_EXCLUSIONS = (
    ('''+repr(tuple(FAMILIES['HCRecoverMediumLeather'][0]))+''',
     'HCRecoverMediumLeather', 'crafting-v1:MIN-PANEL',
     'single-unit pristine panel; no positive lower whole-unit yield; no proved substitute material'),
    (('BarbedBaseballBat',), 'HCRecoverBarbedBat', 'crafting-v1:MIN-WIRE',
     'single-unit pristine wire; no positive lower whole-unit yield; no proved substitute conversion'),
)


def _hc_decisions(root, name):
    if root != 'CfgVehicles':
        return []
    decisions = [dict(recipe=recipe, status='implemented', condition=condition,
                      evidence_id=evidence, runtime_acceptance='pending')
                 for recipe, sources, condition, evidence in HC_RECOVERY_ROWS if name in sources]
    decisions.extend(dict(recipe=recipe, status='excluded', condition='ruined-only',
                          evidence_id=evidence, reason=reason, runtime_acceptance='pending')
                     for sources, recipe, evidence, reason in HC_RUINED_EXCLUSIONS if name in sources)
    return decisions

'''
s=s[:i]+addition+s[i:];s=s.replace("        config.append(dict(id=row['id']", "        hc_decisions = _hc_decisions(row['root'], row['name'])\n        conversion = 'hc-recovery' if any(d['status'] == 'implemented' for d in hc_decisions) else 'UNKNOWN'\n        config.append(dict(id=row['id']");s=s.replace("material_conversion='UNKNOWN', inventory_eligibility='NOT_EVALUATED'", "material_conversion=conversion, hc_decisions=hc_decisions,\n                           inventory_eligibility='NOT_EVALUATED'")
p.write_text(s)
p=Path('tests/fixtures/runtime/crafting-contract.json');d=json.loads(p.read_text());d['v1_decision_evidence']={
 'crafting-v1:LARGE':dict(config_refs=['characters_tops.pbo/config.bin:LeatherJacket_ColorBase@105118','characters_vests.pbo/config.bin:LeatherStorageVest_ColorBase@22424'],decision='Leather material selections; authored 2 panels ordinary, 1 ruined. No registered native garment DeCraft overlap in inspected census.'),
 'crafting-v1:MEDIUM':dict(config_refs=['L1','L2','characters_tops.pbo/config.bin:LeatherShirt_ColorBase@141720','characters_pants.pbo/config.bin:LeatherPants_ColorBase@50723'],decision='Exact leather selections; authored 1 panel ordinary.'),
 'crafting-v1:C1':dict(config_refs=['gear_camping.pbo/config.bin:CamoNet@123889','gear_camping.pbo/config.bin:CableReel@138132','gear_camping.pbo/config.bin:WoodenCrate@127895'],decision='Textile, cord and wood definitions. Native DeCraftWoodenCrate max damage 3; ruined HC crate is disjoint.'),
 'crafting-v1:B1':dict(config_refs=['weapons_melee.pbo/blunt/config.bin:BaseballBat@474','weapons_melee.pbo/blunt/config.bin:NailedBaseballBat@1699','weapons_melee.pbo/blunt/config.bin:BarbedBaseballBat@2949','weapons_melee.pbo/blunt/config.bin:XmasBaseballBat@4527'],decision='Wood impact/bat materials. CraftBaseBallBatNailed consumes 12 nails; ordinary HC recovers stick 1+nails 4, ruined recovers only nail 1. No registered native bat DeCraft overlap.'),
 'crafting-v1:MIN-PANEL':dict(config_refs=['L1','L2','gear_consumables.pbo/config.bin:TannedLeather@30720'],sha256='ed0a211a281fb39a545c9fba18b0881ae8f7e5921aa1775a30989f9a0c343223',native_fields=dict(varQuantityMin=0,varQuantityDestroyOnMin=1),decision='Excluded ruined medium leather: ordinary output is 1 panel, Configure quantity is int. A lower whole-unit output is zero and destroys on minimum. Material selections do not establish cloth/rag yield. Fractional balance and runtime qualification are deferred, not an engine impossibility.'),
 'crafting-v1:MIN-WIRE':dict(config_refs=['gear_crafting.pbo/config.bin:MetalWire@4323','crafting-v1:B1'],sha256='28285d6ab07d1429b1461f494d3994e541f7dce9efb7002503f2972940dfa94d',native_fields=dict(varStackMax=1,varQuantityMin=0,varQuantityDestroyOnMin=1),decision='Excluded ruined barbed bat: ordinary output is 1 wire unit. No positive lower whole-unit yield under Configure int contract. Wood is proved but a wood-for-wire conversion would not be strictly below the ordinary material vector. Fractional yield policy remains deferred.'),
}
d['v1_mechanical_candidates']=[dict(item='RabbitSnareTrap',status='native-action-qualification-pending',sources=['4_World/Classes/Recipes/Recipes/CraftRabbitSnare.c','4_World/Entities/ItemBase/TrapSpawnBase/Trap_RabbitSnare.c','4_World/Entities/ItemBase/TrapSpawnBase.c'],facts='CraftRabbitSnare consumes 1 WoodenStick and destroys MetalWire. No registered DeCraftRabbitSnare or explicit dismantle action found in inspected trap SetActions chain; folding/deactivation is not proved material recovery. No engine invocation performed.',decision='Candidate for mechanical recovery after native action qualification; no HC recipe added.')]
p.write_text(json.dumps(d,indent=2)+'\n')
