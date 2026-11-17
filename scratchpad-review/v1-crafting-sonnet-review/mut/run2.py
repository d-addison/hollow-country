import shutil, subprocess, sys, os, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
BASE = HERE / 'base'
C = 'mods/HollowCountry/scripts/4_World/Crafting/'
S = C + 'HCSalvageRecipe.c'
D = C + 'HCItemUtilityDiagnostic.c'
MODS = [
 ('M01 tool health < instead of <=', S, 'ingredients[1].GetHealth("", "") <= m_HCWear', 'ingredients[1].GetHealth("", "") < m_HCWear'),
 ('M02 drop cargo refusal', S, 'if (cargo && cargo.GetItemCount() > 0)', 'if (false)'),
 ('M03 drop attachment refusal', S, 'if (item.GetInventory().AttachmentCount() > 0)', 'if (false)'),
 ('M04 drop hat source', S, 'if (index == 6) return "LeatherHat_Beige";', ''),
 ('M05 medium yield 1->2', S, '"HCRecoverMediumLeather", "KitchenKnife", "TannedLeather", 1,', '"HCRecoverMediumLeather", "KitchenKnife", "TannedLeather", 2,'),
 ('M06 source not destroyed (dup loot)', S, 'm_IngredientDestroy[0] = true;', 'm_IngredientDestroy[0] = false;'),
 ('M07 allow worn (drop IsAttachment)', S, ' || item.GetInventory().IsAttachment()', ''),
 ('M08 ruined crate not ruined-only', S, 'm_HCRuinedOnly = true;', 'm_HCRuinedOnly = false;'),
 ('M09 output health 0.75->1.0', S, 'm_HCSourceHealth * 0.75', 'm_HCSourceHealth * 1.0'),
 ('M10 add LeatherGloves_Black source', S, 'if (index == 6) return "LeatherHat_Beige";', 'if (index == 6) return "LeatherHat_Beige"; if (index == 7) return "LeatherGloves_Black";'),
 ('M10b count 7->8 w/ gloves black', S, 'if (seed == "HCRecoverMediumLeather") return 7;', 'if (seed == "HCRecoverMediumLeather") return 8;'),
 ('M11 owner check removed', S, 'item.GetHierarchyRootPlayer() != player || ', ''),
 ('M12 drop type recheck', S, 'if (!HCSalvageSources.AllowsSource(m_HCInputType, ingredients[0].GetType()) || !HCSalvageTools.Allows(m_HCToolType, ingredients[1].GetType()))', 'if (false)'),
 ('M13 cable reel plugged allowed', S, 'GetCompEM().IsPlugged() || ', ''),
 ('M14 server check dropped', S, 'if (!GetGame().IsServer())\n            return;', ''),
 ('M15 nailed bat nails 4->8', S, 'AddRecoveryResult("Nail", 4);', 'AddRecoveryResult("Nail", 8);'),
 ('M16 crate nails 2->16', S, 'AddRecoveryResult("Nail", 2);', 'AddRecoveryResult("Nail", 16);'),
 ('M17 ruined crate condition 0.10->0.9', S, 'condition = 0.10;', 'condition = 0.90;'),
 ('M18 wear mutated: tool replaced (dest tool)', S, 'm_IngredientAddHealth[1] = -wear;', 'm_IngredientAddHealth[1] = -wear; m_IngredientDestroy[1] = true;'),
 ('M19 reentrancy guard off', S, 'if (!m_HCCommitGuard.TryEnter())\n            return;', ''),
 ('M20 registration drop hat recipe', C+'HCRecipeRegistration.c', '        RegisterRecipe(new HCRecoverMediumLeather);\n', ''),
 ('M21 registration reorder', C+'HCRecipeRegistration.c', '        RegisterRecipe(new HCSalvageCamoNet);\n        RegisterRecipe(new HCSalvageCableReel);', '        RegisterRecipe(new HCSalvageCableReel);\n        RegisterRecipe(new HCSalvageCamoNet);'),
 ('M22 output mismatch not discarded', S, 'if (!OutputsMatch(spawned_objects, false))\n        {\n            DiscardOutputs(spawned_objects);\n            return;\n        }', ''),
 ('D01 Begin drop empty-server check', D, 'if (players.Count() > 0)\n            return false;', ''),
 ('D02 Begin drop opt-in', D, '|| !explicitOptIn ', ''),
 ('D03 Begin drop isolation confirm', D, '|| !isolatedExternalProfileConfirmed', ''),
 ('D04 SafeConcrete allow all', D, 'if (root != "CfgVehicles")\n            return false;', 'return true;'),
 ('D05 budget time > not >=', D, 'now - m_StartedMs >= m_MaxMillis', 'now - m_StartedMs > m_MaxMillis'),
 ('D06 CanExecute allow results', D, 'recipe.m_NumberOfResults != 0', 'false'),
 ('D07 ValidRequest charset removed', D, 'if (!"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_0123456789".Contains(character))', 'if (false)'),
 ('D08 ValidRequest index replay', D, 'request.Index != m_Cursor || ', ''),
 ('D09 PollCleanup ignores bag', D, 'if (m_Bag || m_ActorObject) return false;', 'if (m_ActorObject) return false;'),
 ('D10 Begin max queue 262144->10M', D, 'totalRows > 262144', 'totalRows > 99999999'),
 ('D11 ObserveObjects scope check dropped', D, 'if (row.Scope != 2 || request.KitIndex == -1) return;', 'if (request.KitIndex == -1) return;'),
 ('D12 creation review dropped', D, '!request.CreationReviewed || ', ''),
 ('D13 ancestors depth 64->1000000', D, 'depth < 64', 'depth < 1000000'),
 ('D14 delete requests count off', D, 'm_DeleteRequests++;\n        }\n        if (m_ToolObject)', 'm_DeleteRequests += 2;\n        }\n        if (m_ToolObject)'),
 ('D15 ObserveNext does not stop at end', D, 'if (m_Cursor == m_Total) Stop("supplied-queue-emitted");', ''),
 ('D16 Snapshot zone limit dropped', D, 'if (state.Zones.Count() > 32)', 'if (false)'),
 ('D17 Summary Complete ignores partial', D, 'summary.Complete = summary.CleanupConfirmed && !m_Partial && m_Total > 0;', 'summary.Complete = summary.CleanupConfirmed && m_Total > 0;'),
 ('D18 RowFits payload limit removed', D, 'if (payload.Length() > 16000) return false;', ''),
 ('D19 actor identity allowed', D, 'm_Actor.GetIdentity()) return false;', 'false) return false;'),
 ('D20 executes without opt-in (m_Execute)', D, '!m_Execute || ', ''),
 ('D21 Stop partial flag', D, 'm_Partial = m_Cursor != m_Total;', 'm_Partial = false;'),
 ('D22 Begin s_Active not set', D, 's_Active = true;\n        m_Running = true;', 'm_Running = true;'),
 ('A01 audit production_enablement True', 'tools/audit/item_utility.py', 'runtime_qualified=False, production_enablement=False', 'runtime_qualified=False, production_enablement=True'),
 ('A02 audit disabled->preserve', 'tools/audit/item_utility.py', "'disabled': 'hold-disabled'", "'disabled': 'preserve-native'"),
 ('A03 audit empty cohort -> qualify', 'tools/audit/item_utility.py', "('empty_observation', 'nonpositive_only')", "('nonpositive_only',)"),
 ('A04 test-only hold dropped', 'tools/audit/item_utility.py', "'hold-test-only' if name == 'ActionRepairWithToolFromHands'", "'preserve-native' if False"),
]
SUBSET = ['tests.unit.test_v1_crafting','tests.unit.test_v1_crafting_diagnostic','tests.unit.test_crafting_audit','tests.unit.test_crafting_completion','tests.unit.test_crafting_contract','tests.unit.test_crafting_families','tests.unit.test_crafting_families_native','tests.unit.test_item_utility','tests.unit.test_salvage_tools','tests.unit.test_script_identifiers','tests.unit.test_script_syntax','tests.unit.test_utility_review']

from concurrent.futures import ThreadPoolExecutor
skip = set(sys.argv[1:])
def one(item):
    i,(name,f,old,new) = item
    w = HERE / ('work%d' % (i % 3))
    # per-slot dir reused sequentially is unsafe with threads; use unique dir
    w = HERE / ('work_' + name.split()[0])
    if w.exists(): shutil.rmtree(w)
    shutil.copytree(BASE, w)
    p = w / f
    t = p.read_text()
    if old not in t:
        shutil.rmtree(w); return name + ' PATTERN-NOT-FOUND'
    p.write_text(t.replace(old, new, 1))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run([sys.executable, '-m', 'unittest'] + SUBSET, cwd=w, env=env, capture_output=True, text=True)
    out = r.stderr.strip().splitlines()
    status = 'SURVIVED' if r.returncode == 0 else 'killed'
    fails = [l.split(' (')[0] for l in out if l.startswith(('FAIL:', 'ERROR:'))][:2]
    shutil.rmtree(w)
    return '%s %s %s' % (name, status, fails)
items = [(i,m) for i,m in enumerate(MODS) if m[0].split()[0] not in skip]
with ThreadPoolExecutor(3) as ex:
    for line in ex.map(one, items):
        print(line, flush=True)
