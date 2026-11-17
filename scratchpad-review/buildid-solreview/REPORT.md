Review: buildid-solreview — Hollow Country #29 build identity, phase 1

No P0/P1 findings. One non-blocking P2 finding; no P3 findings.

- **P2 — Interior config aliases do not survive legacy-layout recovery:** `mods/HollowCountry/scripts/4_World/Interiors/HCInteriorModule.c:65` now admits `.70`, but `AllocateManifest` copies that spelling at line 100 and `PreserveLegacyManifest` still requires raw build equality at line 143. Changing only an existing config's canonical build to the admitted native spelling disables interiors during recovery despite identical layouts, epoch and seed. **Fix:** make interior config/manifest recovery alias-aware while preserving the stored manifest and journal identity; account for the store's exact serialization comparisons (`HCInteriorStore.c:64`, `:84`, `:112`).

The scratch regression executes the existing authored-method adapter with an explicit synthetic fixture. It confirms `SameBuild` accepts the two stamps, then fails on `PreserveLegacyManifest` returning false. This is a config-spelling edge case; unchanged canonical configs retain their previous recovery behavior. The new interior config test stops at the epoch guard and therefore does not cover recovery.

Checks completed:

- `Matches` uses exact equality for `1.30.164289` and `1.30.164289.70`; no prefix, suffix, trimming or numeric matching. Empty, whitespace, padded, malformed and adjacent-version strings are refused by admission gates.
- `CanonicalWorld` copies its input before the in-place `ToLower()` call. The installed `1_Core/proto/EnString.c:171` declares `ToLower()` returning an integer length; the authored helper correctly returns the copied string instead.
- Search registry/provider admission requires admitted engine/caller builds, writes canonical new manifests, and retains legacy stored manifests on rebind. Source pins, reviewed volumes, ownership, scan budgets and depletion checks remain intact.
- Infected and measured-interior build gates widen only to the two exact aliases. Native-script/asset SHA checks, catalog validation, experiment/trust flags and pending qualification checks are unchanged.
- Taped-light normalization preserves equality for unknown nonempty build strings, as the previous raw-equality code did; it adds equivalence only between the two admitted aliases. Canonical/native legacy journal headers remain compatible. Empty headers and foreign headers against an admitted live build refuse.
- Syntax suite passed against the installed cache. Manual inspection of added/changed Enforce statements found no ternary, leading logical operator, engine-type identifier collision, duplicate sibling local, inline out declaration, excessive concatenation or changed override parameter name. This is not native compilation evidence.

Validation performed without DayZ, Wine, network access or mutation testing:

```text
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_build_identity tests.unit.test_search_supply_provider tests.unit.test_infected_defaults tests.unit.test_infected_completion tests.unit.test_taped_light_service tests.unit.test_interior_measured_catalog tests.unit.test_script_syntax
Ran 200 tests in 9.782s — OK (exit 0)

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.unit.test_infected_production_rooms tests.unit.test_room_catalog_completion tests.unit.test_infected_admission tests.unit.test_search_economy_integration
Ran 150 tests in 9.656s — OK (exit 0)

PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scratchpad-review/buildid-solreview -p 'test_review_regressions.py' -v
Ran 1 test in 0.004s — FAILED (failures=1, exit 1)
AssertionError: False is not true : admitted native config alias refuses an otherwise identical canonical legacy layout
```

Test temporary directories were confined under this review directory. Tracked files and git state were not modified. The runtime contract was read locally; ignored specification, spec, plan and task documents missing from this worktree were consulted read-only under `/code/dayzsa_mods/docs/`. Native full-version observation is supplied task evidence, not a runtime result produced by this review. DayZDiag, normal PBO/server and applicable multiplayer acceptance remain pending.

Verdict: MERGE-WITH-FIXES
