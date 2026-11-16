# Completion execution evidence — 2026-11-16

This records execution of the [completion plan](../docs/specs/001-survival-overhaul/completion-plan.md).
It supplements the original 25-task roadmap and preserves all 48 requirements
and 68 original acceptance-test IDs. Product acceptance remains open.

## Implementation and review

- Shared finite search allocations, actor-bound reservation/attempt/result
  journals, explicit v2 sidecar migration and conservative orphan quarantine.
- Bounded native-emission relay chains, measured semantic-room interfaces,
  exact persistent member identity recovery, opt-in profile policies and
  frozen observed-clue retargeting of existing packs. Unknown membership stays
  reserved and unresolved; unsupported movement/door/activation stays unavailable.
- Read-only registered-recipe audit and live core crafting admission; interrupted
  core lifecycle cleanup; bounded 16 KiB settings reads.
- Pinned diagnostic-export CE candidate preparation with minimal structural edits.
  No invented real coordinates, coverage correction or eligibility result.
- Transactional private package install/upgrade/recovery/rollback, bounded ZIP
  admission, drift refusal and retained backups; portable runbook included.

Native API declarations were inspected in the installed 1.30 script snapshot.
Parallel workers owned separate scopes; independent review produced reproducible
CR-01–CR-08 findings. All eight were corrected and independently rechecked on
their recorded source snapshots. Regression tests and corrections are recorded in the
[review](experiments/EXP-completion-review.md) and area experiment reports.
Subagents used the host's native delegation tools. Banso provided the explicit
feature's spec/plan validation and workflow gates; this was not a Banso contracts
dispatch run or a completed gameplay verification phase.

## Executed checks so far

The integrated Banso `verify-offline` workflow passed in 30,878 ms after the
initial completion wave: behavioral tests, executable BDD, setup static checks
and runtime admission. At that snapshot discovery found 371 unit tests and 16
bound canonical offline scenarios. Four additional deployment feature scenarios
execute inside the deployment suite. Later source changes require final rerun;
these counts are historical rather than a claim about the final source.

`python3 -B -m tools.validate.project` passes: 48 requirements, 68 original test
IDs and 25 canonical tasks. This is traceability integrity, not gameplay proof.
Windows CI now executes deployment, coverage and package behavior, including
actual PowerShell helper functions against synthetic bytes. Remote results for
the final source are pending publication.

## Actual engine execution under Wine

Direct Windows PowerShell still fails with a WSL interop timeout. Copying the
unchanged official executables into a private Linux-filesystem cache enabled
Wine execution. No purchased assets or private signing material enter Git.

The actual server is 1.30.164289.70, executable SHA-256
`987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805`.
Early actual compiler failures exposed identifier collisions, expression
complexity and vector/int arithmetic; all were corrected with regressions.

| Run | PBO SHA-256 | Actual outcome |
| --- | --- | --- |
| 008 | `c71579a4d2f498771bcb81cbe7450a34ccc0522618d965432bfb7a39f0f273b4` | Game/World/Mission compiled, core settings self-test PASS, default-off initialization |
| 009 | `8339c144c658862e293bd5eadba65cc6d81b1ea0f61959334230799ff4f87159` | New core/crafting/infected snapshot compiled and initialized |
| 010 crafting | `1ba4caa424f5ebf84362196aee6a73d242c8b2d3e4e30d9a0a919207b9dae502` | Core self-test PASS, actual registered crafting definition/config checks passed, initialized |

Run 010 explicit settings SHA-256:
`74ea6001c7c8ed6680d573256b9e1e8b7293ce6ca9f0dac7d3bd06f1694902b0`.
Its script log SHA-256 is
`7d1ace791249c529ee04d7833d1bae45159cc3516a1378a7beb35042dc47619a`.
Machine reports are in `research/evidence/compiler-*-wine.json` and the private
cache retains original logs. Runs used isolated profiles/storage and forced
bounded termination after the result. No clean persistence restart is inferred.

Official DSSignFile/DSCheckSignatures positively verified the earlier development
PBO under Wine. The integrated 018 candidate was subsequently signed and verified
again; exact evidence is recorded below.

### Subsequent actual checks

- 011: oversized settings rejected before deserialization, original bytes kept.
- 012: malformed JSON rejected and preserved, but the engine emits a JSON
  `SCRIPT(E)`; the conservative harness reports failure rather than suppressing
  it. This is not counted as an error-free compiler smoke.
- 013/014: infected-enabled module admission and core self-test pass. Run 014's
  PBO `e0868ee3a53639795e21e33c0f03412c3b1d8b30c4157caf9abc3fa5021642ce`
  matches the frozen IC-03/IC-04/CR-06 implementation. Independent review confirms
  all recorded log hashes and the 90.792-second hold. No horde journal appeared.
- 015: unsupported settings schema rejected, original bytes preserved, no module
  initialization. Exact reports are retained in `research/evidence`.
- 016: the same PBO remained initialized for a 210.363-second hold, still with
  only settings/config files and no horde journal. The root cause is unresolved;
  periodic save and live-member restart recovery remain unverified. No player
  suppression or successful repeated callback delivery is inferred.

A later integrated Banso gate passed in 30,768 ms: 409 discovered tests and 18
canonical bound scenarios at that snapshot. New diagnostic catalogs, observer
veto policies and content hygiene still require final integration. Two actual
harness regressions failed before fixes: exited-launcher and post-read-deadline
false success. The corrected 26-test probe suite passed; extending its bounded
hold had a separate actual RED then 27 GREEN. Total runtime remains capped at
300 seconds and cleanup targets only its owned process group.

## Remaining gates

The final integrated offline Banso run passed in 31,532 ms, with 508 discovered
unit tests and 22 canonical bound scenarios (455 bound test executions). One
Windows-only test is skipped on Linux. The diagnostic hook extension had two
actual RED errors before implementation and 30 focused GREEN; the map-qualified
mission name had a separate actual failing regression before correction.

Run 018 compiled Game/World/Mission, passed the core self-tests and initialized
the integrated source in the actual dedicated server under Wine. Its PBO SHA-256
is `038a420209dbe4b830fbf41ba44e16be7e6c82fa9759a9bb32bf81a6bfd9cf6c`.
Official DSSignFile/DSCheckSignatures positively verified this exact PBO; see
[signing report](evidence/signing-018-wine.json) and
[checker output](evidence/signing-018-check.txt). No private signing key is in
Git or the delivery. This proves signature mathematics, not client enforcement.

The fresh Windows delivery is
`C:\Users\David\Downloads\HollowCountry-Development-20261116-v2`.
The strict unsigned ZIP was rebuilt twice identically, verified, installed and
rolled back using the actual archive in a disposable filesystem destination.
Its SHA-256 is `004234eb9fee0db75ecd570893554b70b74c45dd4d5803b7541937e579fc6063`;
see [roundtrip evidence](evidence/delivery-018-roundtrip.json). Signed addon and
public key are supplied separately; the ZIP remains explicitly unsigned.

Run 017 compiled diagnostic modules but emitted a native plugin SCRIPT(E), so
the smoke failed. Run 019's disposable mission produced no Mission/self-test
markers and timed out; absence of markers is not success. A map-qualified
disposable mission retry 020 compiled the mission and executed both authored
self-tests: infected scalar `true`, interior storage `true`, final `PASS` marker.
The actual native filesystem serializer/reload/corruption checks used reserved
synthetic epoch 900001. Native plugin errors and deliberate corrupt-JSON errors
remain in the log, so the conservative overall smoke is `compiler-error`, not
clean acceptance. See [020 report](evidence/compiler-020-diagnostic-storage-wine.json)
and [actual script log](evidence/diagnostic-020-script.txt). No inventory grant,
power-loss durability, periodic horde save or multiplayer proof follows.
Source publication, hosted CI and issue evidence updates are still in progress
at this report snapshot. The user subsequently requested unattended acceptance
automation; that additional framework has a separate specification and task ledger.

Clean native Windows and DayZDiag acceptance, real measured CE/interior/room geometry, native
inventory crash boundaries, audible locomotion/relays, two-client race/visibility
checks, observer-safe CE transitions, 3–6-player performance and the friend's
backed-up signed install/restart/rollback remain open. Client connection was
explicitly deferred. No offline test or Wine smoke closes those gates.
