# Hollow Country Batch B review — batchb-solreview

One read-only review pass of the eight requested source/package/test paths. No tracked files or git state were intentionally changed; reviewer artifacts are confined to this directory. No mutation testing, DayZ, Wine, or network use. The active owner decisions take precedence over older design material.

## Blocking finding

**P1 — rollback can overwrite a file outside the selected mission through a hard-linked staging file.** `tools/package/gameplay.py:420-435` permits `cfggameplay.next` in the managed directory without checking its identity or contents, then opens it with `write_bytes(backup)`. `child()` rejects symlinks but accepts hard links. After a valid install, place a hard link at `hollow-country-gameplay/cfggameplay.next` pointing to an unrelated file outside the mission, then invoke rollback: all receipt/config/gear checks pass, the unrelated file is truncated and replaced with the backup bytes, and rollback reports success. The reproduction uses only synthetic files under this scratch directory; it changes no production code. This requires an existing unexpected hard link, rather than occurring during an ordinary untouched install, but directly violates the requested path-escape/drift refusal and causes data loss.

Fix: reject unexpected/multiply linked staging files before any write and create the rollback replacement with exclusive creation in the managed directory (for example, `tempfile.mkstemp`), then atomically replace the config. Do not open an existing staging inode for writing. Preserve refusal and outside-file immutability in regression coverage, including dry-run preflight.

## Nonblocking findings

- **P2** — `mission/hollow-country/gear/hardscrabble.json:7`, `tools/package/gameplay.py:247`, `tests/unit/test_gameplay_delta.py:330`: clothing health `0.6..0.85` includes pristine condition; native `DAMAGE_WORN_VALUE` is `0.7`, and installed clothing configs use that cutoff. Fix all clothing ranges to a strictly worn interval such as `0.6..0.69`, enforce it in the validator/test, and correct the documented range.
- **P2** — `tools/package/gameplay.py:223-225` and `:256-265`: substring bans plus classname syntax do not enforce the small-item contract; a cargo set containing native weapon `M4A1` is accepted by `validate_preset`. The supplied committed preset itself contains only the requested items. Fix by allowlisting the permitted rag/chemlight/canned-food classes and reviewed civilian clothing per slot.

## Checks and native evidence

- Ownership/merge: the leaf allowlist excludes `lightingConfig`, `disablePersonalLight`, `StaminaData`, and `MovementData`; recursive merge preserves unknown keys and the native version. Temperature deltas retain the source monthly curve with the selected modest reductions. Obstruction, heavier wet gear, and complete enabled hit-indicator settings match the inspected native fields/enums.
- Spawn format: inspected installed `4_World/Classes/PlayerGearSpawn/CfgPlayerSpawnDataJson.c` and `CfgPlayerSpawnHandler.c`. The root is one `PlayerSpawnPreset`, paths are resolved under `$mission:`, slots choose one weighted alternative each, and cargo chooses one weighted set. Every supplied cargo set contains one item; there are no clothing children. Native `missionServer.c:565-576` selects the preset path before the default starting-kit path. This is source evidence, not observed spawn behavior.
- Infected config: installed `characters_zombies.pbo` declares `DZ_Characters_Zombies`, `ZombieBase: DayZInfected`, LeftLeg health 100, and `RightLeg: LeftLeg` without a separate Health override. The source patch reopens that existing class/parent and specifies only LeftLeg Health hitpoints 50; it contains no delete directive, zone-array replacement, or replacement listing of the other zones. The mummy's explicit 1000-health override remains outside scope. The baseline parser test does not execute the engine's composed config merge; preservation of all zones/armor/transfer values and crawl behavior still need native config/server acceptance.
- Install/rollback: supplied tests verify source/checksum refusal, symlink refusal, ownership revalidation, untouched neighbors, separate CE ownership, and byte-exact normal rollback. The hard-link case above is uncovered by those tests.
- Packaging: the authored profile, preset, and standalone standard-library helper are included in the handoff allowlists. Runtime/release acceptance remains pending.
- Compile rules: this batch adds config declarations, Python and JSON, with no changed Enforce `.c` methods/statements. No scoped ternaries, leading logical operators, engine-type locals, duplicate sibling locals, inline out declarations, excessive concatenations, or override parameter changes were introduced. The existing syntax suite passed; it is not a native compiler.
- Required spec paths are absent in this confined worktree. Read the copies under `/code/dayzsa_mods/docs/` plus this worktree's `docs/RUNTIME_IMPLEMENTATION_CONTRACT.md`; consulted the parent Banso plan/tasks as design context. No acceptance was inferred from those documents.

## Executed validation

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_gameplay_delta tests.unit.test_package tests.unit.test_deploy`

Result: **97 tests, OK, 1 skipped**, 27.693 seconds.

`TMPDIR="$PWD/scratchpad-review/batchb-solreview/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax -v`

Result: **7 tests, OK**.

`TMPDIR="$PWD/scratchpad-review/batchb-solreview/tmp" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scratchpad-review/batchb-solreview -p regression_checks.py -v`

Result: **3 tests, 3 failures** against the unmodified implementation: outside file overwritten with original config bytes; clothing `0.85` exceeds `0.7`; `M4A1` validation raises no error. These are reviewer regression demonstrations, not source mutation tests. Fixes and passing reruns are left to the owner under the read-only contract. `git diff --check` also passed.

Verdict: FIX-THEN-MERGE
