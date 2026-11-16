# EXP-CE-offline-audit — installed Chernarus CE

Observed UTC: 2026-11-16T19:18:48.069555+00:00. **T0 offline source audit only; no runtime acceptance.**
Requirement: FR-003 / AC-003; raw findings support future FR-004 investigation.

Input: installed `DayZServer/mpmissions/dayzOffline.chernarusplus`, read-only.
Output: [installed-ce-audit.json](../evidence/installed-ce-audit.json).
No vanilla XML, assets or full source dump copied into Git. JSON source paths
are mission-relative, with sizes and SHA-256; no private absolute source paths.
No authoritative classname catalog was supplied.

## Provenance against the official pins

Compared installed bytes with the ledger in
[official-sources-2026-11-16.md](../official-sources-2026-11-16.md), pinned to
Bohemia commit `f220b2918b1d79a5055b1ee9be70c0ec1516e876` / `DZ_130`.
All six local CE file hashes and byte lengths match. The utility audits the first
four files below; the two limit-definition files were hashed for comparison only,
not validated or used to resolve vocabulary references. This comparison proves
these file identities, not the installed executable build or CE runtime behavior.

| Mission-relative source | Bytes | Installed SHA-256 | Official pin |
| --- | ---: | --- | --- |
| `cfgeconomycore.xml` | 2,082 | `b5a88d6d5a79e8c1e272d63a608eb02107d444169aa993348430dd6c9f4dd503` | MATCH |
| `db/types.xml` | 1,057,471 | `d477597418530c3e226fa18b296290eb9669210d9a37a301eaf7e3426e5e1040` | MATCH |
| `mapgroupproto.xml` | 1,229,651 | `44e70165da1b13de1ab2451aea43413955a7e81acd2d7016ba957787632585a6` | MATCH |
| `mapgrouppos.xml` | 1,538,112 | `3eeaad9786a73c339f61f6e6ad203f0732e36b88f27333978cc8b4beece9cec4` | MATCH |
| `cfglimitsdefinition.xml` | 1,280 | `07f4dedfb53e97b6150eb2374c539604b5800b8ec4c4ae243e26419aa77d4d26` | MATCH |
| `cfglimitsdefinitionuser.xml` | 1,360 | `09a7c7d1b355c1bae72dda75d13db5d718af3508ce9797ec0c55b6cb41a9d9f8` | MATCH |

Auditor SHA-256: `cd11fab01d60a073fd5ecb68b0e574631a95c5bb0d1a96f1d0ea2d5a0bf40a10`.
Regression suite SHA-256: `ac5fccae71c7d68d7e9f79ffb6b7f575fdfbef99ecb0b555db1f47e05a0d8c8a`.
Saved JSON SHA-256: `37b230e60afda79309acf5f43730a155a25f505dc66ca168d9345205b724fa8c`.

## Raw findings and remaining concerns

- Audited sources: 4; no modular `ce/file` declarations in the core file.
- Type entries/unique names: 2,382/2,382.
- Prototypes: 436; containers: 831; raw XML points: 11,074.
- Placements: 11,679; dispatch blocks: 75; proxies: 264
  referencing 99 distinct type names (unverified without a catalog).
- Final `inputs_complete=true`, `valid=false`: six unresolved possible-alias names
  account for 148 placements. Three `zero_raw_points` warnings remain.
- Resolved placed raw-point subtotal: 168,333.
  Overall placed raw-point total remains null because of unresolved placements.
- These are XML counts, including points under disabled containers/groups. They
  establish neither loot eligibility/accessibility nor engine classname matches.
  `engine_eligible_loot_points=null`, `building_classes_verified=false`.

| Unresolved placement name | Placements | Unverified prototype candidates |
| --- | ---: | --- |
| `Land_wreck_truck01_aban1_blue` | 19 | `Land_Wreck_truck01_aban1_blue` |
| `Land_wreck_truck01_aban1_green` | 35 | `Land_Wreck_truck01_aban1_green` |
| `Land_wreck_truck01_aban1_orange` | 28 | `Land_Wreck_truck01_aban1_orange` |
| `Land_wreck_truck01_aban2_blue` | 26 | `Land_Wreck_truck01_aban2_blue` |
| `Land_wreck_truck01_aban2_green` | 17 | `Land_Wreck_truck01_aban2_green` |
| `Land_wreck_truck01_aban2_orange` | 23 | `Land_Wreck_truck01_aban2_orange` |

Possible aliases are hints only. No case, path, `Land_` or `.p3d` normalization
was promoted to an exact match. Whether the engine resolves these names requires
native observation; the audit's conservative rejection is not proof the shipped
mission is invalid. Category/usage/tag/value/dynamic-event vocabularies,
`areaflags.map`, other CE files, effective overrides, geometry and native spawning
remain outside this bounded audit. Missing files can also inherit native defaults;
this tool expects an explicit snapshot and does not reconstruct PBO fallback.

## Regressions and corrections

The original auditor rejected 172 shipped entries solely because
`nominal=0` and `min>0`. The same shape was observed in the pinned official data.
A synthetic regression now accepts it while retaining checks on positive nominal
relationships. Cross-file declared type overrides now warn and retain raw
inventory entries without simulating a merge; within-file duplicates still fail.

Other reproduced false passes/rejects fixed with synthetic regressions: missing
or escaping non-types declarations, unknown/empty proxy type references, aliases
reported as resolved coverage, nonfinite cluster dimensions/dispatch probability/
point flags/selected numeric core defaults, BOM XML catalog detection, control
characters in catalogs, and reusing an audited source as a catalog. Present
non-types declarations are hashed and explicitly marked not schema-audited.
No probability upper bound or undocumented schema/engine semantics were inferred.

Exact regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/unit -p test_ce_audit.py -v
```

Actual pre-fix red: **54 tests, 49 failing assertions/subtests, 2 errors, exit 1**
(the main concurrent integrated run saw 143 tests with the same failures/errors).
Actual post-fix green: **54 tests, 0.373s, OK, exit 0**.
Temporary synthetic missions are external to the repository. This suite proves
offline parsing/report behavior, not native CE behavior. Only the two assigned
Python files and these two newly authorized research artifacts were edited.

Reproduce the installed read-only audit with the actual installation directory
in `DAYZ_SERVER_MISSION` (use `-B` to suppress bytecode):

```sh
python3 -B -m tools.audit.ce_audit --mission "$DAYZ_SERVER_MISSION"
```

Expected final CLI exit: **1**, for unresolved aliases; the 172 false nominal/min
errors are removed. The saved report was produced by `audit_mission()` and strict
JSON serialization, then its input hashes were rechecked against installed bytes.
No game process, DayZDiag/PBO test, eligible-point observation or classname
confirmation was performed. T2–T5 gates remain pending.
