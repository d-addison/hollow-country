# Hollow Country CE mission delta

Original authored policy; private development only. Runtime acceptance pending.
The default is stock CE plus disabled experimental settings. Read
[INSTALL_AND_ROLLBACK.md](INSTALL_AND_ROLLBACK.md) before installation.

`economy-profiles/baseline.json` generates no CE registration or rate changes.
`contextual-pilot.json` opts into native usage-route additions for five essentials:
bandages in civilian settlements, batteries in towns/military areas, can openers
at hunting sites, and sewing/repair supplies at military sites. Native CE usage
is an area/building context, not a kitchen/room classifier. Generation retains
all stock usages because a types override replaces the complete usage list.
Generated complete entries retain stock counts, flags, lifetimes, restock, category, tags and tiers verbatim; their runtime merge behavior is unobserved.
Broader eligibility may redistribute stock supply; world counts and acquisition
time remain unmeasured. There are no guarantees or supplementary item spawns.

`diagnostic.json` separately enables five existing core logging defaults. Its
patch is checked against the exact source bytes. Logging volume and CPU cost
need measurement; keep diagnostics out of the ordinary baseline comparison.

`ce/types.xml` and `cfgeconomycore.append.xml` are committed **empty no-op**
files. They do not register or enable a candidate. Opt-in generation reads exact
hashed installed inputs and emits complete entries for only the selected changed
items, retaining every original field and replacing the full usage list with its
stock-preserving union. The installer rejects lost/changed stock fields. Generated
selected entries are local experiment data, excluded from the source handoff.
Do not copy full stock types.xml into Git. The append file is a fragment, never a
replacement for the installed core. Engine duplicate/merge behavior, including
partial-field defaults and effective eligibility, remains unobserved; complete
entries are a conservative experiment input, not evidence the engine uses them.

Apartments and barracks remain investigations: tenement candidates have zero raw
points; known barracks have native points. No placements, coordinates, lootmax or
mapgroupproto merge declarations are invented. Eligible geometry and actual CE
behavior must be observed in DayZDiag and normal PBO/server trials before any
loot-fix claim. Coverage, interiors/search context, high-tier exceptions, measured
balance and multi-route gameplay acceptance remain pending.
