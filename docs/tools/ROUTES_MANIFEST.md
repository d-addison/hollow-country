# Route manifest paging (w3, build 167 follow-up)

Implemented-unverified. No native compile, boot, timing, client or upgrade verdict is
established by the offline generator checks.

`tools.package.ai_route_precompute --write` emits the schema-1
`travel/routes-manifest.json` header and `routes-manifest-NNN.json` pages. The
additive `HashPageVersion=1` format retains the graph fields and four source-file
identities used by the shared compact-road reader. Source hashes are flattened in
source order. Page zero holds catalog-page identities; subsequent pages hold at
most 80 source hashes. Every generated header/page is capped at 6,144 bytes. The
header pins each page's path, byte size and SHA-256. Packaging and generated-digest
inventories include the pages.

The road source pin file `travel/gapcode_routes_source-pages.json` is written and verified by
`tools.audit.gapcode_routes_pins` (`--check` writes nothing). Its road row follows the pin that
`tools.audit.gapcov_routes` authors in `ai/caravans.json` (`gapcov_graph_source`), which the
catalog index must repeat; the tool refuses when they disagree or when the installed road bytes
no longer match that pin. Mission source rows are path declarations only, because
`ai_route_precompute` computes fresh identities for authored mission files on every run, so
ordinary mission edits never stale the file. Its SHA-256 is part of the manifest header, so a
change to it is followed by `ai_route_precompute --write`.

The catalog validates the header in one visit, then reads each page, verifies its
SHA-256 with the existing provider adapter in at most 128-byte updates per visit,
and parses it in a separate visit. All pages must pass before candidates resolve.
Missing, oversized, reordered, mismatched or malformed pages refuse admission with
`ROUTE_MANIFEST_*` reasons. The existing source, catalog identity and row-total
checks remain. Graph opening has a separate visit from catalog parsing/resolution.
The shared graph owner reads only the small compatible header.

The existing `[HC Routes] catalog=loaded` receipt appends `manifest_ms` (peak
manifest-phase visit), `page_ms_max` (peak catalog-page visit), and `graph_open_ms`
(shared graph acquisition/open). These use TickCount and HCWorkBudget's calibrated
ticks-per-millisecond conversion; GetTickTime is fixed within an engine tick and
cannot measure an atomic parse. These receipts include reads and validation, not
only deserialization.

The same receipt also splits the peak `page_ms_max` visit into its four catalog-page
sub-steps. One catalog page is admitted over several visits, one sub-step per visit,
and each field is the peak of that sub-step over all pages:

| Field | Sub-step measured |
| --- | --- |
| `page_read_ms_max` | The bounded read of the page file (one native read call per visit). |
| `page_parse_ms_max` | The JSON parse plus the schema, kind, identity and row-count checks. |
| `page_fields_ms_max` | The two required-field scans of the page text (`island`, then `connected_both_directions`, via `HCJsonFields.Every`); the larger of the two is kept. |
| `page_insert_ms_max` | The final step that inserts the page rows into the catalog (at most the page size). |

A page that fails any sub-step is refused with its `ROUTE_*` reason and its stage state
is reset. Rows become visible only in the insert step, after every earlier check passed,
and the stage survives interleaved work, so a page is never read twice. Compare these
four against the 4 ms slice target the same way as `page_ms_max`.

Upgrade replaces this mission-data set together; partial sets refuse admission.
The route catalog keeps no profile copy or manifest-hash cache, and revalidates
mission data at every start. The profile route-geometry cache uses its existing
build/world/policy/key validity, independent of the manifest document hash. No
profile migration or destructive reset is needed for the new document layout.
Lead validation still requires a previous-release profile upgrade and cold/warm
boot evidence on the exact merged build.

Lead follow-up: native compile to Mission, then compare the three new peak timings
with `[HC Startup] owner=routes_catalog ms_max` against the 4 ms slice target and
20 ms R2 release ceiling. Existing catalog pages are unchanged (up to 16,264 bytes
in this tree); their parse duration has no isolated native measurement yet. If
`page_ms_max` exceeds 4 ms, reduce page rows/bytes in
`tools/audit/gapcov_routes.py` (outside this worker's assigned scope), update the
packaging inventory, and regenerate all dependent pins. Also investigate
`graph_open_ms` if it exceeds 4 ms. Missing engine measurements remain pending;
byte caps alone do not establish the slice target or release acceptance.
