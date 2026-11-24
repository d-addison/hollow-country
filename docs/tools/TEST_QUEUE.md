# Test-service queue

`tools/release/test_queue.py` runs the native-adjacent checks for worker commits on the lead
host: `preland` (with `--changed <base>`), `wb` (Workbench compile) and `gate` (the Wine
compile gate to Mission). Workers never run the gate, `wb_compile` or DayZ themselves.

```sh
python3 -B -m tools.release.test_queue submit --commit <full sha> --checks preland,wb,gate [--base origin/dev]
python3 -B -m tools.release.test_queue run-next   # lead host only; runs the oldest queued or held job
python3 -B -m tools.release.test_queue status [job-id] [--json]
python3 -B -m tools.release.test_queue list [--json]
```

- State is JSON under `.hc-queue/` in the main checkout (git-ignored, shared by every linked
  worktree; override with `HC_QUEUE_DIR`). One file per job, replaced atomically.
- `submit` needs a full 40-character sha that exists, a resolvable base (pinned to a sha at
  submit) and a submitting checkout with no uncommitted tracked changes.
- Every run happens in a clean detached worktree `/code/hc-worktrees/queue-<sha8>` at the pinned
  sha. It is created and removed without force. A worktree that will not remove cleanly is kept
  and recorded (`worktree_kept`); an existing one that is dirty or at another sha is refused.
- The whole job holds the one shared host lock (`tools.release.host_lock`, holder `test_queue`),
  so it serialises with `compile_gate`, `wb_compile`, `friendcycle` and the other native tools.
- Caps: `gate` runs as `agent-run --memory 12G`, `preland` and `wb` as `--memory 3G`. Exit 137
  is recorded as `oom`, fails the job and is never retried: narrow the input first.
- Play pause: before every check the queue runs `python3 -B -m tools.setup.winproc query
  DayZ_x64.exe`. A running (or unknown) client, or friendcycle/another tool holding the host
  lock, leaves the job `held`, not failed; the next `run-next` resumes only the unfinished
  checks. Nothing is ever stopped or killed.
- Each check writes a result record: `sha`, `check`, `rc`, `status` (`pass`/`fail`/`oom`/`held`),
  `log` (under `.hc-queue/logs/`), `started`, `finished`, `advisory`, `note`.
- `wb` is advisory (its failure does not fail the job, and the record says so) until the
  `Calibration status: N/M` line in `docs/tools/WORKBENCH_COMPILE.md` records agreement on all
  rows in the current corpus. From then
  on `submit` drops `gate` unless `--wave` or `--release` is given (the Wine gate runs once per
  integration wave and per release). Until then every gated commit gets the gate.

## needs-host-check

`preland` and `generated_digests --check` cannot verify host-only inputs (native cache, Windows
tools) on a worker checkout. They no longer count a skip as a pass: the run exits 3 with
`status=needs-host-check` and prints the exact `submit` line for the commit. On the lead host,
where the inputs exist, nothing changes. `generated_digests --waive-unavailable` keeps the old
exit 0 for local test builds (`verify_release`) and the CI profile.
