import subprocess, sys, os, shutil
R='/code/hc-worktrees/b04-wp5/scratchpad-review/wp5-review'
F=R+'/mut/mods/HollowCountry/scripts/4_World/Infected/HCInfectedRooms.c'
orig=open(F).read()
M=[
 ("build literal doc", 'if (document.Build != "1.30.164289" || currentBuild != document.Build)', 'if (currentBuild != document.Build)'),
 ("build runtime", 'if (document.Build != "1.30.164289" || currentBuild != document.Build)', 'if (document.Build != "1.30.164289")'),
 ("world compare", 'document.WorldName != GetGame().GetWorldName())\n            return false;\n        s_ProductionReason = "rooms_limits"', 'false)\n            return false;\n        s_ProductionReason = "rooms_limits"'),
 ("schema version", 'document.SchemaVersion != 1)\n            return false;\n        s_ProductionReason = "rooms_build"', 'false)\n            return false;\n        s_ProductionReason = "rooms_build"'),
 ("max houses", 'document.Buildings.Count() > MAX_PRODUCTION_HOUSES', 'document.Buildings.Count() > MAX_PRODUCTION_HOUSES + 1'),
 ("per-house cap", 'counted.Anchors.Count() > MAX_HOUSE_ANCHORS', 'counted.Anchors.Count() > MAX_HOUSE_ANCHORS + 1'),
 ("min anchors", 'counted.Anchors.Count() < 1 ||', 'false ||'),
 ("total cap", 'if (total > MAX_TOTAL_ANCHORS)', 'if (total > MAX_TOTAL_ANCHORS + 1)'),
 ("total accum", 'total = total + counted.Anchors.Count();', 'total = counted.Anchors.Count();'),
 ("class cap", 'document.Classes.Count() > MAX_PRODUCTION_CLASSES)\n            return false;\n        if (!document.Buildings', 'document.Classes.Count() > MAX_PRODUCTION_CLASSES + 1)\n            return false;\n        if (!document.Buildings'),
 ("house cap in coverage", 'houseClasses > MAX_PRODUCTION_CLASSES || known.Find(className) < 0', 'known.Find(className) < 0'),
 ("unknown house class", '|| known.Find(className) < 0)', ')'),
 ("count mismatch", 'if (houseClasses != known.Count())\n            return false;', ''),
 ("dup class", 'if (known.Find(entry.BuildingClass) >= 0)\n                return false;', ''),
 ("disposition valid", '!ProductionDisposition(entry.Disposition))', 'false)'),
 ("excluded used", 'classIndex < 0 || document.Classes[classIndex].Disposition != "covered"', 'classIndex < 0'),
 ("covered unused", 'if (declared.Disposition == "covered" && usedClasses.Find(declared.BuildingClass) < 0)\n                return false;', ''),
 ("config cap hi", 'configCount < 1 || configCount > MAX_CONFIG_CLASSES', 'configCount < 1'),
 ("box order", 'record.BoxMin[axis] < record.BoxMax[axis]))', 'true))'),
 ("box -512", 'record.BoxMin[axis] >= -512 &&', ''),
 ("box 512", 'record.BoxMax[axis] <= 512 &&', ''),
 ("anchor id range lo", 'anchor.Id < 1 || anchor.Id > 64', 'anchor.Id > 64'),
 ("anchor id range hi", 'anchor.Id < 1 || anchor.Id > 64', 'anchor.Id < 1'),
 ("anchor id dup", '|| usedIds.Find(anchor.Id) >= 0)', ')'),
 ("local min in box", 'anchor.LocalMin[anchorAxis] >= record.BoxMin[anchorAxis] &&', ''),
 ("local max in box", 'anchor.LocalMax[anchorAxis] <= record.BoxMax[anchorAxis] &&', ''),
 ("local min<max", '&& anchor.LocalMin[anchorAxis] < anchor.LocalMax[anchorAxis]))', '))'),
 ("pos >= min", 'anchor.LocalPosition[anchorAxis] >= anchor.LocalMin[anchorAxis] &&', ''),
 ("pos <= max", '&& anchor.LocalPosition[anchorAxis] <= anchor.LocalMax[anchorAxis]))', '))'),
 ("spacing", 'vector.DistanceSq(previousPoint, anchor.LocalPosition) < 1', 'false'),
 ("evidence call", 'if (!ProductionEvidence(anchor))', 'if (false)'),
 ("ev null", 'if (!anchor || !ProductionToken(anchor.SourceRunId, 96) || anchor.SourceRunId.Length() < 8)', 'if (!anchor)'),
 ("ev len8", ' || anchor.SourceRunId.Length() < 8', ''),
 ("ev native prefix", 'runId.Substring(0, 7) != "native-" ||', ''),
 ("ev synthetic", ' || runId.Contains("synthetic")', ''),
 ("ev fixture", ' || runId.Contains("fixture")', ''),
 ("ev selftest", ' || runId.Contains("selftest")', ''),
 ("ev kind", 'anchor.EvidenceKind == "native-room-survey-v1" && ProductionHash', 'ProductionHash'),
 ("ev hash", '&& ProductionHash(anchor.SourceSha256);', ';'),
 ("hash len", 'value.Length() != 64', 'false'),
 ("hash nonzero", 'return nonzero;', 'return true;'),
 ("hash lower", '(ascii >= 97 && ascii <= 102)', '(ascii >= 97 && ascii <= 102) && !(ascii >= 65 && ascii <= 70)'),
 ("log once guard", 'if (!ProductionServer() || s_ProductionAttempted)\n            return;\n        s_ProductionAttempted = true;', 'if (!ProductionServer())\n            return;\n        s_ProductionAttempted = true;'),
 ("missing file", 'if (FileExist(PRODUCTION_PATH))', 'if (true)'),
 ("size upper", 'content.Length() <= MAX_PRODUCTION_BYTES)\n                    {', 'true)\n                    {'),
 ("read count", 'bytesRead >= 0 && bytesRead == content.Length()', 'true'),
 ("close handle", '                CloseFile(handle);\n', ''),
 ("preflight", 'if (ValidProductionJson(content))', 'if (true)'),
 ("loaddata result", 'if (JsonFileLoader<HCInfectedProductionRoomDocument>.LoadData(content, document, error))\n                                BindProduction(document);', 'JsonFileLoader<HCInfectedProductionRoomDocument>.LoadData(content, document, error);\n                            BindProduction(document);'),
 ("server check ensure", 'if (!ProductionServer() || s_ProductionAttempted)', 'if (s_ProductionAttempted)'),
 ("server check bind", 'if (!ProductionServer())\n            return false;\n        if (s_ProductionReason == "rooms_admitted', 'if (false)\n            return false;\n        if (s_ProductionReason == "rooms_admitted'),
 ("rebind guard", 'if (s_ProductionReason == "rooms_admitted_measurements_path_audio_doors_pending")\n            return false;', ''),
 ("atomic publish", 's_ProductionBindings = staged;', 'for (int zz = 0; zz < 0; zz++) {} s_ProductionBindings = staged;'),
 ("duplicate house", 'if (previous.HouseObject == building)\n                    return false;\n            }\n            HCInfectedRoomBinding binding = new HCInfectedRoomBinding;', '}\n            HCInfectedRoomBinding binding = new HCInfectedRoomBinding;'),
 ("binding null", 'if (!building)\n                return false;\n            foreach (HCInfectedRoomBinding previous', 'foreach (HCInfectedRoomBinding previous'),
 ("status text", 'rooms_admitted_measurements_path_audio_doors_pending";\n        return true;', 'rooms_admitted";\n        return true;'),
 ("budget guard prod", 'if (!ProductionServer() || budget < 1 || budget > 3', 'if (!ProductionServer() || budget < 1'),
 ("token chars", 'ascii != 45 && ascii != 95', 'ascii != 45'),
 ("token len", 'value.Length() < 1 || value.Length() > limit', 'value.Length() < 1'),
 ("json int digits", 'if (integerOnly && s_JsonOffset - begin > 9)', 'if (false)'),
 ("json escape", 'ascii < 32 || ascii > 126 || ascii == 92', 'ascii < 32 || ascii > 126'),
 ("json dup key", 'if (bit == 0 || (mask & bit) != 0)', 'if (bit == 0)'),
 ("json required", 'return mask == ProductionRequiredKeys(kind);', 'return true;'),
 ("json trailing", 'return s_JsonOffset == content.Length();', 'return true;'),
 ("json arr limit", 'if (count >= limit)', 'if (count >= limit + 100000)'),
 ("json vec3", 'if (kind == 8 && count != 3)', 'if (false)'),
 ("json len cap", 'content.Length() > MAX_PRODUCTION_BYTES)\n            return false;\n        ProductionJsonSkip', 'false)\n            return false;\n        ProductionJsonSkip'),
 ("orders: diag unchanged", 'EnsureDiagnosticLoaded();\n        OrderBindings(observedClue, budget, s_Bindings, points);', 'EnsureProductionLoaded();\n        OrderBindings(observedClue, budget, s_Bindings, points);'),
 ("clear resets prod", '        s_DiagnosticAttempted = false;\n        ClearProduction();', '        s_DiagnosticAttempted = false;'),
 ("coverage copies", 'ownedClass.Disposition = entry.Disposition;', 'ownedClass.Disposition = "covered";'),
 ("evidence copy", 'ownedAnchor.SourceSha256 = anchor.SourceSha256;', ''),
 ("num float frac", 'if (s_JsonOffset == fractionBegin)\n                return false;', ''),
 ("leading zero", 'if (zero || s_JsonOffset - begin > 32)', 'if (s_JsonOffset - begin > 32)'),
]
test=['python3','-B','-m','unittest','tests.unit.test_room_catalog_completion','tests.unit.test_infected_production_rooms']
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
surv=[]
for name,a,b in M:
    if orig.count(a)!=1:
        print("SKIP(anchor count %d): %s"%(orig.count(a),name)); continue
    open(F,'w').write(orig.replace(a,b))
    r=subprocess.run(test,cwd=R+'/mut',env=env,capture_output=True,text=True,timeout=300)
    status='KILLED' if r.returncode!=0 else 'SURVIVED'
    if r.returncode==0: surv.append(name)
    print(status,name,flush=True)
open(F,'w').write(orig)
print("SURVIVORS:",surv)
