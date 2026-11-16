# Shared runtime implementation

Status: authored; native compilation and execution pending.

User requested source/package completion before connecting a client. One addon
owns settings, server-only module startup, bounded periodic work and shutdown.
The six feature flags default false. Invalid schema, limits or dependencies
prevent module startup; existing invalid settings are preserved for diagnosis.

TDD: the five `RuntimeSettingsTests` first failed to import the absent
`tools.validate.runtime` module, then passed after its implementation:
`python3 -B -m unittest discover -s tests/unit -p test_runtime_settings.py -v`.
These check operator JSON admission only. The Enforce native self-test performs
settings assertions when the engine loads the addon; it has not run yet.

API inspection used the installed 1.30.164289 script snapshot identified in the
[integration contract](../../docs/RUNTIME_IMPLEMENTATION_CONTRACT.md).
`3_Game/tools/JsonFileLoader.c` provides boolean LoadFile/SaveFile with errors.
`1_Core/proto/EnSystem.c` provides FileExist/MakeDirectory.
`5_Mission/mission/missionServer.c` provides OnInit;
`3_Game/gameplay.c` provides the mission finish callback.
`3_Game/Global/Game.c:1550` exposes GetCallQueue; installed native classes use
CallLater and Remove for repeating callbacks. This is API evidence, not proof of
compiled integration, timing, shutdown ordering or module correctness.

Native Windows process launches from this WSL session time out at the interop
socket. The user launched the isolated vanilla server successfully; its startup
is recorded separately. No Hollow Country code was loaded in that vanilla run.
Signed package loading, native self-test logs, client registration, save/restart,
two-client authority, collision/audio and calibrated load remain required.

Independent review found CORE-001: configured tick period was used as elapsed
time. Corrected to consecutive GetTickTime samples, reset on Start; no catch-up
loop. Nonpositive deltas or gaps over 300 seconds stop modules conservatively.
Declaration inspected at `3_Game/Global/Game.c:914`. This source correction has
not been executed in the native VM; native timing regression remains pending.

The settings admission scenario first failed BDD admission as unbound, then its
binding was implemented. Five bound offline scenarios executed 164 tests and
passed (temporary-file sandbox access was required). Nine BDD admission tests
also passed. These counts precede the other module workers' integration.
