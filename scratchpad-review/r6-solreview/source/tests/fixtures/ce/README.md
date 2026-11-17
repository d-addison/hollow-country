# Synthetic CE audit fixtures

Every classname, group name and coordinate here is invented for offline tests.
These files contain no extracted game data and identify no real map location.
`synthetic_valid` includes a zero-raw-point group and a group with points under
`lootmax="0"` to prevent confusing raw XML counts with engine loot eligibility.
`synthetic_known_types.txt` is authoritative only within these synthetic tests.
Other invalid and modular variants are generated under `synthetic_run_*` during
unittest runs, then cleaned up. No fixture is evidence of DayZ loadability,
building accessibility or actual loot opportunities.
