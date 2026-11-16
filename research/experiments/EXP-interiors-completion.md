# Interior/search source completion increment — 2026-11-16

Status: substantive source authored and offline regression passing. Native
compilation, placement, inventory durability and multiplayer acceptance remain
pending. This increment belongs to Banso T014/T015, FR-005/FR-006, NFR-001–004
and AC-005. It does not close those runtime obligations or enable production.

## Scoped plan and delivered behavior

1. Inspect the installed 1.30.164289 scripts and existing implementation; retain
   stable building/site IDs, schema-1 manifests and default-false hard gates.
2. Add executable failing crash-cut, version, budget and ownership policies.
3. Add a shared finite search pool; reconcile every registered allocation before
   furnishing/search admission, including unavailable buildings and orphan files.
4. Implement explicit forward journal migration without replacing old manifests,
   claims or layouts; reject changes, missing versions and unsupported downgrades.
5. Separate reservation intent, output attempt and terminal receipt; never replay
   an ambiguous attempt, refund its allocation or delete generated player loot.
6. Persist orphan/partial-placement retirement and limit prop reuse to pointers
   already owned by this process. Run focused and full offline regression.

All six source steps are implemented. Native observations listed below remain
required. No files outside the assigned interior/search/test/report scope were
changed by this worker; unrelated shared-workspace changes belong to other work.
No commits were made.

## Finite allocation and reconciliation

`HCInteriorSearchPool` owns the precommitted manifest allocations: at most 12
sites, at most four one-unit Rag allocations and two Battery9V allocations per
explicit epoch. Empty results remain supported. Duplicate slots/site identities,
unsupported items, oversized identities and excess quotas fail initialization.
The pool opens only once; reopening cannot reset a spent allocation. Every
registered site consumes the same pool rather than maintaining a private quota.

`HCInteriorStore.ReconcileAll` visits all 12 supported slots before placement.
Claims, attempt markers and receipts are matched by exact site ID, allocated
item, actor and schema. Recognized journal files at an unassigned slot stop the
store and remain intact. Registered but unresolved buildings keep their original
allocation. Retirement and uncertain claims are never returned to available
supply. `Supply(item)` returns a new count of allocated/available/reserved/spent/
quarantined units plus `Frozen`, so a persistence failure does not hide escrow or
silently advertise a usable pool. Search still requires `Healthy()`.

This is the shared **supplementary search pool**, not an implemented CE debit.
The installed CE script surface does not demonstrate a transaction joining its
global counts, supplementary reservations, native inventory creation and profile
files. World/inventory/hoarder reconciliation with CE remains an engine experiment
and production gate. No CE count API or global inventory scan was invented.

## Migration and orphan handling

New epochs create an immutable `journal-v2.json` sidecar containing explicit
schema 2, source schema 1 and the complete unchanged layout/allocation manifest.
Existing schema-1 epochs require `MigrateLegacyJournal: true` once; after an exact
sidecar exists, subsequent starts do not require that flag. The original epoch
directory, manifest, backup, site IDs, claim paths and result paths remain.
Legacy exact schema-1 completions remain spent; legacy interrupted reservations
remain quarantined. New reservations use schema 2.

Missing version fields default to zero and are rejected. A corrupt/oversized or
changed sidecar stops startup, with no backup rewind or file replacement.
World/build/epoch/seed mismatches fail before root initialization. This is a
forward **journal** migration. Arbitrary house-transform/layout/catalog remapping
is intentionally not implemented: it needs measured transforms and an explicit
allocation-preserving mapping, rather than silently rerolling an existing world.

Unresolved buildings, foreign/ambiguous prop matches and partial placement create
an immutable `hold_SLOT.json` and retain the allocation as quarantined for this
epoch. Even a corrupt hold remains a blocking marker. Future starts do not remove
that hold or automatically adopt a nearby prop. A matching static prop alone
cannot establish ownership. Repeated placement in this process can reuse only
one exact-transform object whose pointer is already in `m_Objects`; multiple
matches, foreign pointers and mismatched transforms quarantine the slot. Partial
cleanup deletes only objects newly created in that particular attempt. It never
deletes a foreign prop, retained reused prop, generated item or player inventory.

## Interrupted reservation protocol

The server now follows this order:

1. Revalidate the existing duration/range/LOS/owner/item/empty-hands gates and
   preflight inventory capacity. Full inventory leaves the site unconsumed.
2. Exclude the unit in the shared pool, then write/read back the unique schema-2
   `claim_SLOT.json` intent with exact allocation and actor.
3. Validate that intent and write/read back unique `attempt_SLOT.json` before
   any inventory call, including the empty-result completion path.
4. Call native `CreateInInventory` at most once. Never retry or spawn on ground.
   A null return remains consumed/quarantined. Normalize a quantity-bearing item
   to one unit; no refund or duplicate compensation is issued.
5. Validate intent/attempt/actor/output type and write a unique result receipt.
   Capture the output's four-part `EntityAI.GetPersistentID` as a forensic hint;
  it is not a replay token, proof of save completion or item ownership mechanism.
  Both attempt and completion also require the central pool to remain reserved;
  changing stale action data back to phase 1 cannot revive a quarantined unit.

On recovery, only an exact completed journal returns spent. No marker means
available; **any** interrupted, torn, mismatched or orphaned journal means
quarantined. A schema-2 completion without its attempt is damaged. An intent
without an attempt is still quarantined: absence is not proof that a native
grant did not happen when filesystem durability/order is unproven. Global I/O
failures freeze further claims, and terminal pool states cannot become available.

## Actual TDD and offline evidence

The focused command is:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_interiors_contract.py -v
```

- Initial recorded RED: 29 tests, 16 failures and two missing-method errors,
  including the missing `RecoverJournal`, migration, orphan and pool policies.
  The declaration extractor also needed fixing to distinguish a method definition
  from an earlier call. See `interiors-completion-tdd-red.txt`.
- A second real behavioral RED exercised the actual authored pool methods and
  demonstrated that reopening a used pool returned true and refunded its state:
  33 tests, one failure. `interiors-completion-reopen-red.txt` preserves it.
- A third RED demanded explicit accepted journal versions instead of inheriting
  DTO defaults: 34 tests, one missing-algorithm failure. See
  `interiors-completion-version-red.txt`.
- A fourth RED required a central-pool reservation check before grant/completion:
  35 tests, five failures through the missing `Reserved` authored method, including
  the stale-action regression. `interiors-completion-resume-red.txt` preserves it.
- Actual native compiler RED (old `796175f` PBO under Wine):
  `error_2026-11-16_15-49-17.log` reports `World` and `Slot` member names
  conflicting with native types. The full small error report is preserved in
  `interiors-completion-native-red.txt`; native animation skeleton and method
  linkage diagnostics are retained rather than classified as harmless.
  Installed declarations `3_Game/Global/World.c:1` and
  `4_World/Entities/GardenBase/Slot.c:22` were checked, and the scoped identifier
  scan found no other declared native class/enum names among interior identifiers.
  Regression RED: 36 tests, one failure for those collisions, preserved in
  `interiors-completion-native-identifier-red.txt`. Renamed **all scoped DTO fields
  and references** to `MapName` and `SlotId`, including pool and synthetic DTOs.
  Neither replacement name occurs in the installed native class/enum scan.
  The stable generated ID string, epoch directory and claim filename formats
  are unchanged. Pre-compilation draft JSON using the uncompilable `World`/`Slot`
  field spellings needs reviewed conversion to `MapName`/`SlotId`; it is not
  silently migrated or claimed byte-compatible. No accepted native save existed
  from the uncompilable prototype. Native recompilation after this fix is pending.
- Actual compiler-002 RED: `error_2026-11-16_15-53-33.log` reports a broken
  expression at InteriorModule line 207 (`int owned;`), also diagnosed by the
  coordinator as the reserved `owned` keyword. Its SHA-256 is
  `5caceb8d920d9a6f5a05cd979f16ff78971bfa47c2e82533722a4ae8f4106839`;
  tested PBO SHA-256 was
  `ff5e82149fcaa0b63ba0e9b67c3d45ca58d5ab3731ae2e846ae6706a7e846a55`.
  The native diagnostic says `Broken expression (missing ';'?)`, not an explicit
  keyword message. Renamed both the counter and scalar-policy parameter to
  `ownedCount`, and the object foreach variable to `ownedObject`. A regression
  caught the parameter as well: 37 tests, one failure, recorded in
  `interiors-completion-owned-red.txt`. Other compiler-002 failures were in the
  infected worker's scope and were not modified here. Recompilation remains pending.
- Final focused GREEN: **37 tests**, including the original 21, synthetic crash
  cuts, exhaustive flag/version combinations, two-consumer exclusion, quota and
  duplicate-owner rejection, restart reconciliation and reopening rejection.
  `interiors-completion-tdd-green.txt` preserves actual output.
- Full shared-workspace discovery passed **302 tests** in 12.157 seconds at this
  integration snapshot. Other workers were active; this count is not a claim that
  their changes were authored here. Subsequent main integration should rerun the
  final combined gate after all workers freeze.
- `git diff --check -- mods/HollowCountry/scripts/4_World/Interiors tests/unit/test_interiors_contract.py`
  passed at the scoped snapshot.

Fixtures are under `tests/fixtures/runtime/interiors-completion-*`. The existing
offline BDD scenario “Preserve finite interior allocations and depleted search
sites” binds to this test module and therefore executes these tests as well.
Scalar methods and the pool's restricted if/foreach/assignment subset are
executed from authored Enforce source, using explicit synthetic DTOs/lists.
Source assertions additionally inspect call ordering and authority wiring. This
restricted translator is not an Enforce compiler or a native persistence test.

The direct-path BDD invocation `python3 tools/validate/bdd.py` failed because its
test subprocess import path omitted the repository root (`ModuleNotFoundError:
tools`); concurrent infected work also had a pending regression at that snapshot.
The failed output is preserved as `interiors-completion-bdd-attempt.txt`, not a
green record. The coordinator should run the existing module-form BDD gate after
all workers freeze. No BDD pass is claimed for that failed invocation.

`HCInteriorSelfTests.RunStorageProbe(900001)` was expanded for real native
intent/attempt/empty-result, interrupted and torn-claim recovery and pool summary.
It requires a fresh synthetic diagnostic epoch, creates no inventory output, and
was **not run by this worker**. It must not be presented as crash durability proof.

## Installed native API evidence

Inspected only the private installed snapshot at
`/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289`.
No purchased source was copied into this repository.

| Installed file | Inspected surface | SHA-256 |
| --- | --- | --- |
| `3_Game/Entities/EntityAI.c` | Lines 3372–3379: four-part persistent ID and lifetime; ID belongs to EntityAI | `c56a1ed22224f31766bf80b8c547eb265f98a2b7997a73f00f8b89933d6cbbe3` |
| `3_Game/Entities/Object.c` | Existing position/orientation/model transforms; no demonstrated static-prop persistent ownership ID | `1b1b031948b82c111e9be8b9b0bbef8495c07842d7436d9c3111950e8a3ee95b` |
| `3_Game/Systems/Inventory/Inventory.c` | Lines 876–896: native CreateInInventory implementation, returns entity/null; no joint ledger transaction | `e259fbd18febd32b5874603d480547b371534639bc1d814383c2608e4942fcaf` |
| `3_Game/tools/JsonFileLoader.c` | SaveFile opens WRITE, FPrint, CloseFile; separate deserialize/serialize operations | `2d96c61dfabd99967683d0856ee5e2b1c7d06c18166b7f245bba4da1617bfff4` |
| `1_Core/proto/EnSystem.c` | ReadFile, CloseFile, FPrint, FileExist, MakeDirectory; no demonstrated fsync or joint inventory transaction | `8be625999a04df22813052e93fe658c24c82c97b257ebef86b106279a95db188` |
| `3_Game/CE/CentralEconomy.c` | CEApi declarations and native ECE_DYNAMIC_PERSISTENCY semantics | `f0d6825945d41ad24bf91c44a9b8f7f77d75e9e376940a5f567ca3d2ce504076` |
| `3_Game/ObjectSpawner.c` | Native nonpersistent startup prop flags and explicit CE persistence option | `7955aca08479686ffe6a70a431050cdd62c24035c09011b16028bd69981ea368` |

## Bounds and exact remaining constraints

- Maximum 12 allocations and six nonempty output allocations; startup duplicate
  validation is O(12²). Startup reconciliation checks 12 fixed slots and at most
  three journal reads per registered site, each below 32 KiB, plus the immutable
  manifest and sidecar. Holds require existence checks, not an unbounded read.
  Files outside the supported fixed-slot namespace are not enumerated or adopted.
- Each layout currently has two trial props, at most 24 startup props overall.
  Each spatial query is limited in radius and rejects a returned list over 256;
  the native cost of producing that list still needs profiling. There is no live
  furnishing, global player-inventory scan or recovery loop on ticks.
- **Durable exactly-once inventory atomicity is not supplied by the inspected
  script surface.** File readback is not fsync. A crash/power loss can persist
  inventory while losing all markers, or persist a marker while losing inventory.
  Creation and quantity normalization are separate calls and can also be
  interrupted. Quarantining ambiguities favors no replay and can lose a reward;
  it does not prove no duplicate across arbitrary disk write reordering.
- Native compilation/type checking, both serializers' handling of malformed
  input, four-part ID availability/save ordering, filesystem error injection,
  actual restart/crash recovery and interference from other mods remain pending.
- CE world/storage/inventory counts and protected quota integration remain
  pending; this pool is finite supplementary escrow, not whole-world accounting.
- Existing trial offsets remain explicitly unmeasured. Actual house transforms,
  safe clearances/navmesh/door swing, proxy selection, collision/replication and
  placement lifecycle must be observed. No geometry or measured fit was invented.
- Two-client action races, cancellation/death/disconnect, feedback/replication,
  normal signed-PBO/server operation and target-load timing remain pending.
  `PlacementAccepted()` and `SearchAccepted()` still return false. Diagnostic
  switches stay restricted to `DIAG_DEVELOPER`; no production flag was enabled.
