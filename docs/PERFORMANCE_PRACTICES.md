# Performance practices for Hollow Country modules

Lessons from the native boots of builds 091–097. Use them when you write or
review a module, and cite them in worker briefs. A rule here is not native proof;
the server boot is still the test ([HC Perf], [HC TickCost], [HC Step], [HC Save]).

## Shared tick budget

- Core ticks once per second. The shared pool is `MaxTickWorkItems` (32) per
  tick, handed out through `HCUnitBudget` slots (`HCTickWork().HCTakeFor`).
- On a starved tick the first take on a slot is forced, and later takes on
  that slot in the same tick are refused. Two consumers on one slot starve the
  second one completely if the first always runs first in that tick.
  - Build 096: the regional route check ran after the site director on
    `AI_SITES`, got zero units for the whole boot, and AIRoles plus human-ai stayed
    not ready.
- **Give every independent consumer its own slot.** A new slot needs all five
  pieces in one commit:
  1. an `HC_WORK_*` const in `HCUnitBudget.c`, with `HC_WORK_CONSUMERS` raised;
  2. `HCRegister("<NAME>", config.TickWeight_<NAME>)` in `HCUnitProfile.c`;
  3. a `TickWeight_<NAME>` field and its load line in `HCPerfSlices.c`;
  4. `HCAdd("Performance.TickWeight_<NAME>", "int", 1, 1, 64, "HCPerfConfig")`
     in `HCPerfSettingsRegistry.c`;
  5. the name in the `CONSUMERS` list of `tools/validate/tick_cost_report.py`.
- Take the shared admission once per tick, before the local page budget is
  reset. Do not take it again for every item in the inner loop; see
  `gapcode_routes_catalog.c` `HCStep`.
- Reserve what you will really use. A worst-case `HCCharge` (for example
  MaxObjects+MaxPlayers+MaxRouteNodes) empties the pool for everyone else and
  pins every consumer to one item per tick.
- TickCount units: `ticks_per_ms` is about 10000, so 1 tick = 0.1 µs. A
  `[HC Step]` `worst_tick_ticks=233753` is 23 ms.

## Saves and file I/O

- A synchronous store `Save()` does the whole job in one tick: encode, write the
  temp file, read it back, copy the backup, copy the primary and read again.
  For a 72 KB store that is 20–35 ms in that tick (Holdouts re-pin on 096).
- In tick code, mark the store dirty and let its `HCSaveScheduler` job write
  it in stages (`HCStagedSaveImage`). Keep a synchronous save only where a
  durability barrier needs it, such as an intent written before an entity
  is created, and say so in a comment.
- Bulk migrations (a template re-pin, a schema upgrade) should change all rows
  and then save once. Don't republish and save each row on its own tick.
- Keep the exact text you validated (`m_VerifiedText`) and compare against it
  rather than re-reading and re-parsing the prior file on every checkpoint.

## Loops and lookups

- Use `map<string, bool>` / `map<string, int>` id sets for membership and
  joins. A nested scan of two id lists is O(n·m). At 528 sites × 523
  localities that is about 276k string compares in one call (`HCReconcileLocalitySites`).
- Don't call `array.Find` / `IndexOf` or scan a string inside a per-row loop
  over an unbounded list. Build the index once, outside the loop.
- Scan large text through `HCTextWindow` (lint HC-P001).
- Split big loads such as JSON packs or catalogues into resumable stages with a
  per-tick item cap. Report progress, not one line per item.

## Logging

- Never `Print` once per row or per tick on a path that repeats. Latch it: keep
  the last line or a reported flag and print only on change (HC-38 receipt:
  130 identical lines in 8 minutes on 096).
- Write `Print("" + line)`, not `Print(line)`, because the engine logs the
  declaration of a bare variable (lint HC-L001).

## Data that must match

- Module defaults that mirror mission data (the locality catalogue, site
  policies) must be byte-identical to the mission copy. A stale default
  degrades readiness, which looks like a performance problem but isn't one.

## Reading a boot for spikes

1. `[HC Perf] window=N`: `work_p50/p95/max` and `mod_max` per module. Rank
   `mod_max` to find the module.
2. `[HC Step] owner=<Module>`: `heaviest` and the per-stage ticks show
   which stage spiked.
3. `[HC TickCost]`: a slot with `starved == granted` in every window is
   starved; with `granted=0` it never ran.
4. `[HC Save] job=<Module>`: staged save cost. A module with no
   `[HC Save]` line saves synchronously.
5. Tell one-time costs (migration, first pass after a pin change, pack load)
   apart from steady state. Only steady state counts against budgets, but a
   one-time cost above about 50 ms per tick is still worth splitting.

Budgets stay provisional until they are measured at the target load of 3–6 players.
