# WP5 cross-model review (Sonnet 5.5) of 5212907 (#20 production room catalog)

Verdict: MERGE-WITH-FIXES

Source is sound: no gate bypass, no client state, no hostile-JSON crash path, compile shape clean.
The fixes are mostly test strengthening (29 surviving mutants, 6 of them security/contract relevant)
plus three runtime-risk items that must be recorded as open: House-class cap 2048, startup cost
with lazy load, and DTO inheritance in JsonSerializer. All source changes are small.

## Findings (ranked)

1. HIGH (test) - typed JSON preflight is not proven to guard the load path.
   HCInfectedRooms.c (EnsureProductionLoaded, line 979) `if (ValidProductionJson(content))` inside EnsureProductionLoaded
   replaced by `if (true)` -> all 28 tests still pass. The test LoadData stub accepts anything json.loads
   accepts and BindProduction rejects the rest, so only direct ValidProductionJson calls are tested.
   Scenario: someone drops the call; unknown keys/escapes/oversized arrays reach the native
   JsonSerializer unvetted and tests stay green.
   Fix: add a test through EnsureProductionLoaded with raw JSON that is valid for json.loads but fails
   preflight (unknown key, duplicate key, 17 anchors, "A" escape) and assert calls["parse"] == 0 and
   reason == rooms_json.

2. HIGH (test) - Clear() does not provably reset production state.
   Mutant removing `ClearProduction();` from Clear() (line 124) survives. The WP1 contract says
   Module stop calls Clear() and that this resets production; only ClearProduction is tested.
   Fix: test that after admission, Clear() empties s_ProductionBindings/Classes, reason == rooms_not_loaded
   and a following EnsureProductionLoaded re-reads and logs again.

3. MEDIUM (test) - evidence guards individually unproven.
   Surviving: removal of the `native-` prefix check (line 475), `fixture` and `selftest` markers,
   min length 8 (line ~470), SourceSha256 copy into the owned anchor.
   Scenario: run id "run-001" (no native- prefix) is admitted and no test notices.
   Fix: one parametrized case per rule: "run-0001", "native-fixture-1", "native-selftest-1", "native-" (7 chars),
   and assert owned anchors keep SourceRunId/SourceSha256/EvidenceKind.

4. MEDIUM (test) - bound guards with no individual test.
   Surviving mutants: Build pin literal (`document.Build != "1.30.164289"` removed, runtime check alone still
   passes since test runtime == pinned; need doc==runtime=="1.31.1" case), total cap 257 (only 256 admission tested),
   zero-anchor house (`Count() < 1`), 65 houses and 17 anchors via BindProduction directly, BoxMin < -512,
   anchor Id > 64 (production), duplicate Id with distinct positions, positions < 1 apart with distinct Ids
   (each guard masks the other because the test uses both), LocalPosition below LocalMin, LocalMin == LocalMax
   (zero-volume room), House class missing while an extra non-House class pads the count (`known.Find(className) < 0`
   removal at line 525), second BindProduction after admission (rebind guard, report claims it is refused).
   Fix: add one boundary test per guard listed. Code is correct on reading; only the tests are weak.

5. MEDIUM (test) - no class name with an underscore.
   ProductionToken (439) rejecting `_` survives. Real class names are Land_House_1B01 etc.; tests use
   SyntheticHouse only. If the `_` allowance regressed every real class would be refused with rooms_coverage.
   Fix: use Synthetic_House_1 style names in the fixture.

6. MEDIUM (runtime risk, unverifiable offline) - cap of 2048 House classes (line 110, 525; preflight line ~660).
   Denominator is every CfgVehicles class where IsKindOf(.., "House") is true. In vanilla this includes all
   Land_* static objects, not only enterable buildings; I believe the count is well above 2048 on Chernarus
   plus other-map assets, but could not measure it here (no config dump). If so, production admission can never
   succeed (reason rooms_coverage) and the operator cannot tell why.
   Fix: before enabling, log observed configCount and houseClasses in the refusal line (bounded ints, no
   native text), measure in DayZDiag, then set MAX_PRODUCTION_CLASSES to the measured count plus margin. Keep
   JSON size cap 1 MiB in mind. Do not merge claiming full-denominator coverage until measured.

7. MEDIUM (runtime risk) - inherited DTO fields.
   `class HCInfectedProductionRoomAnchor : HCInfectedRoomAnchor` (line 76) puts Id/LocalPosition/LocalMin/LocalMax
   on the base. I found no native documentation or stock DTO proving JsonSerializer reads inherited members
   (gameplay.c:49-90 only shows flat/nested examples). Failure mode is fail-closed (Id 0 -> rooms_geometry), not a
   crash. Minimal fix: flatten the production anchor (declare the 4 base fields plus the 3 evidence fields directly
   and give the class its own Contains) or verify in DayZDiag first and record the result.

8. LOW-MEDIUM (performance) - lazy load inside the AI tick.
   BuildProductionOrder (line 1006) calls EnsureProductionLoaded lazily, which can run up to 32768 x IsKindOf
   (each up to 5 ConfigGetFullPath calls, Game.c:1437-1470) plus a char-by-char Enforce parse of up to 1 MiB
   (about 3-4 script calls per character). Unmeasured; could hitch the server tick once. The report says WP1 should call
   EnsureProductionLoaded at startup; make that a hard requirement for WP1 and have BuildProductionOrder return empty
   (not load) if never loaded, or accept the hitch knowingly. Budgets stay provisional.

9. LOW - ReadFile count semantic unverified (line 970-974): `bytesRead == content.Length()` is required.
   ReadBounded (HCInfectedState.c:208) does not check it. If the engine returns a different count for a string
   target, production never admits (rooms_read, fail-closed). Add the observed values to the DayZDiag experiment list.
   GetVersion string format likewise unverified (BindProduction build check); consider logging the observed
   build string (bounded to 32 chars) on rooms_build refusal.

10. LOW - chained `value.Get(i).ToAscii()` (lines 443, 452, 495-ish and ProductionJsonValue
    `content.Get(textBegin + 1).ToAscii()`). Existing authored code assigns `string ch = content.Get(i)` first.
    Chaining on a temporary string is probably fine (stock code chains Substring(...).ToInt(), ScriptConsoleGeneralTab.c:375)
    but ToAscii is not chained on Get anywhere in stock scripts. Cheap hardening: assign to a local first.

11. INFO - the "measured box" (BoxMin/BoxMax) is operator-declared and only checked for self-consistency; it is not
    compared with a native house extent. Documented as provenance-only trust; keep as an open evidence item.
    Admitted state with zero instances (all-excluded document) still reports the "admitted" reason; consumers must check
    instance count, not reason alone. Production log line carries counts so this is visible.

## 1. Native APIs (all under /home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/)

- JsonFileLoader<T>.LoadData: 3_Game/tools/JsonFileLoader.c:69 `static bool LoadData(string string_data, out T data, out string errorMessage)`.
  Returns bool. On malformed JSON it sets errorMessage and returns false (lines 74-78); no ErrorEx, no print, no
  crash in script. The void/ErrorEx variants are the deprecated JsonLoadData (:152-160), which WP5 does not use.
  LoadFile (:6-34) is not used: it reads up to READ_FILE_LENGTH 100000000 (:3), which the writer correctly avoids.
- Native JsonSerializer.ReadFromString: gameplay.c:49-90, proto bool, error is an out string.
  Hostile shape never reaches it unless preflight is removed (finding 1); it supports vector as [x,y,z],
  nested objects and dynamic arrays (gameplay.c:81-86).
- FileExist 1_Core/proto/EnSystem.c:397 (bool); OpenFile :417 (0 on failure); ReadFile :425 (returns bytes read);
  CloseFile :443; FileMode.READ :382-384. All match usage. Handle closed on every path where it opened.
- GetGame().GetVersion(out string): 3_Game/Global/Game.c:942; GetWorldName wrapper :934 (out :932); IsServer :1120.
- ConfigGetChildrenCount(string) Game.c:611 (single-arg form used by stock AttachmentsOutOfReach.c:97);
  ConfigGetChildName(path, index, out name) Game.c:594, bool; IsKindOf Game.c:1437 (script, ConfigGetFullPath loop).
- GetObjectsAtPosition3D Game.c:930; Print 1_Core/proto/EnDebug.c:96.
- string: ToAscii EnString.c:86, Substring :113, ToLower :171 (in place, returns int), Length :199, Contains :286, Get :448.
- $profile paths: prefix documented at EnSystem.c:~410 ("$profile:myfilename.txt").
- array Find/Insert/Count/Get EnScript.c:380-407. vector.DistanceSq as cited in report.
- Hostile JSON: every loop is bounded by content length/field caps (7 fields per object, 3 per vector, array caps 2048/64/16/3,
  strings 128, numbers 32, recursion fixed depth 3 objects). No unbounded loop or recursion found.

## 2. Compile shape (all changed lines, verified by script and reading)

- Max binary '+' per statement: 5 (the Print line), by a comment/string-stripped statement counter. Limit 8.
- No leading `||`/`&&` line (rg `^\s*(\|\||&&)` empty), no ternary (rg `\?` empty outside comments), explicit .ToString() on both log counts.
- No duplicate locals across sibling scopes found by reading each new function (ValidateProductionCoverage i/className/classIndex;
  ValidateProductionHouse axis/anchorAxis; BindProduction counted/record/anchor/ownedAnchor/previous/binding/entry; JsonNumber ascii/digit/fractionDigit/exponentDigit).
- `string currentBuild; GetVersion(currentBuild)` and `TVectorArray points` declared before out calls. No override changes.
- No identifier equals an engine type name (test_script_identifiers green).
- DTOs: string/int/vector/ref array<ref T>/nested class fields only; vector defaults as string literals match the existing diagnostic DTO. Only open question is inheritance (finding 7).

## 3. Semantics

- Build pin: BindProduction checks both literal and runtime GetVersion (finding 4 notes the literal half is untested).
- World: token charset plus exact GetWorldName. Allowlist: Disposition enum, only "covered" classes may have records, covered class needs >=1 instance.
- Caps: 64 houses, 16 per house, 256 total, 2048 classes, 32768 config, 1 MiB. Offsets: LocalMin/Max inside BoxMin/Max (+-512), position inside room box,
  all positive comparisons so NaN/inf refused. Evidence per anchor: native- run id, no synthetic/fixture/selftest, 64 lowercase hex non-zero, kind native-room-survey-v1.
  Self-declared provenance only; SHA is never recomputed (documented).
- Specific reason codes assigned per stage; failures leave s_Production* untouched (atomic publish after full stage). Log once per lifecycle (Print at EnsureProductionLoaded end; guarded by s_ProductionAttempted).
- DIAG untouched: BuildOrder still uses EnsureDiagnosticLoaded + s_Bindings; OrderBindings extracted unchanged (diff lines 692-725). Diagnostic tests (13) still pass.
- No gate bypass: rg finds no caller of EnsureProductionLoaded/BuildProductionOrder in Module/Navigation/State/Policy/Profiles; no Enable* flag, waypoint, group, perception, door or audio API added. Routing remains behind Investigation/NativePackRoutes qualifications, which are false.
- Admitted reason is `rooms_admitted_measurements_path_audio_doors_pending`. No client-owned state: ProductionServer() = GetGame().IsServer(), fixed path, no RPC, no write path; ProductionCoverage returns copies.

## 4. Integration

- b04-integ HEAD is a3b6085 (later than dc8a563). HCInfectedRooms.c and the two WP5 test files are unchanged there vs 73241f6; the integ diff touches Module, Navigation, Policy, Profiles, State, SelfTests, HordeStimulus, AlertChain only.
- `patch -p1 --dry-run` of the WP5 patch on a `git archive` copy of a3b6085: clean for all 3 files. After applying, the full unit suite in that copy: Ran 2497 tests ... OK (skipped=1).
- Dependencies still exist in integ: HCInfectedStore.ValidPosition (HCInfectedState.c:346), HCInfectedPolicy.AdmitRoomCatalog (:551), PreferRoom (:538). Module calls HCInfectedRoomCatalog.Clear() at HCInfectedModule.c:897 (now also clears production). Navigation still calls BuildOrder at HCInfectedNavigation.c:153 (DIAG only).
- Interface asked of WP1/WP2 is purely additive: WP1 calls EnsureProductionLoaded at startup and reads ProductionReason/ProductionCoverage; WP2 switches to BuildProductionOrder only under both qualifications. Note for WP2: tests/unit/test_infected_completion.py:189-190 asserts the substring `HCInfectedRoomCatalog.BuildOrder` in Navigation and an ordering relative to something else; if WP2 renames the call that test needs updating (it will not match `BuildProductionOrder`). No conflict with integ today.

## 5. Test strength

Required run (actual):
```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_room_catalog_completion tests.unit.test_infected_production_rooms -v
Ran 28 tests in 2.850s
OK
```
Script tests: `python3 -m unittest discover -s tests/unit -p 'test_script_*.py'` -> Ran 8 tests ... OK.
Caveat: the tests run a Python translation of the authored Enforce source against fabricated boundaries; they cannot catch Enforce compile or engine semantic faults.

Mutation run (72 single-line mutants, script mutate.py / output mutate.out in this directory, applied to a throwaway `git archive` copy, source untouched):
- KILLED 43, SURVIVED 29 (incl. 2 equivalent/no-op), 2 skipped for anchor ambiguity then re-run (prod id lo KILLED, prod id hi SURVIVED).
- Survivors: build literal pin, max houses +1, per-house cap +1, min-anchors, total cap +1, class cap +1, house cap in coverage (equivalent: known list already bounded), unknown house class, duplicate class (near-equivalent: count mismatch catches), box order (equivalent given >=1 anchor), box lower -512, anchor id dup, anchor id hi, local min<max, pos>=min, spacing, ev len8, ev native prefix, ev fixture, ev selftest, hash lowercase (my mutant was a no-op, ignore), JSON preflight call, rebind guard, token underscore, JSON backslash rejection in ProductionJsonText, array limit +100000 (preflight cap redundant with Bind caps), JSON length cap (redundant with Ensure cap), Clear() resets production, evidence SHA copy, float fraction digits required.
- Killed (good): runtime build, world, schema version, total accumulation, count mismatch, disposition, excluded class used, covered class unused, config cap, box max 512, local min/max in box, pos<=max, evidence call, ev synthetic, kind, hash, hash len, hash non-zero, log-once guard, missing file, size cap, read count, close handle, LoadData result, server checks, atomic publish, duplicate house, null binding, status text, budget guard, token length, integer digits, duplicate key, required keys, trailing text, vec3, DIAG ordering, coverage copy, leading zero.

Test-leak check: neither WP5 test writes files (rg for tmp/open/write: none). Ran the full unit suite in a throwaway copy: no tests/fixtures/benchmark/tmp* dirs created; `git status --short` in b04-wp5 shows only `?? scratchpad-review/wp5-review/` (this review). The tmp* directory the caller mentioned does not exist in b04-wp5.

## Commands run
- `git show 5212907 --stat`, diff read in full.
- compile-shape rg/python scans (above): only the Print line exceeds 3 '+' (5).
- required unittest run: 28 OK; script tests: 8 OK.
- integ-copy: `git -C b04-integ archive HEAD | tar -x` (a3b6085), `patch -p1 --dry-run` then apply, `unittest discover -s tests/unit` -> 2497 tests OK (skipped=1). Copy removed afterwards.
- mutation run: python3 -B mutate.py (output file mutate.out). Copies removed afterwards.
