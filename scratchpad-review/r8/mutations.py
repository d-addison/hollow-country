"""Mutate scratch exports only, restoring each source in finally; record exact replacements."""
from pathlib import Path
import json,os,subprocess
ROOT=Path(__file__).resolve().parent
HEAD=ROOT/'head'; OUT=ROOT/'mutation-logs';OUT.mkdir(exist_ok=True)
R='tools/audit/taped_light_report.py';P='tools/setup/taped_light_probe.py';L='tools/setup/probe_runtime.py'
mutants=[
 ('res_lod_order_check_removed',R,'or name != lod["name"] or listed != lod["list_ok"]','or listed != lod["list_ok"]'),
 ('res_list_status_check_removed',R,'or name != lod["name"] or listed != lod["list_ok"]','or name != lod["name"]'),
 ('res_selection_from_failed_list_allowed',R,'if selection and not (listed and lod["selection_count"] > 0):','if False:'),
 ('res_row_count_check_removed',R,'if rows is MISSING or len(rows) != len(res["lods"]):','if rows is MISSING:'),
 ('res_complete_ignored',R,'if not lod["scan_complete"] or not found["selection"]:','if not found["selection"]:'),
 ('resolution_path_check_removed',R,'if len(item["model"]) <= 5 or _resolution_path(found["selection"]) != _path(item["model"]):','if False:'),
 ('resolution_vertex_flag_ignored',R,'elif not found["vertex_ok"]:','elif False:'),
 ('resolution_vertex_parse_ignored',R,'elif _vertex(found["vertex"]) is None:','elif False:'),
 ('finite_number_check_removed',R,'return numbers if all(math.isfinite(number) for number in numbers) else None','return numbers'),
 ('vertex_fullmatch_to_match',R,'_NUMBER_TEXT.fullmatch(item)','_NUMBER_TEXT.match(item)'),
 ('lod_crosscheck_removed',R,'(res is not None and not _lods_agree(res, lod))','False'),
 ('alias_config_conflict_ignored',R,'if known != reading or lookups.setdefault(values["cfg_class"].casefold(), lookup) != lookup:','if lookups.setdefault(values["cfg_class"].casefold(), lookup) != lookup:'),
 ('alias_lookup_conflict_ignored',R,'if known != reading or lookups.setdefault(values["cfg_class"].casefold(), lookup) != lookup:','if known != reading:'),
 ('alias_not_collapsed',R,'if known is reading:','if True:'),
 ('alias_collapse_diagnostic_zeroed',R,'collapsed += identity in seen','collapsed += 0'),
 ('first_matching_lod_only',R,'for lod, found in zip(res["lods"], item["res"]):','for lod, found in zip(res["lods"][:1], item["res"][:1]):'),
 ('empty_basename_both_guards_removed',R,' or not path.rsplit("/", 1)[-1] or path.endswith("/")',''),
 ('lod_name_fullmatch_to_match',R,'not _RES_LOD_NAME.fullmatch(name) or total < 0','not _RES_LOD_NAME.match(name) or total < 0'),
 ('enum_false_treated_empty',R,'return "resolution_enumeration_failed", None       # LOD.GetSelections','return "resolution_proxy_missing", None       # LOD.GetSelections'),
 ('hook_failed_array_not_cleared',P,'                        listedFlag = 0;\n                        lodSelections.Clear();','                        listedFlag = 0;'),
 ('hook_lod_cap_removed',P,'if (resNames.Count() < 16)','if (true)'),
 ('hook_selection_cap_removed',P,'if (selectionKept > 512)','if (false)'),
 ('hook_lod_total_cap_removed',P,'if (lodTotal > 128)\n            return -1;','if (false)\n            return -1;'),
 ('hook_vertex_index_guard_removed',P,'matchSelection.GetVertexCount() > 0 && matchSelection.GetLODVertexIndex(0) != -1','matchSelection.GetVertexCount() > 0'),
 ('hook_vertex_count_guard_removed',P,'matchSelection.GetVertexCount() > 0 && matchSelection.GetLODVertexIndex(0) != -1','matchSelection.GetLODVertexIndex(0) != -1'),
 ('hook_numeric_names_all_accepted',P,'if (HCTLIsNumericName(lodName))','if (true)'),
 ('hook_first_digit_check_removed',P,'if (digitSet.IndexOf(lodName.Substring(0, 1)) == -1)\n            return false;','if (false)\n            return false;'),
 ('hook_last_digit_check_removed',P,'if (digitSet.IndexOf(lodName.Substring(nameLength - 1, 1)) == -1)\n            return false;','if (false)\n            return false;'),
 ('getselections_out_lint_removed',L,'("GetSelections", (0,)), ',''),
]
mods=['tests.unit.test_probe_runtime','tests.unit.test_ce_probe','tests.unit.test_diagnostic_mission',
      'tests.unit.test_flashlight_matrix','tests.unit.test_taped_light_probe','tests.unit.test_taped_light_report']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(ROOT/'tmp'))
records=[]
for name,relative,before,after in mutants:
    path=HEAD/relative;source=path.read_text();assert source.count(before)==1,(name,source.count(before))
    try:
        path.write_text(source.replace(before,after))
        # Report changes need the report suite; generator/lint changes need all shared consumers.
        tests=['tests.unit.test_taped_light_report'] if relative==R else mods
        argv=['python3','-B','-m','unittest',*tests,'-q']
        result=subprocess.run(argv,cwd=HEAD,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    finally:path.write_text(source)
    (OUT/(name+'.log')).write_text(result.stdout)
    rec=dict(name=name,file=relative,before=before,after=after,argv=argv,exit=result.returncode,
             summary=[line for line in result.stdout.splitlines() if line.startswith(('Ran ','FAILED','OK'))])
    records.append(rec);(ROOT/'mutations.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(dict(name=name,result='SURVIVED' if result.returncode==0 else 'KILLED',summary=rec['summary'])),flush=True)
