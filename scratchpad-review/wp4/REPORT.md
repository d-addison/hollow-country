# B04 WP4 — D4 variant substitution

Source implementation only; runtime acceptance and production enablement remain pending. Module integration is assigned to its owner below.

## Files changed

- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedProfiles.c`: separate config validity from supported-choice checks, preserve requested IDs, resolve actual descriptors, and add bounded substitution diagnostics.
- `mods/HollowCountry/scripts/4_World/Infected/HCInfectedPolicy.c`: add per-choice disposition and reason functions; preserve ordinary resolution of 3/4.
- `tests/unit/test_infected_wave.py`: require disposition alongside existing fallback intent; support the requested module-form unittest command.
- `tests/unit/test_infected_contract.py`: test disposition/reason semantics; extend the restricted translator for authored profile helpers with explicit synthetic collaborators.
- `tests/unit/test_infected_variants.py`: port the audit D4 counterexample and exercise supported-only, mixed, all-unsupported, invalid and empty maps, disabled preference, descriptor safety, and aggregate diagnostic counts.
- `scratchpad-review/wp4/REPORT.md`: this report.
- `.banso-writer/commit-message`: requested writer metadata (not committed).

No Module, State, Navigation or other shared product files were edited. No Git commands, DayZ, Wine or PowerShell were run; no writes under `/mnt/d` were performed by this task.

## Decision and traceability

This implements the explicit-disposition portion of B04 WP4 / D4 / #20, traced to T020, AC-007.f/i, FR-008/013, AI-007 and AUD-004. It does not complete the physical-variant or full appearance/location roster requirements.

`ValidateMap(configured, false)` checks input syntax: exactly four IDs in 0..5, or an allocated empty template. Unsupported 3/4 requests remain valid input and remain unchanged in both operator arrays. `ValidateMap(configured, true)` additionally requires a nonempty map containing only supported attention-policy choices; this is why the original audit counterexample now fails closed. Neither result establishes native qualification. `ConfiguredVariant` preserves requested IDs for valid populated maps, including mixed/all-unsupported maps. Either empty/invalid map retains the existing whole-config native fallback (-1).

| Requested ID | Disposition | Reason | Resolved descriptor / remaining scope |
| --- | --- | --- | --- |
| 0 ordinary | supported | attention_policy_only | ordinary_wanderer; native doorway/distraction comparisons pending |
| 1 reactive | supported | attention_policy_only | reactive_infected; response/audio/recognition pending |
| 2 searcher | supported | attention_policy_only | persistent_searcher; actual measured room traversal remains WP5/pending |
| 3 stalker | unsupported_substituted_native | stalker_physical_unqualified | 0 / ordinary_wanderer; no slow/quiet/pausing capability granted |
| 4 heavy | unsupported_substituted_native | heavy_physical_unqualified | 0 / ordinary_wanderer; no forceful/loud/door capability granted |
| 5 responder | supported | attention_policy_only | group_responder; local chain/audio acceptance pending |
| 6 crawler | invalid as base map choice | invalid_base_variant | native injury overlay descriptor retained; injury/route acceptance pending |

Other IDs are invalid. The word `supported` is limited to the existing authored attention-policy selection, not physical behavior, recognition, rooms or native runtime acceptance. `RequestedDescriptorName(3/4)` retains proposal labels for diagnostics; `DescriptorName(3/4)` returns `ordinary_wanderer`, so requested labels cannot masquerade as actual capability.

## TDD record

Tests were authored before changing Profiles/Policy. Actual RED command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_wave tests.unit.test_infected_contract tests.unit.test_infected_variants -v
test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants (tests.unit.test_infected_variants.InfectedVariantTests.test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants) ... FAIL
AssertionError: True is not false : Requested stalker/heavy map must not count as available without a capability disposition
Ran 42 tests in 0.104s
FAILED (failures=2, errors=14)
exit=1
```

The second failure is all-unsupported map admission; errors identify the not-yet-implemented disposition/reason, diagnostic and requested-descriptor helpers. Synthetic translated source execution is not native runtime evidence.

Actual GREEN with the requested command:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_wave tests.unit.test_infected_contract tests.unit.test_infected_variants -v
test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants (tests.unit.test_infected_variants.InfectedVariantTests.test_stalker_and_heavy_maps_do_not_admit_unavailable_physical_variants) ... ok
Ran 42 tests in 0.099s
OK
exit=0
```

Broader verification:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -v
Ran 2371 tests in 76.137s
OK (skipped=1)
exit=0

python3 -B -m tools.validate.bdd
Ran 1277 tests in 35.993s
OK (skipped=1)
Bound offline scenarios: 61; runtime acceptance: NOT EXECUTED
exit=0

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_script_syntax tests.unit.test_script_identifiers -v
Ran 8 tests in 0.781s
OK
exit=0
```

Additional read-only Python check used `tools.setup.probe_runtime.native_type_names` on the pinned cache, `lint_hook(..., explicit_numbers=True)` and `max_statement_plus` on each changed Enforce file. Actual output:

```text
HCInfectedProfiles.c: findings=[], max_binary_plus=6 (limit=8)
HCInfectedPolicy.c: findings=[], max_binary_plus=1 (limit=8)
```

No ternary, leading logical operator, duplicate local, engine-type identifier collision or undeclared out argument was introduced; the helpers have no out arguments. Numeric log fields use explicit `int.ToString()`. Offline lint is not Enforce compilation.

## Module owner integration request

Added public static helper in Profiles:

```c
static void LogUnsupportedSubstitutions(HCInfectedConfig config)
```

Exact call, once during startup after valid configuration is available:

```c
HCInfectedProfiles.LogUnsupportedSubstitutions(m_Config);
```

Do not call per actor/tick. Each invocation emits at most one record for stalker and one for heavy, aggregating repeated slots across civilian and military maps. Counts mean configured stance slots, not actors. There are at most 8 validation-slot visits plus 16 counting-slot visits, no entity scans, allocations of gameplay objects, config writes, persistent latch or unbounded retry. A new module startup can diagnose its configuration again. Null, disabled, invalid or partially empty configurations produce no substitution records because selection retains native fallback; the existing generic map diagnostic remains responsible for missing/invalid maps.

Replace the original map diagnostic block at Module lines 128–133 with the following, preserving the missing-map diagnostic intent without calling an explicitly substituted populated map "missing":

```c
bool variantMaps = HCInfectedProfiles.ValidateMap(m_Config.CivilianVariants, false);
variantMaps = variantMaps && HCInfectedProfiles.ValidateMap(m_Config.MilitaryVariants, false);
if (variantMaps)
{
    variantMaps = m_Config.CivilianVariants.Count() == 4 && m_Config.MilitaryVariants.Count() == 4;
}
if (m_Config.EnableVariantPolicies && !variantMaps)
{
    Print("[HC Infected] variant preference enabled; explicit stance maps missing or invalid; native profiles retained");
}
HCInfectedProfiles.LogUnsupportedSubstitutions(m_Config);
```

This diagnostic block does not admit a capability; keep WP1 qualification/admission gates independent. The Module owner must integrate and rerun shared tests. That file was intentionally untouched here, so startup logging is **not yet wired** in this worktree.

Example synthetic output for two stalker and two heavy slots across both maps:

```text
[HC Infected] variant requested=3 name=careful_stalker disposition=unsupported_substituted_native reason=stalker_physical_unqualified resolved=0 actual=ordinary_wanderer count=2
[HC Infected] variant requested=4 name=forceful_heavy disposition=unsupported_substituted_native reason=heavy_physical_unqualified resolved=0 actual=ordinary_wanderer count=2
```

## Installed native source evidence

Inspected snapshot root: `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/`. Policy functions call no engine API. Profiles uses only the following native surfaces (including its existing selection path):

| Surface | Exact installed source |
| --- | --- |
| `array.Count()` | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/1_Core/proto/EnScript.c:380` |
| Array element access (`Get` declaration, existing stance indexing) | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/1_Core/proto/EnScript.c:399` |
| `int.ToString()` | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/1_Core/proto/EnConvert.c:30` |
| `Print(void var)` | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/1_Core/proto/EnDebug.c:96` |
| Existing `ZombieBase.IsZombieMilitary()` | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/4_World/Entities/Creatures/Infected/ZombieBase.c:113` |
| Native true military classification examples | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/4_World/Entities/Creatures/Infected/ZombieMaleBase.c:130`, `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/4_World/Entities/Creatures/Infected/ZombieFemaleBase.c:133` |
| Native stance field read through the existing authored `HCIndividualStance()` bridge | `/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289/4_World/Entities/Creatures/Infected/ZombieBase.c:10` (field), `:96` (existing 0..3 initialization); authored bridge is `mods/HollowCountry/scripts/4_World/Infected/HCInfectedNative.c:52` |

Inspection establishes declarations only. It does not establish observed movement, audible effort, doors or multiplayer behavior.

## Remaining gaps

- Module integration above remains with its owner; this slice alone does not close D4 end to end at startup.
- Stalker/heavy physical behavior remains SOURCE_MISSING and requires WP3 native evidence. No speculative locomotion, audio, contact, door, health or damage controller was added.
- Full recognizable appearance/location probabilities and all seven proposed roster behaviors remain tracked, unqualified requirements. Empty default maps remain empty. Persistent room search depends on WP5, local audible response on WP6, and broader admission on WP1.
- DayZDiag compilation, normal PBO/server testing and actual startup diagnostic observation remain pending. Movement/audio/visibility acceptance needs two clients; performance budgets remain provisional for the active 3–6-player load.
- Local `docs/SPECIFICATION.md` and `docs/specs/001-survival-overhaul/{spec,plan,tasks}.md` are absent from this portable worktree. Read the canonical files under `/code/dayzsa_mods/` as read-only design input, plus the assigned audit and local runtime integration contract. The active task's decisions and scope take precedence; no planning artifact or runtime gate was marked accepted.
