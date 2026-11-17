"""Synthetic original text only: no game data or fixtures."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

from tools.package import pbo
from tools.validate.runtime import validate_settings
from unittest.mock import Mock


class PackageBehavior(unittest.TestCase):
    def test_stored_roundtrip_exact_prefix_and_reproducibility(self):
        files = {'scripts/4_World/HC.c': b'// synthetic\n', 'config.cpp': b'class Synthetic {};'}
        blob = pbo.pack(files)
        self.assertEqual(blob, pbo.pack(dict(reversed(list(files.items())))))
        prefix, entries = pbo.parse(blob)
        self.assertEqual(prefix, 'HollowCountry')
        self.assertEqual(entries, files)
        self.assertEqual(blob[-21:], b'\0' + hashlib.sha1(blob[:-21]).digest())
        self.assertIn(b'scripts\\4_World\\HC.c\0', blob)

    def test_independent_wire_layout(self):
        # Hand-authored structural fixture, independent of the writer.
        body = b'\0' + struct.pack('<5I', 0x56657273, 0, 0, 0, 0)
        body += b'prefix\0HollowCountry\0\0'
        body += b'config.cpp\0' + struct.pack('<5I', 0, 0, 0, 0, 3)
        body += bytes(21) + b'abc'
        self.assertEqual(pbo.parse(body + b'\0' + hashlib.sha1(body).digest()),
                         ('HollowCountry', {'config.cpp': b'abc'}))

    def test_corrupt_checksum_truncation_and_trailing_data_rejected(self):
        blob = pbo.pack({'config.cpp': b'synthetic'})
        for bad in [blob[:-1], blob + b'x', blob[:-22] + b'X' + blob[-21:], b'']:
            with self.subTest(bad=bad[:20]), self.assertRaises(ValueError):
                pbo.parse(bad)

    def test_unsafe_names_and_windows_collisions_rejected(self):
        for name in ['../a.c', '/a.c', 'C:/x.c', 'a//b.c', 'a/./b.c', 'a\\b.c',
                     'a\0.c', 'a/CON.c', 'a./b.c', 'a:stream.c', 'a/../b.c', 'a\nb.c']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                pbo.pack({name: b'x'})
        with self.assertRaises(ValueError):
            pbo.pack({'a.c': b'1', 'A.c': b'2'})

    def test_parser_rejects_unsafe_name_even_with_valid_checksum(self):
        blob = pbo.pack({'safe.c': b'x'})
        body = blob[:-21].replace(b'safe.c\0', b'../x.c\0')
        with self.assertRaises(ValueError):
            pbo.parse(body + b'\0' + hashlib.sha1(body).digest())

    def test_parser_rejects_compression_and_false_lengths(self):
        blob = pbo.pack({'config.cpp': b'x'})
        off = blob.index(b'config.cpp\0') + len(b'config.cpp\0')
        for field, value in [(0, 0x43707273), (1, 100), (2, 1), (4, 100)]:
            body = bytearray(blob[:-21])
            struct.pack_into('<I', body, off + 4 * field, value)
            with self.subTest(field=field), self.assertRaises(ValueError):
                pbo.parse(bytes(body) + b'\0' + hashlib.sha1(body).digest())

    def test_addon_allowlist_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'config.cpp').write_text('class Synthetic {};')
            scripts = root / 'scripts/4_World'
            scripts.mkdir(parents=True)
            (scripts / 'Synthetic.c').write_text('// synthetic')
            self.assertEqual(len(pbo.collect_addon(root)), 2)
            for bad in ['secret.biprivatekey', 'model.p3d', 'types.xml', 'profile.json', 'config.bin']:
                p = root / bad
                p.write_bytes(b'not allowed')
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    pbo.collect_addon(root)
                p.unlink()
            (scripts / 'link.c').symlink_to(root / 'config.cpp')
            with self.assertRaises(ValueError):
                pbo.collect_addon(root)

    def test_expansion_ai_addon_packs_under_its_own_prefix_only_on_request(self):
        from tools.setup import local_test_session
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / '$PBOPREFIX$').write_text('HollowCountryExpansionAI\n')
            (root / 'config.cpp').write_text('class CfgPatches\n{\n    class HollowCountryExpansionAI {};\n};\n')
            (root / 'scripts/4_World').mkdir(parents=True)
            (root / 'scripts/4_World/HCXAI.c').write_text('// synthetic')
            with self.assertRaisesRegex(ValueError, 'prefix'):
                pbo.collect_addon(root)  # the default contract stays the main HollowCountry prefix
            self.assertEqual(pbo.addon_prefix(root), 'HollowCountryExpansionAI')
            blob = pbo.pack(pbo.collect_addon(root, 'HollowCountryExpansionAI'), 'HollowCountryExpansionAI')
            with self.assertRaisesRegex(ValueError, 'prefix'):
                pbo.parse(blob)  # callers expecting the main addon still refuse it
            prefix, entries = pbo.parse(blob, prefixes=pbo.PREFIXES)
            self.assertEqual(prefix, 'HollowCountryExpansionAI')
            self.assertEqual(set(entries), {'config.cpp', 'scripts/4_World/HCXAI.c'})
            local_test_session.check_ai_pbo(blob)
            (root / '$PBOPREFIX$').write_text('SomeoneElse\n')
            with self.assertRaisesRegex(ValueError, 'prefix'):
                pbo.addon_prefix(root)
            with self.assertRaisesRegex(ValueError, 'prefix'):
                pbo.pack({'config.cpp': b'x'}, 'SomeoneElse')

    def test_cli_builds_and_verifies_the_repository_expansion_ai_addon(self):
        from tools.setup import local_test_session
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / 'xai.pbo'
            run = lambda *a: subprocess.run([sys.executable, '-B', '-m', 'tools.package.pbo', *a],
                                            capture_output=True, text=True, cwd=Path(__file__).parents[2])
            refused = run('pbo', '--addon', 'mods/HollowCountryExpansionAI', '--out', str(Path(t) / 'no.pbo'))
            self.assertNotEqual(refused.returncode, 0)  # the contract is chosen by the caller, not the marker
            built = run('pbo', '--prefix', 'HollowCountryExpansionAI', '--addon', 'mods/HollowCountryExpansionAI',
                        '--out', str(out))
            self.assertEqual(built.returncode, 0, built.stderr)
            self.assertNotEqual(run('verify', str(out)).returncode, 0)  # default verify is the main addon
            checked = run('verify', '--prefix', 'HollowCountryExpansionAI', str(out))
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)['prefix'], 'HollowCountryExpansionAI')
            local_test_session.check_ai_pbo(out.read_bytes())

    def test_cli_main_addon_with_a_foreign_marker_is_refused_by_default(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t) / 'addon'
            shutil.copytree(Path(__file__).parents[2] / 'mods/HollowCountry', root)
            (root / '$PBOPREFIX$').write_text('HollowCountryExpansionAI\n')
            built = subprocess.run([sys.executable, '-B', '-m', 'tools.package.pbo', 'pbo', '--addon', str(root),
                                    '--out', str(Path(t) / 'main.pbo')],
                                   capture_output=True, text=True, cwd=Path(__file__).parents[2])
            self.assertNotEqual(built.returncode, 0)
            self.assertIn('prefix', built.stderr)
            self.assertFalse((Path(t) / 'main.pbo').exists())

    def test_original_layout_text_is_packaged_without_allowing_game_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.cpp').write_text('class Synthetic {};')
            layouts = root / 'gui/layouts'
            layouts.mkdir(parents=True)
            layout = b'FrameWidgetClass Synthetic { size 1 1 }\n'
            (layouts / 'hc_synthetic.layout').write_bytes(layout)
            _, entries = pbo.parse(pbo.pack(pbo.collect_addon(root)))
            self.assertEqual(entries['gui/layouts/hc_synthetic.layout'], layout)
            for name, data in [('gui/image.edds', b'asset'),
                               ('gui/layouts/binary.layout', b'\x00binary'),
                               ('gui/other.layout', layout)]:
                path = root / name
                path.write_bytes(data)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    pbo.collect_addon(root)
                path.unlink()

    def test_custom_input_defaults_survive_pbo_and_handoff_without_admitting_other_xml(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            addon, mission = root / 'addon', root / 'mission'
            addon.mkdir()
            mission.mkdir()
            (addon / 'config.cpp').write_text('class Synthetic {};')
            inputs = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                      b'<modded_inputs><inputs><actions><input name="UASynthetic" '
                      b'loc="Synthetic" /></actions></inputs><preset><input '
                      b'name="UASynthetic"><btn name="kO" /></input></preset></modded_inputs>\n')
            (addon / 'inputs.xml').write_bytes(inputs)
            self.assertEqual(inputs, pbo.parse(pbo.pack(pbo.collect_addon(addon)))[1]['inputs.xml'])
            handoff = pbo.handoff(addon, mission)
            self.assertEqual(hashlib.sha256(inputs).hexdigest(),
                             pbo.verify_handoff(handoff)['sources']['inputs.xml'])
            with zipfile.ZipFile(io.BytesIO(handoff)) as archive:
                _, entries = pbo.parse(archive.read('@HollowCountry/addons/hollowcountry.pbo'))
                self.assertEqual(inputs, entries['inputs.xml'])
            for name in ('other.xml', 'input.xml', 'scripts/inputs.xml', 'INPUTS.xml'):
                self.assertFalse(pbo.original_addon_name(name), name)
                candidate = addon / name
                if candidate.exists():
                    # Case-insensitive filesystem (NTFS): the alias is the admitted file itself.
                    continue
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(inputs)
                with self.subTest(name=name), self.assertRaises(ValueError):
                    pbo.collect_addon(addon)
                candidate.unlink()
            self.assertEqual(inputs, (addon / 'inputs.xml').read_bytes())

    def test_custom_input_file_preserves_existing_text_and_link_guards(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.cpp').write_text('class Synthetic {};')
            target = root / 'inputs.xml'
            for data in (b'\x00binary', b'\xffinvalid-utf8'):
                target.write_bytes(data)
                with self.subTest(data=data), self.assertRaises(ValueError):
                    pbo.collect_addon(root)
            target.unlink()
            target.symlink_to(root / 'config.cpp')
            with self.assertRaises(ValueError):
                pbo.collect_addon(root)

    def test_handoff_allowlist_determinism_and_release_gate(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            addon = root / 'addon'
            addon.mkdir()
            (addon / 'config.cpp').write_text('class Synthetic {};')
            mission = root / 'mission'
            mission.mkdir()
            (mission / 'README.md').write_text('Synthetic original instructions')
            one = pbo.handoff(addon, mission)
            self.assertEqual(one, pbo.handoff(addon, mission))
            with zipfile.ZipFile(io.BytesIO(one)) as z:
                self.assertIn('@HollowCountry/addons/hollowcountry.pbo', z.namelist())
                self.assertIn('manifest.json', z.namelist())
                self.assertIn(b'unsigned-development', z.read('manifest.json'))
                self.assertFalse(any('privatekey' in n for n in z.namelist()))
                self.assertIn('tools/package/coverage.py', z.namelist())
                self.assertIn('tools/package/deploy.py', z.namelist())
                self.assertIn('docs/INSTALL_ROLLBACK.md', z.namelist())
                for portable in ('tools/package/interior_catalog.py', 'tools/package/atmosphere.py', 'LICENSE.md', 'docs/PROVENANCE_AND_LICENSES.md'):
                    with self.subTest(portable=portable):
                        self.assertIn(portable, z.namelist())
            (mission / 'mapgroupproto.xml').write_text('<prototype/>')
            with self.assertRaises(ValueError):
                pbo.handoff(addon, mission)
            with self.assertRaises(ValueError):
                pbo.handoff(addon, mission, release=True)

    def test_mod_metadata_outside_pbo(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'config.cpp').write_text('class Synthetic {};')
            (root / 'mod.cpp').write_text('name="Synthetic";')
            (root / 'mission').mkdir()
            entries = pbo.collect_addon(root)
            self.assertNotIn('mod.cpp', entries)
            blob = pbo.handoff(root, root / 'mission')
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                self.assertEqual(z.read('@HollowCountry/mod.cpp'), b'name="Synthetic";')

    def test_zip_verification_detects_tampering(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            (root / 'config.cpp').write_text('class Synthetic {};')
            mission = root / 'mission'
            mission.mkdir()
            blob = pbo.handoff(root, mission)
            report = pbo.verify_handoff(blob)
            self.assertEqual(report['status'], 'unsigned-development')
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(blob)) as src, zipfile.ZipFile(output, 'w') as dst:
                for name in src.namelist():
                    dst.writestr(name, b'tampered' if name.endswith('.pbo') else src.read(name))
            with self.assertRaises(ValueError):
                pbo.verify_handoff(output.getvalue())

    def test_windows_signing_arguments_and_failing_verifier(self):
        from tools.package import sign
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / 'synthetic.pbo'
            source.write_bytes(pbo.pack({'config.cpp': b'class Synthetic {};'}))
            private = root / 'test.biprivatekey'
            public = root / 'test.bikey'
            private.write_text('SYNTHETIC-NOT-A-KEY')
            public.write_text('SYNTHETIC-NOT-A-KEY')
            tools = root / 'tools/Bin/DsUtils'
            tools.mkdir(parents=True)
            for name in ['DSSignFile.exe', 'DSCheckSignatures.exe']:
                (tools / name).write_text('SYNTHETIC-NOT-EXECUTABLE')
            calls = []
            def fake_run(argv, **kwargs):
                calls.append(argv)
                self.assertFalse(kwargs.get('shell', False))
                if argv[0].endswith('DSSignFile.exe'):
                    Path(argv[2] + '.test.bisign').write_text('SYNTHETIC-NOT-A-SIGNATURE')
                    return Mock(returncode=0, stdout='', stderr='')
                return Mock(returncode=0, stdout='Signature synthetic.pbo.test.bisign is OK\n', stderr='')
            result = sign.sign_and_verify(source, root / 'tools', private, public, root / 'signed', runner=fake_run)
            # Keep lexical paths: resolve() expands native Windows 8.3 parents.
            # The signer intentionally checks links before invoking the tools.
            self.assertEqual(calls[0][1], str(private.absolute()))
            self.assertTrue(Path(calls[0][1]).samefile(private))
            self.assertEqual(len(calls[0]), 3)
            self.assertEqual(calls[1][1:], [str(root / 'signed/addons'), str(root / 'signed/keys')])
            self.assertEqual(result['runtime_acceptance'], 'pending')
            self.assertFalse((root / 'signed/test.biprivatekey').exists())
            def bad_run(argv, **kwargs):
                result = fake_run(argv, **kwargs)
                if argv[0].endswith('DSCheckSignatures.exe'):
                    result.stdout = 'Signature synthetic.pbo.test.bisign is wrong'
                return result
            with self.assertRaises(ValueError):
                sign.sign_and_verify(source, root / 'tools', private, public, root / 'rejected', runner=bad_run)

    def test_signing_accepts_the_expansion_ai_addon_prefix_and_reports_it(self):
        from tools.package import sign
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / 'hollowcountryexpansionai.pbo'
            source.write_bytes(pbo.pack({'config.cpp': b'class Synthetic {};'}, prefix='HollowCountryExpansionAI'))
            unknown = root / 'other.pbo'
            body = pbo.pack({'config.cpp': b'class Synthetic {};'}).replace(b'HollowCountry\0', b'OtherAddonXYZ\0', 1)
            unknown.write_bytes(body[:-21] + b'\0' + hashlib.sha1(body[:-21]).digest())
            private = root / 'test.biprivatekey'
            public = root / 'test.bikey'
            private.write_text('SYNTHETIC-NOT-A-KEY')
            public.write_text('SYNTHETIC-NOT-A-KEY')
            tools = root / 'tools/Bin/DsUtils'
            tools.mkdir(parents=True)
            for name in ['DSSignFile.exe', 'DSCheckSignatures.exe']:
                (tools / name).write_text('SYNTHETIC-NOT-EXECUTABLE')
            def fake_run(argv, **kwargs):
                if argv[0].endswith('DSSignFile.exe'):
                    Path(argv[2] + '.test.bisign').write_text('SYNTHETIC-NOT-A-SIGNATURE')
                    return Mock(returncode=0, stdout='', stderr='')
                return Mock(returncode=0, stdout='Signature x.pbo.test.bisign is OK\n', stderr='')
            result = sign.sign_and_verify(source, root / 'tools', private, public, root / 'signed', runner=fake_run)
            self.assertEqual(result['prefix'], 'HollowCountryExpansionAI')
            with self.assertRaises(ValueError):
                sign.sign_and_verify(unknown, root / 'tools', private, public, root / 'other', runner=fake_run)
            self.assertFalse((root / 'other').exists())

    def test_structural_verifier_rejects_forged_distribution_and_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config.cpp').write_text('class Synthetic {};')
            mission = root / 'mission'
            mission.mkdir()
            blob = pbo.handoff(root, mission)
            for field, value in [('distribution', 'public'), ('runtime_acceptance', 'accepted')]:
                with self.subTest(field=field):
                    output = io.BytesIO()
                    with zipfile.ZipFile(io.BytesIO(blob)) as source, zipfile.ZipFile(output, 'w') as target:
                        for name in source.namelist():
                            data = source.read(name)
                            if name == 'manifest.json':
                                manifest = json.loads(data)
                                manifest[field] = value
                                data = json.dumps(manifest).encode()
                            target.writestr(name, data)
                    with self.assertRaises(ValueError):
                        pbo.verify_handoff(output.getvalue())

    def test_native_smoke_controls(self):
        script = Path('tools/package/Invoke-NativeSmoke.ps1').read_text()
        for token in ['SupportsShouldProcess', '127.0.0.1', 'MaxSeconds', 'HasExited',
                      'Kill()', 'Server initialized', 'runtime-acceptance-pending',
                      'verifySignatures = 0', 'Get-FileHash', '-mod=']:
            self.assertIn(token, script)

    def test_native_smoke_reports_actual_sockets_without_isolation_claim(self):
        script = Path('tools/package/Invoke-NativeSmoke.ps1').read_text()
        self.assertNotIn('unsigned_loopback_only', script)
        self.assertIn('requested_gameplay_loopback', script)
        self.assertIn('Get-NetUDPEndpoint -OwningProcess $server.Id', script)
        self.assertIn('Get-NetTCPConnection -OwningProcess $server.Id', script)
        self.assertIn('$MaxSeconds = 180', script)
        native_tests = Path('tools/package/Test-NativePackage.ps1').read_text()
        self.assertIn('Parser]::ParseFile', native_tests)
        self.assertIn('-WhatIf', native_tests)
        self.assertIn('SYNTHETIC-NOT-EXECUTABLE', native_tests)
        self.assertIn('Steam', native_tests)

    def test_native_smoke_config_contains_required_stock_instance_fields(self):
        script = Path('tools/package/Invoke-NativeSmoke.ps1').read_text()
        config = re.search(r'\$configText = @"\r?\n(.*?)\r?\n"@', script, re.S).group(1)
        for field, value in [('instanceId', '1'), ('guaranteedUpdates', '1'), ('shardId', '"hcdev1"')]:
            self.assertEqual(re.findall(r'(?m)^' + field + r'\s*=\s*([^;]+);', config), [value])
        self.assertRegex(config, r'(?m)^BattlEye\s*=\s*0;')

    def test_native_smoke_uses_verified_isolated_battleye_dependency(self):
        script = Path('tools/package/Invoke-NativeSmoke.ps1').read_text()
        self.assertIn("$sourceBattleye = Join-Path $ServerRoot 'battleye\\BEServer_x64.dll'", script)
        self.assertIn("$battleye = Join-Path $runtimeFull 'battleye'", script)
        self.assertIn('"-BEpath=$battleye"', script)
        self.assertIn("Copy-NewVerifiedFile $sourceBattleye (Join-Path $battleye 'BEServer_x64.dll') $battleyeExpected", script)
        for field in ['battleye_source_sha256', 'battleye_staged_sha256', 'battleye_bytes']:
            self.assertIn(field, script)
        gate = script.index('if (-not $PSCmdlet.ShouldProcess')
        capture = script.index('sha256 = (Get-ReadOnlySha256 $sourceBattleye)')
        copy = script.index('Copy-NewVerifiedFile $sourceBattleye')
        launch = script.index('$server = Start-Process')
        self.assertLess(gate, capture, 'WhatIf must not require the synthetic fixture to contain BE DLLs')
        self.assertLess(capture, script.index('$null = New-Item'), 'dependency admission must precede staging')
        self.assertLess(capture, copy)
        self.assertLess(copy, launch)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell helper execution belongs to Windows CI')
    def test_native_smoke_verified_copy_rejects_drift_and_overwrite(self):
        """Execute actual smoke-helper AST functions against synthetic files only."""
        powershell = shutil.which('powershell.exe')
        self.assertIsNotNone(powershell, 'native Windows PowerShell is required on the Windows runner')
        helper = Path('tools/package/Invoke-NativeSmoke.ps1').resolve()
        harness = r'''
param([string]$Helper, [string]$Fixture)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Helper, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Smoke helper AST parse failed.' }
foreach ($name in @('Assert-NoReparseAncestors', 'Get-ReadOnlySha256', 'Assert-PinnedFile', 'Copy-NewVerifiedFile')) {
    $definition = $ast.Find({ param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name
    }, $true)
    if ($null -eq $definition) { throw "Missing real smoke helper: $name" }
    . ([scriptblock]::Create($definition.Extent.Text))
}
$source = Join-Path $Fixture 'synthetic-BEServer_x64.dll'
$destination = Join-Path $Fixture 'staged-BEServer_x64.dll'
[IO.File]::WriteAllText($source, 'SYNTHETIC-NOT-A-DLL')
$expected = [pscustomobject]@{ bytes = (Get-Item -LiteralPath $source).Length; sha256 = (Get-ReadOnlySha256 $source) }
Copy-NewVerifiedFile $source $destination $expected
if ((Get-ReadOnlySha256 $destination) -ne $expected.sha256) { throw 'Copy checksum differs.' }
Assert-PinnedFile $source $expected
[IO.File]::WriteAllText($destination, 'UNRELATED-DO-NOT-OVERWRITE')
$rejected = $false
try { Copy-NewVerifiedFile $source $destination $expected } catch { $rejected = $true }
if (-not $rejected -or [IO.File]::ReadAllText($destination) -ne 'UNRELATED-DO-NOT-OVERWRITE') {
    throw 'Existing destination was overwritten.'
}
[IO.File]::WriteAllText($source, 'SYNTHETIC-NOT-A-DLX')
$driftTarget = Join-Path $Fixture 'must-not-be-created.dll'
$rejected = $false
try { Copy-NewVerifiedFile $source $driftTarget $expected } catch { $rejected = $true }
if (-not $rejected -or (Test-Path -LiteralPath $driftTarget)) { throw 'Changed source was copied.' }
[IO.File]::WriteAllText($destination, 'SYNTHETIC-NOT-A-DLY')
$rejected = $false
try { Assert-PinnedFile $destination $expected } catch { $rejected = $true }
if (-not $rejected) { throw 'Changed staged dependency was accepted.' }
Write-Output 'PASS actual smoke helper copy/hash/drift/overwrite behavior on synthetic bytes; no DayZ launch.'
'''
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / 'test-smoke-copy.ps1'
            script.write_text(harness, encoding='utf-8')
            result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                     '-File', str(script), '-Helper', str(helper), '-Fixture', str(root)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('PASS actual smoke helper', result.stdout)

    def test_operator_settings_and_install_rollback_guide_are_packaged(self):
        mission = Path('mission/hollow-country')
        settings = __import__('json').loads((mission / 'operator/settings.json').read_text())
        # User decision: feature preferences default on; capability admission stays fail-closed.
        self.assertEqual(json.loads(Path('config/hollow-country-settings.json').read_text()), settings)
        self.assertEqual([], validate_settings(settings))
        self.assertTrue(all(v is True for k, v in settings.items() if k.startswith('Enable')))
        self.assertEqual(settings['SchemaVersion'], 1)
        with tempfile.TemporaryDirectory() as t:
            addon = Path(t)
            (addon / 'config.cpp').write_text('class Synthetic {};')
            blob = pbo.handoff(addon, mission)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                self.assertIn('mission/hollow-country/operator/settings.json', z.namelist())
                text = z.read('mission/hollow-country/INSTALL_AND_ROLLBACK.md').decode()
                for word in ['settings.json', 'rollback', 'pending', '-mod=', 'private']:
                    self.assertIn(word, text)

    def test_windows_python_preflight_is_explicit(self):
        for name in ['Build-Sign-Verify.ps1', 'Invoke-NativeSmoke.ps1']:
            script = Path('tools/package', name).read_text()
            self.assertIn('Get-Command -Name $Python', script)
            self.assertIn('WindowsApps', script)
            self.assertIn('sys.version_info', script)
            self.assertLess(script.index('Get-Command -Name $Python'), script.index('$null = New-Item'))

    def test_signing_command_contract(self):
        script = Path('tools/package/Build-Sign-Verify.ps1').read_text()
        self.assertIn('DSSignFile.exe', script)
        self.assertIn('DSCheckSignatures.exe', script)
        self.assertIn('sign.py', script)
        self.assertIn('PrivateKey', script)
        self.assertIn('PublicKey', script)
        self.assertIn('$LASTEXITCODE', script)
        self.assertIn('Unsigned', script)


if __name__ == '__main__':
    unittest.main()
