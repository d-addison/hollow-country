# Friend server: mods, build and ports

Status: procedure for the private 3–6-player friend server. Nothing here has been
exercised on that server yet; the owner's local session (`docs/LOCAL_ACCEPTANCE_V1.md`)
comes first. Server settings are in `mission/hollow-country/INSTALL_AND_ROLLBACK.md`
(Server configuration for the friend server).

## Mods each player needs

Hollow Country is private and not on the Workshop, so the DayZ launcher cannot
download it. The friend hosting the server has access to the private repository.
They build and sign `@HollowCountry` from source on their own machine with DayZ
Tools (see `docs/LOCAL_ACCEPTANCE_V1.md`, Build, sign and verify) and their own
private key, which never goes into Git. They install the matching public
`.bikey` under the server's `keys`. They then give every player the same signed
`@HollowCountry` folder through a private channel. Each player keeps it on disk
and loads it with `-mod=` or with "Add local mod" in the DayZ launcher. Every
player must run the same build as the server.

| Set | Server | Each player | Notes |
| --- | --- | --- | --- |
| Base | `@HollowCountry` in `-mod` | the same `@HollowCountry` (same build) | No Workshop mod is required. Community Framework (CF) is not needed for the base mod. |
| SNAFU subset (optional) | SNAFU Weapons in `-mod`, its key | subscribe to SNAFU Weapons | SNAFU does not depend on CF. |
| Tactical Flava subset (optional) | Tactical Flava in `-mod`, its key | subscribe to Tactical Flava | Tactical Flava does not depend on CF. |
| PvE patrols (optional) | CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI in `-mod`, each mod's key, `@HollowCountryExpansionAI` | subscribe to CF, Dabs Framework, Expansion-Core, Expansion-Animations and Expansion-AI | Only this set needs CF. Expansion is never repacked or bundled. |

Load order in `-mod`: CF, then Dabs Framework, then the Expansion mods (Core, then
Animations, then AI), then SNAFU, then Tactical Flava, then `@HollowCountry`, then
`@HollowCountryExpansionAI`. Every player's `-mod` list must match the server's
client-side list. A mismatch is refused at join.

Port forwarding (the friend's router, UDP): the game port (`-port`, default 2302)
plus the next three ports (2303–2305), and `steamQueryPort` (27016 by default) so
the server shows up in the browser. Keep BattlEye and `verifySignatures = 2` on.
