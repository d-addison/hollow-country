# Friend server reports

Redacted status reports from the friend's Windows server, uploaded after a play session so the mod author can
see what the server logged without asking for raw files.

## What a report is

`server-report.bat` (in the server bundle) runs `tools/setup/server_report.py`, reads the newest server `.RPT`
in the server profiles folder, the newest script log and counts from the Hollow Country profile state, and writes
one file named `hollow-country-report-<UTC date-time>.md`, for example
`hollow-country-report-20261118T101530Z.md`.

Sections, in order: Summary (verdict and counts), Build and version, Mod list, Hollow Country lines (every
`[HC ...]` line once with its count), Script errors (the `SCRIPT (E)` line with its context, repeats counted),
Search Houses refusals (count per reason), AI (`[HC XAI]`, `[HC Expansion AI]` and Expansion AI error lines),
Player connect (is `Player connect enabled` logged, plus event counts only), Crash and minidumps, Economy (CE)
load lines, Profile state summary (file and entry counts, never contents) and Redaction.

## Redaction

Everything below is removed before the file is written, and a final check refuses to write the file if one is
still present:

- Steam64 ids (17 digits starting 7656), BattlEye GUIDs (32 hex characters), IP addresses and ports.
- Player names and ids in connect, disconnect and kick lines; `player=`, `identity=` and `steamid=` fields.
- Windows user paths (`C:\Users\<name>` becomes `C:\Users\<user>\...`), e-mail addresses and the server name.
- Any whole line that mentions a password, an admin remote-console setting, a key or a token.

The file is at most 512 KB. Raw `.RPT`, `.log`, `.ADM`, `.mdmp` files and anything under the profiles folder are
never uploaded and the repository hygiene check rejects them.

## How to upload

Pick one. Both are public, so read the file once first.

1. Issue (simplest): open a new issue titled `Server report <date>` using the "Server report" template (it adds the
   `server-report` label) and drag the `.md` file onto the issue. Say in one line what you did in the session.
2. Pull request: add the file under `reports/friend-server/` on a branch and open a pull request.
