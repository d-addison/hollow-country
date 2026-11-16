# Native execution access recheck

C01 / T002–T004. On 2026-11-16 the coordinator retried native PowerShell using a
15-second outer timeout and only `$PSVersionTable.PSVersion.ToString()`.
The attempt exited 1 with `WSL ERROR: UtilAcceptVsock:271: accept4 failed 110`.
It did not reach PowerShell. `/run/WSL` contains no interop socket and the
configured `/run/WSL/1_interop` is absent; no WSLInterop binfmt entry is visible.
Restarting WSL would terminate the active development session and was not done.

An independent fallback tested the installed official 64-bit `DSCreateKey.exe`
under installed Wine 9.0 with a fresh isolated win64 prefix, 45-second timeout
and key output directory outside Git. The tool exited 5 with a null-write page
fault before creating any key. The private signing output directory remained
empty. This establishes neither an official signature nor Windows execution.
No private material was read, committed or included in development packages.

Those two initial attempts did not run a DayZ compiler. Further investigation
found a working fallback: copying the unchanged official executable from the
Windows mount to the Linux filesystem allowed Wine to execute it. Source and
copied DSCreateKey SHA-256 both equal
`81a100eeb190fab4492970d0e6f051db5c025bf8a4adc2815c57ed9fe3022067`.
The generated private key is outside Git with mode 0600; its bytes are not
included in any report. Official DSSignFile and DSCheckSignatures copied in the
same way signed and positively verified the prior `796175f` development PBO.
Actual checker output: `Signature addons\hollowcountry-796175f.pbo.HollowCountryDevelopment20261116.bisign is OK`.

A complete isolated Chernarus server copy outside Git then launched the actual
`1.30.164289.70` server under Wine. Its executable SHA-256 matches the installed
server: `987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805`.
The first headless run waited on an invisible compiler dialog; a private Xvfb
display exposed it and produced actual compiler logs. Baseline errors included
reserved `World`, `Slot` and `Entity` identifiers. The next source snapshot
reached further compiler errors (`owned`/`local` keywords). These are actual
engine compiler failures, not static-test or invented native observations.

`tools/setup/wine_compile_probe.py` now stages a fresh PBO/profile/storage,
classifies real compiler/lifecycle logs, bounds execution and terminates only its
own process group. Probe classification tests first failed on the missing module,
then five tests passed. Its unsigned disposable config is not a live deployment.
Every run records PBO/server/log hashes and forced-stop status. It neither
accepts gameplay nor tests clean save shutdown or native Windows execution.

Normal Windows execution still fails at WSL interop. Wine compiler/signature
results must remain distinguished from native Windows, diagnostic builds,
client behavior and performance acceptance. Client connection is deferred and
does not prevent these compiler checks.

## Compiler progression

Pass 004 reached a genuine `Formula too complex` policy expression failure.
Pass 005 reached `Incompatible parameter 'living'` in vector division; the code
now uses the installed native reciprocal-multiplication pattern. Pass 006
compiled Game (441 files) and World (2341 files) without SCRIPT(E), on PBO
`c71579a4d2f498771bcb81cbe7450a34ccc0522618d965432bfb7a39f0f273b4`.
It exited 255 before mission initialization. Pass 007 added stock identity fields;
an actual private Xvfb screenshot showed `BattlEye initialization failed`.
The isolated copy lacked the official server DLL. The next correction copies
that installed dependency into a fresh experiment and sets its explicit BEpath.
No BattlEye bypass or gameplay acceptance is claimed by the config flag.

Each experiment's `compiler-report.json` and original logs remain in the private
cache. A successful module compile does not imply mission initialization or a
successful save/restore. The original failed startup artifacts are preserved.

## Actual initialization — compile-008

With the official dependencies present and explicit isolated BEpath, the actual
server initialized BattlEye and Steam, compiled Mission (220 files / 470 classes)
and emitted these exact authored messages at 16:07:11 local time:

```text
[HollowCountry][SelfTest] Core settings PASS in native script VM
[HollowCountry] Server initialized; experimental features require explicit settings
```

All six generated feature flags were zero. PBO SHA-256 is the compile-006 hash
above; script-log SHA-256 is
`fbfe9032d90c462b3e080fbfd87f7c024c4b89d11dc61795b2ef1ead6e14c033`.
The harness stopped its process group after the marker; forced stop is recorded.
This is an actual script-VM self-test and default-off lifecycle smoke under Wine,
not a clean save/restart, diagnostic build, Windows or multiplayer acceptance.

Independent review also found launcher-lifetime cleanup and final-log budget
gaps (CR-03/04). Three new regression cases first failed on missing helpers.
The corrected harness cleans its owned group even after the leader exits and
caps discovery, file count, per-file and aggregate bytes with streamed reads.
Ten focused tests pass, including a real forked child that ignores TERM after
its launcher exits; bounded group cleanup stops it. No prefix-wide kill is used.

## Feature and invalid-settings probes

Compile-010 enables only crafting in an explicit bounded settings file. The
actual registered-recipe/config audit, core self-test and initialization passed.
The exact source/PBO/log binding is recorded in `EXP-crafting-completion.md` and
`../evidence/compiler-010-crafting-wine.json`; inventory execution is untested.

Compile-011 supplies 16,385 spaces. The actual module rejects the document before
JSON deserialization, preserves the original file byte-for-byte, and does not
initialize experimental features. The report records `settings-rejected`.

Compile-012 supplies the single byte `{`. The installed JSON deserializer emits
`SCRIPT (E): JSON ERROR` and returns failure. Hollow Country then reports invalid
settings, preserves the original byte and does not initialize features. The
harness deliberately reports `compiler-error`/exit 1 because its conservative
error classifier takes precedence; this is a negative input outcome, not a
successful error-free smoke or an unresolved script compilation diagnostic.
The original log and report remain preserved. No error signature is suppressed.

The seed reader was developed with a real missing-helper RED then 13 focused
GREEN tests. It accepts at most three exact config/journal names, 64 KiB each,
and rejects links and unexpected paths. Optional bounded post-initialization
holding permits periodic journal checks in fresh copied profiles. These controls
do not make forced shutdown a clean-save test or establish live member recovery.
