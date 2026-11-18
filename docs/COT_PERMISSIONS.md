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

After the owner's first authenticated join, disconnect and stop the server.
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
