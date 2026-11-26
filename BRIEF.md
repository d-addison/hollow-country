# Brief: HC-E058 extensions (raw borrow released by its owner)

Worktree: this directory, branch rt/v16-lint58 (from rt/v16-integ). You own ONLY:
tools/validate/enforce_lint_remove.py, tests/unit/test_enforce_lint_remove.py,
the HC-E058 rows in docs/pitfalls/enforce-pitfalls.md and audit/CHECKS.md.
Do not touch mods/**. Do not start DayZ, Workbench, the compile gate or a soak.
Do not commit BRIEF.md or any candidates/notes file.

HC-E058 today flags a non-ref local of a non-Managed class that borrows an element of an
owning `ref` container and is used after `Remove`. Extend it to these release shapes
(each needs a positive and a negative unit test):
1. Field replacement: `T x = obj.F;` (T non-Managed, F a `ref` field) then `obj.F = <anything>`
   then any use of x (including writing x back: `obj.F = x;`). Real bug, soak 195/196 AV:
   HCGroupStore.SaveStep held `state.Invitations` in a raw local, replaced the field, restored it.
   Not flagged when the local is `ref`, or when x was first stored into another owner
   (inserted into a ref container / assigned to a ref field) before the release.
2. Indexed store `C[k] = y;` on an owning container releases the borrowed C[k] (HCRemoveRoute shape).
3. `Resize(0)`, `Clear()` and replacing the whole container field count as releases.
4. A field store through the borrowed local after the release counts as a use.
5. Tolerate whitespace in `Find (`, and tie a parameter to its container when it was obtained
   through the container's Find slot in the same function.
Managed-derived types (Object/EntityAI/PlayerIdentity/any class deriving Managed, resolve via the
existing class index) are never flagged.

Acceptance: run the new rule over the tree; every new finding is either fixed-by-design (list it)
or a true positive you list in your report with file:line (do not edit mods). Then:
- python3 -B -m pytest tests/unit/test_enforce_lint_remove.py -q
- agent-run --memory 4G -- python3 -B -m tools.validate.enforce_lint --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289
- python3 -B -m tools.validate.preland --native-scripts ~/.cache/hollow-country/native-scripts/scripts-1.30.164289 --changed origin/main
Report: findings list, test output tail, preland result. Commit on the branch; do not push or merge.
