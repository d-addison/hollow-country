**FIX-THEN-MERGE — four P2 findings; no P0/P1 finding.**

Reviewed the four-file working-tree diff against `182db38` and the previously unreviewed `73241f6..182db38 -- tools tests`, including the `probe_runtime.py` out-argument lint addition. Findings below refer to current working-tree line numbers. This was a single cross-model review, not a panel vote. No repository source or git metadata was changed; no DayZ, Wine, or network was used. All reviewer-authored files are under this directory.

Read `AGENTS.md`, `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`, the writer's `scratchpad-review/r8-fix/REPORT.md`, and `scratchpad-review/opus/ANALYSIS.md`. The two specifications named by AGENTS (`docs/SPECIFICATION.md`, `docs/specs/001-survival-overhaul/spec.md`) are absent from this checkout; no renamed specification was found in its file listing. The owner's rules A–C in the review request govern this review. The Banso CLI skill's dispatched-worker guidance was applied; no lifecycle or panel command was run.

**Findings and exact fixes**

1. **P2-1 — Conflicting light-slot aliases can still produce `geometry_missing`.** `tools/audit/taped_light_report.py:884` (also `:887`, `:892`, `:905`; conflict detected at `:625`). `_proxies()` correctly detects conflicting copies, but `_evaluate_slot()` only consults the resulting pending model evidence through `_accepted()` on an allowed attachment. Refusal branches return a negative verdict first. With two spellings of the universal-light proxy, one existing and one nonexistent config readback, a clean synthetic native refusal gives host/pair/slot `geometry_missing`, reason `native_attach_refused`, and no integrity issues. With exactly the same aliases and an allowed attach it gives `pending`. Rule A requires the conflicting host to remain pending regardless of the attach outcome. A conflict can also be ignored by the no-compatible-slot/no-native-slot exits.

   **Fix:** retain a host-level alias-conflict reason independent of the attach result and let the affected slot/pair remain pending before evaluating native refusals. Cover direct refusal, prerequisite refusal, no-compatible-slot cases, and both alias orders. Do not implement this as an indiscriminate invalidation of unrelated pairs; see P2-2.

2. **P2-2 — An unrelated proxy alias conflict voids independent light-slot evidence.** `tools/audit/taped_light_report.py:625` and `:798`. Every proxy conflict becomes one host-wide `("malformed",)` value. `_model_evidence()` then rejects every light slot before inspecting its own proxy, including a valid universal-light row when the only conflict concerns `magazine` aliases. The synthetic reproduction yields host `pending` (correct), but also changes the independently evidenced universal-light pair from `server_qualified` to `pending` (violates rule A's unrelated-slot clause). Coherent magazine aliases do not cause this problem; conflicting unrelated readbacks expose the lost scope.

   **Fix:** retain conflict identities and their affected slots rather than discarding all parsed rows. Keep the host pending for contradictory copies, withhold evidence from the affected light slots, and preserve an independently valid light pair when the conflict is demonstrably unrelated. If copies disagree about their slot, use all implicated slots rather than selecting the favorable copy. Add a valid light proxy plus coherent and conflicting magazine-alias fixtures, in both orders.

3. **P2-3 — Proxy inventory-slot membership is case-insensitive despite exact slot names.** `tools/audit/taped_light_report.py:807` and `:812`. The code case-folds both the queried slot and the config's `inventory_slots`. A proxy whose only slot is `weaponflashlight` qualifies the exact `weaponFlashlight` host slot. The rest of the slot/preflight/classification joins are keyed by the exact strings, and `HCTLProxyHoldsSlot()` uses exact `Find(slotName)` at `tools/setup/taped_light_probe.py:1096`, so this also creates an internal policy discrepancy.

   **Fix:** compare `slot` directly against the original `inventory_slots` strings and use exact names for the other-light-slot classification. Retain case/slash normalization for proxy paths and config class spellings. Add case-changed slot tests alongside the existing pistol-versus-weapon and substring tests. The existing `pistolFlashlight` versus `weaponFlashlight` distinction itself is preserved; the gap is the broader-than-exact membership check.

4. **P2-4 — A malformed optional spawn diagnostic aborts the whole report.** `tools/audit/taped_light_report.py:746`. `_spawn_control()` evaluates `if key in raw` before testing `isinstance(raw, dict)`. Valid JSON with `spawn_control: null`, `42`, or `true` raises `TypeError`; the CLI catches it and returns failure without a report. This contradicts the diagnostic-only contract and the function's promised malformed status. It is newly introduced in this round; an absent control still works correctly.

   **Fix:** reject a non-dict `raw` as `{"status":"malformed"}` before membership tests. Exercise null, number, bool, string, list, and malformed object inputs and assert that an otherwise valid pair keeps its verdict. The current hook's fallback object is valid; this finding concerns the report's handling of mistyped input.

5. **P3-1 — Several new tests do not distinguish the behavior their names claim.** `tests/unit/test_taped_light_report.py:1186`; `tests/unit/test_taped_light_probe.py:2180`, `:2286`, `:2300`. Four fault injections survive all 273 in-memory tests:

   - R02 appends coherent aliases twice instead of collapsing them; the tests check verdicts and a separately computed diagnostic count, not the parsed evidence-row count.
   - P08 replaces `boneObject == attached` with mere non-nullness. The fixture labeled “another object” returns no object, so it never tests a distinct non-null object.
   - P09 removes `HCTLSlotBones(variantHost)`; base and variant fixtures have indistinguishable bone indices.
   - P10 removes the control's immediate `HCTLReleaseAll()`; checking only final cleanup allows a later host release to mask it.

   **Recommended test fixes:** assert one parsed evidence row for aliases; return a distinct live object for a negative bone-identity case; give base and prerequisite hosts different bone readbacks and record which host is queried; assert control deletion occurs before the next host spawn. These are coverage gaps, not evidence that the current identity comparison, variant refresh, or immediate release is absent. The original P3-4 guards listed by the author are now mutation-sensitive (see below).

**Closure of the author's claimed prior findings**

| Prior finding | Review result and evidence |
| --- | --- |
| P2-1, null `scanLod` / unavailable vs genuine false | Fixed in source: `taped_light_probe.py:651` gets the name outside the instance guard; `:661` guards count/list calls. `:739` emits instance state. `taped_light_report.py:542` validates the paired fields, `:547` rejects impossible null-instance facts, `:678` reports unavailable separately. Mutation P01 is killed. This has not been compiled or run in the real engine by this review. |
| P2-2, R12 / Mich2001Helmet pending for client | Fixed for the archived inputs: `_model_evidence` at report `:827` returns client when absence decides nothing; `_accepted` at `:839` emits `pending_client`; `:943` carries `client_required`. Rejoining probe-006 gives both hosts pending with that reason, not geometry_missing. |
| P2-3, legacy positive flags need the queried selection | Fixed: report `:275` requires a nonempty queried name and `:279` compares it with the top-level native mapping when present. Unknown or mistyped mappings do not agree. R08/R09 are killed. The case-fold here compares **model selection names**, not inventory-slot keys. |
| P3-4, surviving finite-number / full-name / row agreement / vertex guards | Fixed for the stated cases. R04 rejects loss of finite-number checking (`1e999`), R05 rejects prefix matching (`1\n`), R06 rejects partial numeric LOD names, R07 rejects row/host `list_ok` disagreement even with another qualifying LOD, P04/P05 reject omission of either vertex guard. All six mutants are killed. |
| P3-5, retained base and prerequisite attempts | Fixed: report `:878` stores separate attempts and evaluated route; `:902` retains handguard identity/readback/rail status; `:934` exposes them. R10 and R11 are killed. |

The source changes in `182db38` that are superseded by round 8 include the unguarded LOD selection call and later-scope vertex read. The current scan reads vertices before clearing each LOD's selection list (`taped_light_probe.py:687`, `:694`, `:701`) and keeps only text for later JSON rows (`:765`). Its numeric-LOD/whole-path matching remains implemented; resolution results are now diagnostics rather than qualification gates. The shared `_OUT_CALLS` addition for `GetSelections` in `probe_runtime.py:170` is appropriate.

**Rules A–C and concrete-class identity**

| Rule | Enforcement / gap |
| --- | --- |
| A, collapse only coherent aliases; add no evidence | `_proxy_name`, report `:412`, normalizes proxy spelling while retaining instance identity. `_proxies`, `:621`, compares config existence/model/slot list/count/resolution lookup; `:624`–`:628` append only the first coherent identity. The scratch regression directly confirms exactly one parsed evidence row. Conflicts are detected, but their precedence and scope are wrong: P2-1/P2-2. |
| B, every concrete variant needs its own rows | Report `:1181` indexes raw observations by exact `class`; `:1190` looks up `entry["name"]`; `:1033` requires a row; `:1035` checks root/group; `:1045` checks the spawned concrete type. `root` is a config namespace, not an ancestor class. Probe `:145` retains each concrete class in targets and `:1502`/`:1510` spawns that exact class. No verdict is keyed by ancestor, parent, stripped suffix, or shared model. The scratch regression leaves FNX45_arrow, SCARH_Black, and Glock19_Tan pending without their own rows even when the parent row qualifies. |
| C, exact slots | `_keyed` and the slot/preflight/configured-set comparisons use exact string keys (report `:289`, `:351`, `:394`, `:1056`). Pistol and weapon slots are not conflated. The config-proxy membership join additionally case-folds names; P2-3 is the gap. Native switch-action keys are exact (`:163`/`:845`). |

**Generated Enforce hook and installed API audit**

Generated the full archived classification's default hook without staging or launching anything. `generated-hook.c` is authored probe output, not an installed-script dump. Actual checks are in `static-output.txt`:

```text
Hook bytes: 98904
Hook sha256: a8e8d7f3298a9c05905e2c54206a54a5c785d4a03c67ff69d5bca5dc5301931f
Lint with installed native type names and explicit_numbers: []
Maximum + per statement: 8
CreateObjectEx call sites: 1
ObjectDelete call sites: 1
```

No ternary, leading `||`/`&&`, engine-type local collision, duplicate sibling-scope local, or implicit numeric concatenation was found. The actual maximum satisfies the requested **8**, although the shared lint's general budget is 9. Booleans pass through `HCTLBool`, numeric JSON/concatenation terms through `ToString`. Arrays used as out arguments are constructed before calls; text outputs for ConfigGetText, ConfigGetChildName, GetWorldName, GetVersion, and slot lookups are declared before use. I checked these manually as well as running the available lint, whose out-call table covers only a subset of these APIs.

Hook loops terminate through a decreasing index/string or increasing cursor over bounded data: at most 600 hosts, 8 lights/slots, 3 prerequisite slots, 128 enumerated LODs, 16 resolution/count entries, 512 model selections per scan, 24 emitted proxy rows, 8 listed config slots, 4 proxy names × 4 bone spellings per slot, 4096 config children, and 2048 residual objects. The full loop listing is in `static-output.txt`. As documented, queued watchdogs do not interrupt a synchronous native call that never returns.

Every directly emitted non-HCTL call has a matching declaration or script wrapper in the installed **1.30.164289** snapshot. In this table, paths are relative to `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`; line numbers were read locally, not copied from comments. Some entries are script helpers rather than `proto native`, which is stated explicitly.

| Emitted API(s) | Installed declaration / implementation |
| --- | --- |
| `GetGame` | `3_Game/gameplay.c:636` (script helper) |
| `super.OnInit` | `5_Mission/mission/missionServer.c:85` (script override inherited through the mission) |
| `IsServer`, `SurfaceY`, `GetTime` | `3_Game/Global/Game.c:1120`, `:1176`, `:1535` |
| `Vector` | `1_Core/proto/EnMath3D.c:18` |
| `GetCallQueue`, `CallLater` | `3_Game/DayZGame.c:1233` (script override); `2_GameLib/tools.c:61` |
| `CreateObjectEx`, `ObjectDelete` | `3_Game/Global/Game.c:703`, `:705` |
| `GetObjectsAtPosition3D`, `GetWorldName`, `GetVersion` | `3_Game/Global/Game.c:930`, `:932`, `:942` |
| Game `ConfigGetText`, `ConfigGetTextArray`, `ConfigGetChildName`, `ConfigGetChildrenCount`, `ConfigIsExisting` | `3_Game/Global/Game.c:449`, `:558`, `:594`, `:611`, `:612` |
| Object `ConfigGetBool`, `ConfigIsExisting` | `3_Game/Entities/Object.c:887` (script bool helper), `:929` |
| `GetLODS`, `GetLODName`, `GetLODByName` | `3_Game/Entities/Object.c:98`, `:101`, `:106` (last is a script helper) |
| `GetSelectionList`, `HasSelection` | `3_Game/Entities/Object.c:382`, `:405` (last is a script helper) |
| `MemoryPointExists`, `GetMemoryPointPos` | `3_Game/Entities/Object.c:454`, `:452` |
| Object `GetType` | `3_Game/Entities/Object.c:467` (script helper calling Game.ObjectGetType, declared `3_Game/Global/Game.c:712`) |
| `GetBoneIndex`, `GetBoneObject` | `3_Game/Entities/Entity.c:36`, `:39` |
| `GetInventory` | `3_Game/Entities/EntityAI.c:1884` |
| `GetSlotId`, `GetSlotIdCount`, `GetAttachmentSlotId`, `GetAttachmentSlotsCount` | `3_Game/Systems/Inventory/Inventory.c:171`, `:175`, `:180`, `:184` |
| `HasAttachmentSlot`, `HasInventorySlot` | `3_Game/Systems/Inventory/Inventory.c:188` (script helper), `:201` |
| `CreateAttachmentEx`, `FindAttachment`, `CanAddAttachment`, `CanAddAttachmentEx` | `3_Game/Systems/Inventory/Inventory.c:215`, `:224`, `:241`, `:246` |
| `GetSlotIdFromString`, `GetSlotName`, `IsSlotIdValid`, `GetBoneNameForSlotId`, `GetSelectionForSlotId` | `3_Game/Systems/Inventory/InventorySlots.c:42`, `:48`, `:59`, `:80`, `:86` |
| Selection `GetName`, `GetVertexCount`, `GetLODVertexIndex`, `GetVertexPosition` | `3_Game/gameplay.c:184`, `:185`, `:186`, `:188` (last is script and guards its native LOD index) |
| LOD `GetSelectionCount`, `GetSelections`, underlying `GetVertexPosition` | `3_Game/gameplay.c:215`, `:216`, `:218` |
| `EntityAI.Cast` | Inherited `Class.Cast`, `1_Core/proto/EnScript.c:94` |
| Array `Count`, `Clear`, `Find`, `Get`, `Insert` | `1_Core/proto/EnScript.c:380`, `:385`, `:394`, `:399`, `:407` |
| String `Substring`, `Replace`, `ToLower`, `Length`, `IndexOf`, `LastIndexOf`, `IndexOfFrom` | `1_Core/proto/EnString.c:113`, `:156`, `:171`, `:199`, `:240`, `:253`, `:271` |
| Integer `ToString`, `AsciiToString`; float `ToString` | `1_Core/proto/EnConvert.c:30`, `:44`, `:115` |
| `Print`, `FileExist`, `OpenFile`, `CloseFile`, `FPrintln`, `MakeDirectory` | `1_Core/proto/EnDebug.c:96`; `1_Core/proto/EnSystem.c:397`, `:417`, `:443`, `:481`, `:525` |

The exact native switch-slot strings used by the report are present at `4_World/Classes/UserActionsComponent/Actions/SingleUse/ActionTurnOnWeaponFlashlight.c:27` and `:32`, and `ActionTurnOnHelmetFlashlight.c:40`; corresponding off actions use the same weapon/pistol strings at `:27`/`:32` and helmet at `:59`. This supports the table of addressable slots, not observed operation of a client switch.

The one `CreateObjectEx` site is `taped_light_probe.py:294`; each successful object enters `m_HCTLLive` once at `:297`. Attachments created through the two `CreateAttachmentEx` sites (`:1274`, `:1476`) are separately tracked at `:1277`/`:1487`. The one `ObjectDelete` site is `:318`, in reverse creation order; the list is cleared at `:324`. Thus children are released before their owning hosts, with one explicit deletion request per tracked non-null handle. Runtime deletion success is checked separately by released handles and the residual census; static review does not prove engine cleanup.

Ordinary CreateObjectEx calls use `ECE_IN_INVENTORY | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME` (`:305`); the control uses only `ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME` (`:1328`) and is immediately released (`:1357`). Installed constants are `3_Game/CE/CentralEconomy.c:37` (787456), `:31` (8388608), and `:30` (4194304): ordinary flags are **13370368**, control flags **12582912**. The emulator's 7/6 flag values are explicitly synthetic and are not the engine constants. CreateAttachmentEx has no ECE-flags argument, so the flag claim applies to world-object spawns.

**Actual focused test output**

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_taped_light_report tests.unit.test_taped_light_probe
```

Combined stdout/stderr, also retained unmodified in `unit-output.txt`:

```text
.....taped_light_report: Expecting value: line 1 column 1 (char 0)
.taped_light_report: report output must be outside the source checkout
.taped_light_report: [Errno 17] File exists: '/tmp/tmpwpciviho/report.json'
............................................................................................................................................................................................................................................................................................
----------------------------------------------------------------------
Ran 291 tests in 13.990s

OK
report: server_qualified=1 geometry_missing=0 not_server_evidencable=0 excluded=1 pending=0 hosts=2 -> /tmp/tmpwpciviho/report.json
```

`git diff --check 182db38 -- tools tests` also passed. The full 2417-test discovery result in the writer's report was not rerun and is not claimed as reviewer evidence.

Separate scratch behavioral regressions (`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python3 scratchpad-review/r8-sol-review/test_review_regressions.py`) ran **6 tests: 3 failures, 1 error, 2 passes**. They demonstrate P2-1 through P2-4; coherent alias collapse and concrete-class isolation pass. Full actual output is in `regression-output.txt`; compact counterexample output is in `cases-output.txt`. No implementation was made in this review.

**Scratch mutation results**

Ran `PYTHONDONTWRITEBYTECODE=1 python3 scratchpad-review/r8-sol-review/mutations.py`. Each subprocess imports exactly one mutated scratch copy in place of the report or probe module and runs the original in-memory test classes. The 18 CLI/stager tests are excluded because they intentionally require destinations outside the checkout; this keeps mutation-run files within the authorized scratch directory. The same **273-test unmutated baseline passed** (`mutants/B00/output.txt`: `Ran 273 tests in 10.446s`, `OK`). The complete requested 291-test suite was separately run above.

A preliminary harness attempt included the filesystem tests with a scratch-local TMPDIR and triggered unrelated outside-checkout guards. That attempt was discarded; only the corrected runs below are counted. No survivor is hidden by a harness error. Each row has its own full actual output in `mutants/<id>/output.txt`; `mutation-results.json` records failure names and counts.

**24 mutations: 19 KILLED, 5 SURVIVED.** R03 is a corrective mutation, so the fault-only score is 19 of 23 killed, with four surviving faults.

| ID | Change to scratch module | Result | Actual unittest outcome |
| --- | --- | --- | --- |
| R01 | alias/config readback conflict check removed | **KILLED** | FAILED (failures=25) |
| R02 | coherent aliases retained as duplicate evidence rows | **SURVIVED** | OK |
| R03 | proxy inventory slot comparison made exact | **SURVIVED** | OK |
| R04 | nonfinite vertex guard removed | **KILLED** | FAILED (failures=1) |
| R05 | vertex numeric fullmatch weakened to prefix | **KILLED** | FAILED (failures=1) |
| R06 | resolution name fullmatch weakened to prefix | **KILLED** | FAILED (failures=7) |
| R07 | per-row/host LOD list flag agreement removed | **KILLED** | FAILED (failures=1) |
| R08 | legacy positive flag empty-selection guard removed | **KILLED** | FAILED (failures=6) |
| R09 | legacy/top-level mapping agreement removed | **KILLED** | FAILED (failures=4) |
| R10 | base attempt overwritten by evaluated attempt | **KILLED** | FAILED (failures=1) |
| R11 | prerequisite handguard readback identity guard removed | **KILLED** | FAILED (failures=7) |
| R12 | proxy model-path equality guard removed | **KILLED** | FAILED (failures=6) |
| R13 | observed beam-point absence ignored | **KILLED** | FAILED (failures=3) |
| P01 | null resolution LOD guard removed | **KILLED** | FAILED (failures=1) |
| P02 | native resolution selection count replaced by zero | **KILLED** | FAILED (failures=3) |
| P03 | per-LOD count bound raised from 16 to 128 | **KILLED** | FAILED (failures=1) |
| P04 | LOD vertex-index guard removed | **KILLED** | FAILED (failures=1) |
| P05 | selection vertex-count guard removed | **KILLED** | FAILED (failures=1) |
| P06 | proxy bone queries no longer filtered by slot | **KILLED** | FAILED (failures=2) |
| P07 | firearm control gains inventory spawn flag | **KILLED** | FAILED (failures=1) |
| P08 | bone object identity comparison reduced to presence | **SURVIVED** | OK |
| P09 | variant-host proxy bone refresh removed | **SURVIVED** | OK |
| P10 | firearm control immediate release removed | **SURVIVED** | OK |
| P11 | explicit numeric ToString removed from JSON output | **KILLED** | FAILED (failures=2, errors=105) |

R02 changes the internal evidence multiplicity without changing the final verdict in these fixtures; it is still a rule-A coverage gap. R03 repairs P2-3 and survives, confirming the suite lacks the case-sensitive slot requirement. P08/P09/P10 are the discriminating-fixture gaps described in P3-1. The existing implementation still contains all three guards. P11's removal of ToString is rejected by both lint and the strict synthetic concatenation behavior; its errors are intentional mutation failures, not native compiler output.

**Archived-data reproduction and acceptance boundary**

Rejoined local `taped-light-probe-003/classification.json` with `taped-light-probe-006/observations.json` using the current report. Actual totals: **26 server_qualified, 0 geometry_missing, 415 not_server_evidencable, 141 excluded, 2 pending; 584 hosts**. Host/light pairs: 26 server_qualified, 28 geometry_missing, 830 not_server_evidencable, 2 pending. Integrity: cleanup clean, no issues or unexpected rows. Routes: 14 direct, 12 after the handguard prerequisite. R12 and Mich2001Helmet remain pending_client. FNX45_arrow and colored variants in the 26 are backed by their own observation rows, not borrowed verdicts.

The archive predates the new hook and cannot validate its new count/bone/control facts. The generated hook matches the author's byte count and hash. Real native compilation, DayZDiag, normal PBO/server testing, and the two-client presentation/switch/visibility tests remain unperformed and pending. `acceptance` remains `PENDING`, tier S / client pending; none of this enables production behavior.

**Merge condition:** implement P2-1/P2-2 with scoped conflict tracking, implement exact proxy-slot membership (P2-3), and make optional spawn-control parsing type-safe (P2-4). Add the four failing behavioral regressions to the owned test suite, then rerun the requested focused command. The P3-1 discriminating fixture improvements are recommended. Keep runtime acceptance pending; a client join is not required to author these source fixes.
