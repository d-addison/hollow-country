"""Static safety checks only: these do not parse or execute PowerShell or DayZ."""
import json
from pathlib import Path, PureWindowsPath
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "tools/setup"

class WindowsSetupStaticTests(unittest.TestCase):
    def setUp(self):
        self.script = (SETUP / "New-LocalVanillaRuntime.ps1").read_text()
        self.guide = (ROOT / "docs/LOCAL_WINDOWS_SETUP.md").read_text()
        self.baseline = json.loads((SETUP / "installed-vanilla-baseline.json").read_text())

    def test_setup_cannot_launch_or_change_host_services(self):
        code = "\n".join(line for line in self.script.splitlines() if not line.lstrip().startswith("#"))
        for forbidden in (r"(?im)^\s*(?:\$\w+\s*=\s*)?Start-Process\b", r"(?i)\bStop-Process\b", r"(?i)\bInvoke-Expression\b", r"(?i)\bRemove-Item\b", r"(?i)\bEnable-PSRemoting\b", r"(?i)\bSet-ExecutionPolicy\b", r"(?i)\bNew-NetFirewallRule\b", r"(?i)\bnetsh\b", r"(?i)-filePatching\b", r"(?i)-serverMod=", r"(?i)-mod=", r"(?i)\bupnp\s*="):
            with self.subTest(forbidden=forbidden):
                self.assertNotRegex(code, forbidden)

    def test_whatif_gate_precedes_all_writes(self):
        self.assertIn("SupportsShouldProcess = $true", self.script)
        gate = self.script.index("if (-not $PSCmdlet.ShouldProcess(")
        creation = self.script.index("New-Item -ItemType Directory", gate)
        self.assertLess(gate, creation)
        self.assertIn("Runtime already exists; refusing to overwrite", self.script)
        self.assertIn("[System.IO.FileMode]::CreateNew", self.script)
        self.assertIn("[System.IO.File]::Copy($Source, $Destination, $false)", self.script)
        self.assertNotRegex(self.script, r"(?i)-(?:Force|Recurse)\b")

    def test_launch_plan_keeps_all_mutable_paths_isolated(self):
        for required in ("-ip=127.0.0.1", "-port=2302", "-mission=$missionDestination", "-storage=$storageDestination", "-profiles=$profilesDestination", "-BEpath=$battleyeDestination"):
            with self.subTest(required=required):
                self.assertIn(required, self.script)
        self.assertIn("'maxPlayers' = '6'", self.script)
        self.assertIn("'verifySignatures' = '2'", self.script)
        self.assertIn("'forceSameBuild' = '1'", self.script)
        self.assertIn("ReparsePoint", self.script)
        self.assertIn(r"D:\HollowCountryLocal", self.script)

    def test_baseline_has_safe_unique_pinned_mission_paths(self):
        entries = self.baseline["mission_files"]
        self.assertEqual(len(entries), 43)
        names = [entry["path"] for entry in entries]
        self.assertEqual(len(names), len(set(n.casefold() for n in names)))
        self.assertIn("init.c", names)
        self.assertIn("db/messages.xml", names)
        for entry in entries:
            p = PureWindowsPath(entry["path"])
            self.assertFalse(p.is_absolute() or p.drive or ".." in p.parts)
            self.assertFalse(any(part.lower().startswith(("storage", "profile", "log")) for part in p.parts))
            self.assertRegex(entry["sha256"], r"^[a-f0-9]{64}$")
            self.assertGreater(entry["bytes"], 0)
        self.assertEqual(self.baseline["server_exe"]["sha256"], "987fbc47bab1dab37f74d7f700aa2e5b6af936a7181a62f5ba9f0090aebba805")
        self.assertEqual(self.baseline["server_config"]["sha256"], "2a6d24d89f61939fe0310342a83bfd55cefdbf1dfaa191ee3bffc6aa07e7f295")

    def test_stock_backup_and_only_scheduled_shutdown_delta(self):
        self.assertIn("stock-backup", self.script)
        self.assertIn("Get-FileHash", self.script)
        self.assertIn("<shutdown>1</shutdown>", self.script)
        self.assertIn("<deadline>$SessionMinutes</deadline>", self.script)
        self.assertIn("Copy-NewVerifiedFile", self.script)
        self.assertIn("Get-ChildItem -LiteralPath", self.script)

    def test_runbook_has_concrete_windows_paths_and_unmet_gates(self):
        for required in (r"D:\SteamLibrary\steamapps\common\DayZ Tools", r"D:\SteamLibrary\steamapps\common\DayZServer", r"\\wsl.localhost\Ubuntu-24.04\code\dayzsa_mods", "-WhatIf", "Start-Process", "Get-NetUDPEndpoint", "127.0.0.1", "static only", "not executed", "T003", "NET-004", "NET-005", "stock-backup", "graceful"):
            with self.subTest(required=required):
                self.assertIn(required, self.guide)
        self.assertNotIn("-ExecutionPolicy Bypass", self.guide)

if __name__ == "__main__":
    unittest.main(verbosity=2)
