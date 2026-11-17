"""Synthetic Git repositories only; no credential or game-runtime evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from unittest import mock

from tools.validate import hygiene


class HygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hc-synthetic-hygiene-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        for name in (
            "AGENTS.md", "README.md", "docs/SPECIFICATION.md",
            "docs/specs/001-survival-overhaul/spec.md", "docs/SOURCES.md",
            "docs/DECISIONS_AND_RISKS.md", "docs/MODULE_STATUS.md",
            "docs/PROVENANCE_AND_LICENSES.md",
        ):
            self.put(name, "# Explicitly synthetic governance fixture\n")
        self.put("LICENSE.md", (
            "Copyright (c) 2026 David Addison\nAll rights reserved.\n"
            "No open-source or public reuse license is granted.\n"
            "Third-party materials remain subject to their owners' terms.\n"
        ))

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(text, str):
            text = text.encode("utf-8")
        path.write_bytes(text)
        return path

    def check(self):
        return hygiene.check_repository(self.root)

    def codes(self, report):
        return {e["code"] for e in report["errors"]}

    def test_private_authored_source_has_hash_inventory_and_honest_license(self):
        self.put("mods/Example/scripts/source.c", "// Synthetic authored text\n")
        report = self.check()
        self.assertTrue(report["valid"], report)
        item = next(x for x in report["inventory"] if x["path"].endswith("source.c"))
        self.assertEqual(64, len(item["sha256"]))
        self.assertEqual(27, item["bytes"])
        self.assertEqual("all-rights-reserved", report["license"]["project"])
        self.assertFalse(report["license"]["publication_authorized"])
        self.assertEqual("pending-human-review", report["license"]["third_party_rights"])
        self.assertEqual(report, self.check())

    def test_public_visibility_does_not_change_rights_or_make_scan_a_publication_approval(self):
        notice = (self.root / "LICENSE.md").read_text()
        self.put("LICENSE.md", "# Publicly viewable source\n" + notice)
        report = self.check()
        self.assertTrue(report["valid"], report)
        self.assertEqual("all-rights-reserved", report["license"]["project"])
        self.assertFalse(report["license"]["publication_authorized"])

    def test_given_ignored_local_key_when_forced_into_git_then_scan_refuses(self):
        self.put(".gitignore", "*.biprivatekey\n")
        self.put("local.biprivatekey", b"SYNTHETIC-NOT-A-KEY")
        self.assertTrue(self.check()["valid"])
        self.git("add", "-f", "local.biprivatekey")
        self.assertIn("restricted_path", self.codes(self.check()))

    def test_repository_ignore_policy_excludes_local_private_keys_and_artifacts(self):
        self.put(".gitignore", (hygiene.ROOT / ".gitignore").read_bytes())
        for name in ("synthetic.biprivatekey", "synthetic.bikey", "synthetic.pbo", ".env"):
            self.put(name, b"SYNTHETIC-NOT-KEY-OR-ASSET")
        report = self.check()
        self.assertTrue(report["valid"], report["errors"])
        self.git("add", "-f", "synthetic.biprivatekey")
        self.assertIn("restricted_path", self.codes(self.check()))

    def test_untracked_private_material_is_not_hidden_by_tracked_only_scan(self):
        for name in ("keys/key.biprivatekey", ".env", ".env.production",
                     "id_ed25519", "profiles/server.json", "storage_1/world.txt",
                     "workshop_mods/source.c", "third_party/source.py"):
            with self.subTest(name=name):
                path = self.put(name, "SYNTHETIC")
                self.assertIn("restricted_path", self.codes(self.check()))
                path.unlink()

    def test_env_example_with_paths_is_allowed(self):
        self.put(".env.example", "DAYZ_CLIENT_ROOT=C:\\Steam\\DayZ\n")
        self.assertTrue(self.check()["valid"])

    def test_local_absolute_home_paths_are_refused_without_echo(self):
        samples = ["// /home/" + "someone/.cache/x\n", "C:\\Users\\" + "someone\\x\n",
                   "/Users/" + "someone/x\n", "/mnt/c/Users/" + "someone/x\n",
                   "ok\nZ:\\home\\" + "someone\\x\n"]
        for sample in samples:
            with self.subTest(kind=samples.index(sample)):
                self.put("mods/Example/scripts/source.c", sample)
                report = self.check()
                self.assertIn("local_absolute_path", self.codes(report))
                self.assertNotIn("someone", json.dumps(report))
        self.put("mods/Example/scripts/source.c", "lines = 2\nZ:\\home\\" + "someone\\x\n")
        found = [e for e in self.check()["errors"] if e["code"] == "local_absolute_path"]
        self.assertEqual([{"code": "local_absolute_path", "path": "mods/Example/scripts/source.c", "line": 2}], found)

    def test_portable_home_placeholders_are_allowed(self):
        self.put("docs/SETUP.md", "~/.cache/x $HOME/x Path.home() /home/<user>/x C:\\Users\\<user>\\x /home/runner/work\n")
        self.assertNotIn("local_absolute_path", self.codes(self.check()))

    def test_rejects_precise_private_key_and_github_token_formats_without_echo(self):
        samples = ["-----BEGIN " + "OPENSSH PRIVATE KEY-----\nSYNTHETIC",
                   "gh" + "p_" + "A" * 36,
                   "github_" + "pat_" + "A" * 22 + "_" + "B" * 59]
        for sample in samples:
            with self.subTest(kind=samples.index(sample)):
                self.put("notes.txt", sample)
                report = self.check()
                self.assertIn("credential_content", self.codes(report))
                self.assertNotIn(sample, json.dumps(report))
                self.assertFalse(any(x["path"] == "notes.txt" for x in report["inventory"]))

    def test_secret_formats_are_checked_in_utf16_text_too(self):
        sample = "-----BEGIN " + "RSA PRIVATE KEY-----\nSYNTHETIC"
        self.put("notes.txt", sample.encode("utf-16"))
        self.assertIn("credential_content", self.codes(self.check()))

    def test_repeated_credential_markers_have_bounded_memory_and_one_finding(self):
        marker = "gh" + "p_" + "A" * 36 + "\n"
        sample = marker * (1024 * 1024 // len(marker))
        self.put("repeated.txt", sample)
        tracemalloc.start()
        try:
            report = self.check()
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(1, len(report["errors"]))
        self.assertLess(peak, 4 * len(sample), "scanner retained all credential matches")

    def test_exact_banso_spec_alias_is_preserved_but_redirect_is_refused(self):
        target = "docs/specs/001-survival-overhaul/spec.md"
        alias = self.root / "spec.md"
        try:
            alias.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create symlinks")
        report = self.check()
        self.assertTrue(report["valid"], report["errors"])
        entry = next(x for x in report["inventory"] if x["path"] == "spec.md")
        self.assertEqual("repository-alias", entry["kind"])
        alias.unlink()
        alias.symlink_to("README.md")
        self.assertIn("unsafe_file", self.codes(self.check()))

    def test_windows_git_textual_spec_alias_is_supported(self):
        self.put("spec.md", "docs/specs/001-survival-overhaul/spec.md")
        self.assertTrue(self.check()["valid"])

    def test_credential_paths_are_redacted_as_well_as_content(self):
        token = "gh" + "p_" + "Z" * 36
        self.put(token + ".txt", "synthetic")
        report = self.check()
        self.assertIn("credential_path", self.codes(report))
        self.assertNotIn(token, json.dumps(report))

    def test_ordinary_hashes_and_documented_key_names_are_not_credentials(self):
        self.put("notes.txt", "private-key path; token placeholder; sha256 " + "a" * 64)
        self.assertTrue(self.check()["valid"])

    def test_game_binary_and_disguised_executable_are_rejected(self):
        for name, content in (("model.p3d", b"SYNTHETIC"),
                              ("package.zip", b"SYNTHETIC"),
                              ("pretend.txt", b"MZ\x00SYNTHETIC"),
                              ("pretend.txt", b"PK\x03\x04SYNTHETIC"),
                              ("pretend.txt", b"\x7fELFSYNTHETIC")):
            with self.subTest(name=name, magic=content[:2]):
                path = self.put(name, content)
                self.assertFalse(self.check()["valid"])
                path.unlink()

    def test_binary_content_cannot_hide_under_source_extension(self):
        self.put("source.py", b"synthetic\x00opaque")
        self.assertIn("binary_content", self.codes(self.check()))

    def test_full_vanilla_economy_filename_requires_explicit_synthetic_scope(self):
        self.put("mission/mapgrouppos.xml", "<map/>")
        self.assertIn("vanilla_dump_path", self.codes(self.check()))
        (self.root / "mission/mapgrouppos.xml").unlink()
        self.put("tests/fixtures/ce/synthetic_valid/mapgrouppos.xml", "<map/>")
        self.assertTrue(self.check()["valid"])

    def test_markdown_checks_inline_images_reference_and_encoded_local_paths(self):
        self.put("docs/good name.md", "# Synthetic target\n")
        self.put("README.md", (
            "[inline](docs/good%20name.md#synthetic-target)\n"
            "[reference][target]\n[target]: <docs/good name.md>\n"
            "[external](https://example.invalid/not-contacted)\n"
            "[mail](mailto:example@example.invalid)\n"
        ))
        self.assertTrue(self.check()["valid"])
        self.put("README.md", "![missing](docs/missing.png)\n[reference][lost]\n")
        self.assertEqual({"documentation_target", "documentation_reference"}, self.codes(self.check()))

    def test_documentation_examples_are_not_links_and_missing_target_is(self):
        self.put("README.md", (
            "```markdown\n[synthetic](absent.md)\n```\n"
            "`[synthetic](absent.md)`\n[actual](missing.md)\n"
        ))
        errors = self.check()["errors"]
        self.assertEqual(1, len(errors), errors)
        self.assertEqual(5, errors[0]["line"])

    def test_documentation_target_must_be_in_repository_candidate_inventory(self):
        self.put(".gitignore", "local/\n")
        self.put("local/only-here.md", "# Synthetic ignored target")
        self.put("README.md", "[machine-local](local/only-here.md)")
        self.assertIn("documentation_target", self.codes(self.check()))

    def test_documentation_escape_is_refused_without_reading_outside(self):
        self.put("README.md", "[escape](../external.md)\n[local](file:///etc/passwd)\n")
        self.assertEqual({"documentation_path"}, self.codes(self.check()))

    def test_required_governance_and_license_are_not_silently_optional(self):
        (self.root / "docs/SOURCES.md").unlink()
        (self.root / "LICENSE.md").unlink()
        report = self.check()
        self.assertIn("required_document", self.codes(report))
        self.assertEqual("missing", report["license"]["project"])
        self.assertFalse(report["valid"])

    def test_portable_checkout_does_not_require_local_planning_records(self):
        for relative in ('AGENTS.md', 'docs/SPECIFICATION.md',
                         'docs/specs/001-survival-overhaul/spec.md',
                         'docs/DECISIONS_AND_RISKS.md'):
            (self.root / relative).unlink()
        report = self.check()
        self.assertTrue(report['valid'], report['errors'])

    def test_license_lint_refuses_unapproved_switch_to_open_reuse(self):
        self.put("LICENSE.md", "Synthetic MIT license: Permission is hereby granted.")
        self.assertIn("license_policy", self.codes(self.check()))

    def test_symlinks_and_hardlinks_never_supply_source_or_link_targets(self):
        outside = self.root.parent / (self.root.name + "-outside.txt")
        outside.write_text("SYNTHETIC-EXTERNAL", encoding="utf-8")
        self.addCleanup(lambda: outside.unlink(missing_ok=True))
        try:
            (self.root / "link.md").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create symlinks")
        self.put("README.md", "[external](link.md)")
        self.assertIn("unsafe_file", self.codes(self.check()))
        (self.root / "link.md").unlink()
        os.link(outside, self.root / "hard.txt")
        self.assertIn("unsafe_file", self.codes(self.check()))

    def test_symlink_ancestor_is_rejected_without_open(self):
        self.put("actual/source.txt", "synthetic")
        try:
            (self.root / "link").symlink_to(self.root / "actual", target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("host cannot create symlinks")
        # Git normally lists the link itself; the reader must also reject an
        # explicit candidate traversing that link before opening the file.
        with mock.patch.object(hygiene, "_candidates", return_value=["link/source.txt"]):
            self.assertIn("unsafe_file", self.codes(self.check()))

    def test_oversized_input_is_refused_before_read(self):
        self.put("large.txt", b"x" * 257)
        with mock.patch.object(hygiene, "MAX_FILE_BYTES", 256):
            self.assertIn("size_limit", self.codes(self.check()))

    def test_total_size_and_entry_limits_fail_closed(self):
        with mock.patch.object(hygiene, "MAX_TOTAL_BYTES", 10):
            self.assertIn("size_limit", self.codes(self.check()))
        with mock.patch.object(hygiene, "MAX_FILES", 1):
            self.assertIn("entry_limit", self.codes(self.check()))

    def test_git_discovery_output_has_its_own_predecode_size_bound(self):
        with mock.patch.object(hygiene, "MAX_DISCOVERY_BYTES", 128):
            self.assertIn("repository_discovery", self.codes(self.check()))

    def test_oversized_discovery_closes_pipe_and_reaps_before_directory_cleanup(self):
        child = mock.MagicMock()
        child.__enter__.return_value = child
        child.stdout.read.return_value = b'x' * 129
        child.wait.return_value = 0
        with mock.patch.object(hygiene, 'MAX_DISCOVERY_BYTES', 128), \
                mock.patch.object(hygiene.subprocess, 'Popen', return_value=child), \
                mock.patch.object(hygiene.threading, 'Timer') as timer:
            with self.assertRaises(ValueError):
                hygiene._candidates(self.root)
        child.stdout.close.assert_called_once()
        child.kill.assert_not_called()
        child.wait.assert_called()
        timer.return_value.join.assert_called_once()

    def test_metadata_size_preflight_never_opens_candidate_content(self):
        self.put("large.txt", b"x" * 257)
        with mock.patch.object(hygiene, "MAX_FILE_BYTES", 256), \
                mock.patch.object(hygiene, "_read", side_effect=AssertionError("must not open")):
            self.assertIn("size_limit", self.codes(self.check()))

    def test_discovery_cannot_accept_zero_exit_after_watchdog_expired(self):
        child = mock.MagicMock()
        child.__enter__.return_value = child
        child.stdout.read.return_value = str(self.root.resolve()).encode()
        child.wait.return_value = 0
        child.poll.return_value = 0
        def timer_factory(seconds, callback):
            timer = mock.Mock()
            timer.start.side_effect = callback
            return timer
        with mock.patch.object(hygiene.subprocess, 'Popen', return_value=child), \
                mock.patch.object(hygiene.threading, 'Timer', side_effect=timer_factory):
            with self.assertRaises(ValueError):
                hygiene._candidates(self.root)

    def test_replaced_source_after_preflight_is_refused(self):
        self.put("changing.txt", "synthetic first")
        original_read = hygiene._read

        def changed_read(root, relative, expected):
            if relative == "changing.txt":
                self.put(relative, "synthetic second")
            return original_read(root, relative, expected)

        with mock.patch.object(hygiene, "_read", side_effect=changed_read):
            self.assertIn("unsafe_file", self.codes(self.check()))

    def test_repository_discovery_does_not_silently_scan_a_parent_repo(self):
        nested = self.root / "nested"
        nested.mkdir()
        report = hygiene.check_repository(nested)
        self.assertIn("repository_discovery", self.codes(report))

    def test_git_failure_does_not_leak_exception_or_stderr(self):
        with mock.patch.object(hygiene, "_candidates", side_effect=OSError("SYNTHETIC-PRIVATE-DETAIL")):
            report = self.check()
        self.assertIn("repository_discovery", self.codes(report))
        self.assertNotIn("SYNTHETIC-PRIVATE-DETAIL", json.dumps(report))

    def test_cli_returns_machine_readable_failure_without_secret_on_either_stream(self):
        token = "gh" + "p_" + "Q" * 36
        self.put("notes.txt", token)
        result = subprocess.run([sys.executable, "-B", "-m", "tools.validate.hygiene",
                                 "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertFalse(json.loads(result.stdout)["valid"])
        self.assertNotIn(token, result.stdout + result.stderr)
        self.assertEqual("", result.stderr)


if __name__ == "__main__":
    unittest.main()


class EnvExampleTests(unittest.TestCase):
    def test_repository_env_example_host_is_loopback_or_documentation_range(self):
        import ipaddress
        root = Path(__file__).resolve().parents[2]
        values = dict(line.split("=", 1) for line in (root / ".env.example").read_text().splitlines()
                      if line and not line.startswith("#") and "=" in line)
        host = ipaddress.ip_address(values["DAYZ_SERVER_HOST"])
        documentation = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")]
        self.assertTrue(host.is_loopback or any(host in n for n in documentation), str(host))
