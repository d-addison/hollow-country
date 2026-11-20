# COT owner permissions

COT is a subscribed dependency on the server and every client, immediately after
CF. Keep its original signed files and keys. Do not repack, copy into an HC addon,
or modify COT. Admin ids are never written to git or exported in a friend bundle.

Use the server's actual `-profiles` directory. COT stores settings beneath
`$profile:CommunityOnlineTools/`; its permissions framework stores roles in
`$profile:PermissionsFramework/Roles/*.txt`, players in
`$profile:PermissionsFramework/Players/*.json`, and individual permissions (when
that upstream build enables them) in `PermissionsFramework/Permissions/*.txt`.
These are local server state, outside this repository and its bundle allowlist.

The friend installer does this for you. Its Profiles step reads the server's own
`profiles/HollowCountry/admins.json` (`PlainIds`) and, for each valid 17-digit id,
makes sure `PermissionsFramework/Players/<id>.json` exists with `"admin"` in
`Roles`. An existing record keeps all its other fields and roles and only gains
`admin` if missing; a new one copies the schema of COT's
`Your_Steam64_ID.json` example when present, else is just `{"Roles": ["admin"]}`.
It is planned in the dry run, backed up and undone like every other write, and
prints only counts, never ids. A missing or invalid `admins.json`, non-17-digit
entries, and unreadable existing records are skipped. Run it with the server
stopped; ids not yet in `admins.json` are not invented.

Manual fallback (no `admins.json`, or a different layout): after the owner's first
authenticated join, disconnect and stop the server.
Back up the profile. Check the installed COT-generated
`PermissionsFramework/Players/Your_Steam64_ID.json` example and the matching player
record. Create a private `<owner Steam64>.json` alongside the example, using the
installed example's schema and setting `Roles` to `["admin"]`. If the owner
already has a record, preserve its other fields and roles. Use the owner's actual
authenticated Steam64 only on the server. Show Windows file extensions so the
file ends in `.json`, not `.json.txt`. Restart and reconnect, then verify COT's
role management UI recognizes the owner. Use that UI to grant narrower roles to
other operators; leave `everyone` unchanged. Never paste account IDs into source,
commit messages, public screenshots or Workshop descriptions.

Local installed source evidence, read in memory from Workshop item 1564026768
`addons/scripts.pbo` (no vendor source is shipped here):

- `3_Game/CommunityOnlineTools/JMConstants.c:225–234`: profile directories and
  `.txt` role / `.json` player extensions.
- `4_World/CommunityOnlineTools/Classes/Permissions/JMPermissionManager.c:44–56`:
  first-run example with the `admin` role.
- `4_World/CommunityOnlineTools/Classes/Permissions/JMPlayerSerialize.c:41–55`:
  explicit Steam64 file takes precedence over the generated GUID record.
- `4_World/CommunityOnlineTools/Classes/COTModule.c:103–109`: default role creation.

These paths describe the inspected installed build. Recheck its generated example
after a COT update. No join, permission grant or role persistence was exercised by
this source change; native Windows compilation and joined-client checks are pending.

## Seeing Expansion AI

COT's map has no AI and its ESP "Player AI" view only covers a radius around the admin.
Use the Hollow Country admin map (Pause key, layer `ai-units`); steps in
[FRIEND_SERVER_AI_RUNBOOK.md](FRIEND_SERVER_AI_RUNBOOK.md#seeing-the-ai-admin-map-snapshot-file-log).

## HC server authorization adapter (#203)

HC admin ingress now accepts either the private `admins.json` allowlist or a
live server permission provider granting the named permission
`HollowCountry.Admin`. The adapter is requested by default; the operator can
opt out by creating
`$profile:HollowCountry/acceptance/COTAuthorization.disable` before startup.
`EnableAdminMap` still controls the entire admin module. Neither opting out nor
an unavailable provider grants access. The existing validated allowlist remains
usable independently. A malformed or interrupted allowlist still refuses module
startup; the permission adapter never bypasses store recovery.

**The COT binding is missing, not verified or silently admitted.** Repository
[acceptance documentation](ACCEPTANCE_CHECKLIST.md) records the public API names
`GetPermissionsManager`, `GetPlayer`, and `HasRole`, but no receiver, parameter,
return-type, build guard, registration API, or call-site line evidence. This
worker was prohibited from inspecting COT source. Those names alone do not
justify a callable binding or treating an `admin` role as an HC grant. HC does
not read COT role/player files, invoke undocumented signatures, or infer permission
from possession of the UI. No COT or Expansion call was added.

The source-ready seam lives in `HCAdminModule.c`:

- Obtain the running module's `HCPermissionAdapter()` using the existing module
  registry, then bind a server-owned subclass of `HCAdminPermissionPort` through
  `HCBind(port)`. Bind only after the real COT permission service is available.
- `HCReady()` must reflect that service's current lifecycle.
  `HCAllowed(PlayerIdentity sender, string permission)` must query the actual
  authenticated server sender and the named permission on every call. It must
  return false for unknown identities, unloaded roles and permission errors.
  The base port refuses both methods. Only one live owner can bind; another
  owner cannot replace or unbind it.
- Unbind that exact port with `HCUnbind(port)` when its service stops. Admin
  shutdown clears the reference; each new startup requires a fresh binding.
  Revocation is rechecked at ingress, queued dispatch and delayed reply delivery.
  Grants are never copied into `admins.json` or cached as authorization.

The adapter uses `HCOperationalStatus.HCPublish` and print-on-change reasons.
Core status polling refreshes its status. Missing binding logs
`[HC Admin] COTAuthorization reason=cot_permission_binding_missing runtime=PENDING`
once per reason change; a bound but unavailable provider reports
`cot_permission_provider_unavailable`. `ready` is derived only from a running,
requested adapter with a bound, available provider. The main module's existing
ready receipt describes the loaded allowlist, not COT readiness. Server-only
checks cite native `3_Game/Global/Game.c:1120` (`IsServer`),
`3_Game/gameplay.c:636` (`GetGame`), `:370` (`GetPlainId`), and
`1_Core/proto/EnSystem.c:397` (`FileExist`). No new settings registry row,
module slot, mission file, distance or gameplay limit is introduced.

Both authorization sources share the existing 32-session ingress arrays,
per-peer cadence, replay tickets and one-command queue. COT-authenticated peers
never index the allowlist with `-1`. Revoked sessions can yield their slots;
capacity exhaustion refuses ingress. No additional tick scan or controller is
introduced. The adapter performs constant work per permission check; session
selection examines at most the existing 32 slots.

Integration still requires separately authorized COT API inspection/documentation
with exact file:line evidence and a binding against that build's real signatures.
After integration, boot the normal server/PBO and DayZDiag, grant/revoke the named
permission, stop/restart the provider, test the opt-out, and use one client to
verify that an unauthorized peer receives no live snapshot or admin data. The
synthetic adapter tests do not establish these results.
