"""Synthetic byte bundles and receipts; no native or rendered acceptance."""
import copy
import hashlib
import importlib
import json
import re
import unittest

STOCK = b"""void main() { Hive ce = CreateHive(); if (ce) ce.InitOffline(); }
class CustomMission: MissionServer {}
Mission CreateCustomMission(string path) { return new CustomMission(); }
"""

def request():
    return dict(world_name="chernarusplus", engine_version="1.30.164289.70",
        stock_init_sha256=hashlib.sha256(STOCK).hexdigest(),
        victim_position=[100, 10, 100], source_position=[102, 10, 100])

def receipt(p, files):
    m = json.loads(files[p.MARKER])
    cases = []
    for i in range(2):
        f = 2 + i*6
        t = i*4.0
        cases.append(dict(index=i, name=p.CASES[i], spawn_frame=f, spawn_queue=f,
            damage_frame=f+1, damage_queue=f+1, command_frame=f+2,
            delete_frame=f+4, delete_queue=f+4, cleanup_frame=f+5, cleanup_queue=f+5,
            spawn_elapsed=t+.2, damage_elapsed=t+.4, command_elapsed=t+.6,
            delete_elapsed=t+2.6, cleanup_elapsed=t+2.8,
            damage_calls=1, eval_calls=1, before_type=0, after_type=i, command_type=i,
            hit_direction=90.0, command_direction=90.0, ammo="MeleeFist", zone="Torso",
            ammo_physics_flag=0, ammo_damage=10.0, cleanup_confirmed=1,
            samples=[dict(elapsed=t+.2, frame=f, health=100.0, death_processed=0,
                          position=[100,10,100], spine=[100,11,100]),
                     dict(elapsed=t+.6, frame=f+2, health=0.0, death_processed=0,
                          position=[100,10,100], spine=[100,10.5,100]),
                     dict(elapsed=t+2.6, frame=f+4, health=0.0, death_processed=1,
                          position=[100,10,100], spine=[100,10.2,100])]))
    return dict(schema=1, kind=p.KIND, run_id=m["run_id"],
        request_sha256=m["request_sha256"], world_name="chernarusplus",
        engine_version="1.30.164289.70", ce_initialization="omitted",
        server_context=1, complete=1, failed=0, reason="", callbacks_detached=1,
        frames=14, queues=14, elapsed_seconds=7.0, peak_owned_entities=2,
        owned_entities_remaining=0, render_observed=0, ragdoll_observed=0,
        gameplay_acceptance=0, cases=cases)

class DeathSelectionTests(unittest.TestCase):
    def setUp(self):
        self.p = importlib.import_module("tools.setup.death_selection_probe")

    def generate(self, req=None, blob=STOCK, interfaces=None, **kw):
        if interfaces is None:
            interfaces = {n:"\n".join(v).encode() for n,v in self.p.INTERFACES.items()}
        return self.p.generate_probe(blob, request() if req is None else req, interfaces,
            run_id=kw.get("run_id","a"*32))

    def validate(self, row=None, files=None, **kw):
        files = self.generate() if files is None else files
        data = json.dumps(receipt(self.p,files) if row is None else row).encode()
        return self.p.validate_receipt(data, files,
            **dict(dict(outer_timed_out=False,outer_elapsed_seconds=80),**kw))

    def test_fixed_ce_disabled_bundle_and_no_manual_callback(self):
        files=self.generate(); text=files["init.c"].decode()
        self.assertNotIn("ce.InitOffline();",text)
        self.assertIn("Hive ce = CreateHive();",text)
        self.assertIn("HCDS.Begin();",text)
        native=files[self.p.PROVIDER].decode()
        for token in ("CallLater(Tick, 100, true)","Insert(Frame)","Remove(Tick)",
                      "Remove(Frame)","State.frames < 2","State.queues < 2"):
            self.assertIn(token,native)
        self.assertEqual(1,native.count("void Frame("))
        self.assertEqual(1,native.count("void Tick("))
        self.assertNotIn("Tick();",native)
        self.assertNotIn("Frame();",native)

    def test_native_damage_hook_and_command_observation_preserve_vanilla(self):
        code=self.generate()[self.p.PROVIDER].decode()
        for token in ("ProcessDirectDamage(DamageType.CUSTOM, Source",
                      '"Torso", "MeleeFist"', "GetDamageZones(zones)",
                      "GetDamageZonePos", "super.EvaluateDeathAnimationEx(",
                      "super.CommandHandler(pDt, pCurrentCommandID, pCurrentCommandFinished)",
                      "IsBeingBackstabbed()", "COMMANDID_DEATH", "ANIM_DEATH_IMPULSE"):
            self.assertIn(token,code)
        for token in ("SetHealth(", "StartCommand_Death(", "dBodyApply", "SetPosition(",
                      "PhysicsSet", "SetAnimationInstance"):
            self.assertNotIn(token,code)
        self.assertEqual(1,code.count("ProcessDirectDamage("))

    def test_receipt_success_is_observation_only(self):
        result=self.validate()
        self.assertEqual("death-selection-observations-complete",result["status"])
        for field in ("gameplay_acceptance","visual_acceptance","ragdoll_acceptance"):
            self.assertIs(False,result[field])

    def test_real_callbacks_required_before_spawn(self):
        files=self.generate()
        for field in ("spawn_frame","spawn_queue","damage_frame","damage_queue",
                      "command_frame","cleanup_frame","cleanup_queue"):
            row=receipt(self.p,files); row["cases"][0][field]=0
            with self.subTest(field=field),self.assertRaises(ValueError): self.validate(row)

    def test_spawn_height_uses_observed_surface_before_creation(self):
        code=self.generate()[self.p.PROVIDER].decode()
        for name in ('vp', 'sp'):
            token=f'{name}[1] = GetGame().SurfaceY({name}[0], {name}[2]);'
            self.assertIn(token,code)
            self.assertLess(code.index(token),code.index('OwnedSource = GetGame().CreateObjectEx'))
        self.assertIn('SurfaceY(float x, float z)', self.p.INTERFACES['3_Game/Global/Game.c'])

    def test_generated_guards_do_not_start_continuation_with_operator(self):
        code=self.generate()[self.p.PROVIDER].decode()
        self.assertIsNone(re.search(r'^\s*(?:\|\||&&)',code,re.M))

    def test_override_parameter_names_match_native_declarations(self):
        code=self.generate()[self.p.PROVIDER].decode()
        self.assertIn('EvaluateDeathAnimationEx(EntityAI pSource, ZombieHitData data,',code)
        self.assertIn('out int pAnimType, out float pAnimHitDir)',code)
        self.assertIn('CommandHandler(float pDt, int pCurrentCommandID, bool pCurrentCommandFinished)',code)
        self.assertIn('super.EvaluateDeathAnimationEx(pSource, data, pAnimType, pAnimHitDir)',code)

    def test_selection_requires_real_eval_and_command_values(self):
        files=self.generate()
        for field,value in (("eval_calls",0),("damage_calls",0),("before_type",1),
            ("after_type",0),("command_type",0),("command_direction",-90),
            ("ammo","invented"),("zone","fake"),("ammo_physics_flag",1),("ammo_damage",0)):
            row=receipt(self.p,files); row["cases"][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): self.validate(row)

    def test_cleanup_precedes_next_victim_and_is_confirmed(self):
        files=self.generate()
        for field,value in (("cleanup_confirmed",0),("cleanup_frame",8),
                            ("cleanup_queue",8),("cleanup_elapsed",4.2)):
            row=receipt(self.p,files); row["cases"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): self.validate(row)

    def test_no_frame_zero_or_instant_health_only_completion(self):
        row=receipt(self.p,self.generate())
        row["cases"][0]["samples"][-1]["elapsed"]=.6
        with self.assertRaises(ValueError): self.validate(row)
        row=receipt(self.p,self.generate()); row["cases"][0]["samples"][0]["health"]=0
        with self.assertRaises(ValueError): self.validate(row)

    def test_timeout_partial_wrong_nonce_and_acceptance_claims_rejected(self):
        for changes in (dict(complete=0),dict(failed=1),dict(run_id="b"*32),
            dict(owned_entities_remaining=1),dict(ragdoll_observed=1),
            dict(render_observed=1),dict(gameplay_acceptance=1),dict(callbacks_detached=0),
            dict(frames=20001),dict(queues=513),dict(peak_owned_entities=3)):
            row=receipt(self.p,self.generate()); row.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError): self.validate(row)
        for kw in (dict(outer_timed_out=True),dict(outer_timed_out=0),
                   dict(outer_elapsed_seconds=181),dict(outer_elapsed_seconds=True),
                   dict(outer_elapsed_seconds=float("nan")),dict(outer_elapsed_seconds=6)):
            with self.subTest(kw=kw),self.assertRaises(ValueError): self.validate(**kw)

    def test_bytes_hashes_and_strict_duplicate_keys(self):
        files=self.generate(); row=receipt(self.p,files)
        encoded=json.dumps(row).encode()
        out=self.p.validate_receipt(encoded,files,outer_timed_out=False,outer_elapsed_seconds=80)
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),out["receipt_sha256"])
        for data in (encoded[:-1]+b',"complete":1}', encoded.replace(b'7.0',b'NaN'),
                     b'{"x":'+b'['*30+b'0'+b']'*30+b'}'):
            with self.assertRaises(ValueError):
                self.p.validate_receipt(data,files,outer_timed_out=False,outer_elapsed_seconds=80)

    def test_tampered_or_unrelated_bundle_is_rejected(self):
        for name in ("init.c",self.p.PROVIDER,self.p.CONFIG,self.p.PREFIX):
            files=self.generate(); files[name]+=b"tampered"
            with self.subTest(name=name),self.assertRaises(ValueError): self.validate(files=files)
        files=self.generate(); files["../foreign"]=b"x"
        with self.assertRaises(ValueError): self.validate(files=files)
        with self.assertRaises(ValueError): self.validate(expected_bundle_sha256="0"*64)

    def test_invalid_input_rejected_before_emission(self):
        for changes in (dict(victim_position=[True,0,0]),dict(source_position=[100,10,100]),
            dict(victim_position=[float("inf"),0,0]),dict(engine_version="1.29"),
            dict(stock_init_sha256="0"*64),dict(extra="unknown")):
            req=request();req.update(changes)
            with self.subTest(changes=changes),self.assertRaises(ValueError): self.generate(req)
        with self.assertRaises(ValueError): self.generate(run_id="../bad")
        with self.assertRaises(ValueError): self.generate(interfaces={})
        with self.assertRaises(ValueError): self.generate(blob=b"x"*65537)

    def test_source_shape_ambiguity_and_instrumentation_rejected(self):
        for blob in (STOCK+STOCK,STOCK.replace(b"ce.InitOffline();",b"// ce.InitOffline();\n"),
                     STOCK.replace(b"if (ce)",b"if (ce && true)"),
                     STOCK.replace(b"MissionServer {}",b"MissionServer {void OnMissionFinish(){}}")):
            req=request();req["stock_init_sha256"]=hashlib.sha256(blob).hexdigest()
            with self.subTest(blob=blob[:60]),self.assertRaises(ValueError): self.generate(req,blob)

    def test_native_boolean_flags_accept_only_exact_zero_or_one(self):
        row=receipt(self.p,self.generate())
        row["complete"]=True;row["failed"]=False
        self.assertEqual("death-selection-observations-complete",self.validate(row)["status"])
        for value in (1.0,"1",2,None):
            row["complete"]=value
            with self.subTest(value=value),self.assertRaises(ValueError): self.validate(row)

    def test_sample_bounds_and_finite_values(self):
        for field,value in (("health",float("nan")),("frame",True),
                            ("position",[0,0,float("inf")]),("spine",[0,0])):
            row=receipt(self.p,self.generate());row["cases"][0]["samples"][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError): self.validate(row)
        row=receipt(self.p,self.generate());row["cases"][0]["samples"]*=6
        with self.assertRaises(ValueError): self.validate(row)

POLICY_SOURCE = b"""class HCInfectedDeathPolicy
{
    static int SelectDeathType(int nativeType, bool finisher, int ammoHitAnimation, bool heavyOverride, string zone, float hitDirection)
    {
        return nativeType;
    }
}
"""

def policy_receipt(p, files):
    row = receipt(p, files)
    row["cases"][1]["name"] = "policy-selection"
    for index, case in enumerate(row["cases"]):
        case["hit_direction"] = case["command_direction"] = 10.0
        case["policy_type"] = index * 2 - 1
        case["heavy_override"] = index
    return row

class DeathSelectionExtensionTests(unittest.TestCase):
    """Synthetic bytes only: no DayZ behavior, crash cause or render is established here."""
    def setUp(self):
        self.p = importlib.import_module("tools.setup.death_selection_probe")

    def generate(self, **changes):
        req = request()
        policy = changes.pop("policy_source", None)
        req.update(changes)
        interfaces = {n: "\n".join(v).encode() for n, v in self.p.INTERFACES.items()}
        return self.p.generate_probe(STOCK, req, interfaces, run_id="a"*32, policy_source=policy)

    def native(self, files):
        return files[self.p.PROVIDER].decode()

    def validate(self, row, files):
        return self.p.validate_receipt(json.dumps(row).encode(), files,
            outer_timed_out=False, outer_elapsed_seconds=80)

    def test_absent_optional_fields_keep_the_legacy_probe_text(self):
        text = self.native(self.generate())
        self.assertIn('CreateObjectEx("ZmbF_JournalistNormal_Blue", vp, ECE_INITAI);', text)
        self.assertIn("if (HCDS.Row.index == 1) pAnimType = DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;", text)
        self.assertIn('Row.name = "impulse-selection";', text)
        for token in ("HCInfectedDeathPolicy", "policy_type", "heavy_override", "m_HeavyHitOverride"):
            self.assertNotIn(token, text)
        self.assertEqual(0, len(re.findall(r"@[A-Z]+@", text)))
        self.assertNotIn(self.p.POLICY, self.generate())

    def test_spawn_profiles_select_documented_creation_flags(self):
        expected = {"initai-only": "ECE_INITAI", "surface-initai": "ECE_PLACE_ON_SURFACE|ECE_INITAI",
                    "surface-only": "ECE_PLACE_ON_SURFACE"}
        self.assertEqual(set(expected), set(self.p.SPAWN_PROFILES))
        for name, flags in expected.items():
            files = self.generate(spawn_profile=name)
            text = self.native(files)
            with self.subTest(name=name):
                self.assertIn('CreateObjectEx("ZmbF_JournalistNormal_Blue", vp, %s);' % flags, text)
                self.assertEqual(1, text.count('ZmbF_JournalistNormal_Blue", vp'))
                self.assertEqual(name, json.loads(files[self.p.MARKER])["request"]["spawn_profile"])
                for token in ("SetHealth(", "StartCommand_Death(", "dBodyApply", "SetPosition(", "PhysicsSet"):
                    self.assertNotIn(token, text)
                self.assertNotRegex(text, r"(?m)^\s*(\|\||&&)")

    def test_spawn_profile_changes_the_pinned_request_and_rejects_unknown_values(self):
        pins = {json.loads(self.generate(spawn_profile=n)[self.p.MARKER])["request_sha256"]
                for n in self.p.SPAWN_PROFILES}
        self.assertEqual(len(self.p.SPAWN_PROFILES), len(pins))
        self.assertNotIn(json.loads(self.generate()[self.p.MARKER])["request_sha256"], pins)
        for bad in ("ECE_INITAI", "", None, 1, ["surface-only"], "SURFACE-ONLY"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.generate(spawn_profile=bad)

    def test_policy_selection_requires_and_pins_the_exact_policy_source(self):
        with self.assertRaises(ValueError): self.generate(selection="policy")
        with self.assertRaises(ValueError): self.generate(policy_source=POLICY_SOURCE)
        for bad in (b"", b"class Other {}", POLICY_SOURCE+b"x"*70000, "text"):
            with self.subTest(bad=bad[:20]), self.assertRaises(ValueError):
                self.generate(selection="policy", policy_source=bad)
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        self.assertEqual(POLICY_SOURCE, files[self.p.POLICY])
        manifest = json.loads(files[self.p.MARKER])
        self.assertIn(self.p.POLICY, manifest["files"])
        self.assertEqual(["vanilla", "policy-selection"], manifest["cases"])
        self.assertEqual("policy", manifest["request"]["selection"])

    def test_policy_selection_probe_calls_policy_without_unsupported_mutations(self):
        text = self.native(self.generate(selection="policy", policy_source=POLICY_SOURCE))
        self.assertIn("HCInfectedDeathPolicy.SelectDeathType(", text)
        self.assertNotIn("if (HCDS.Row.index == 1) pAnimType = DayZInfectedDeathAnims.ANIM_DEATH_IMPULSE;", text)
        self.assertIn('Row.name = "policy-selection";', text)
        self.assertLess(text.index("Victim.m_HeavyHitOverride = true;"), text.index("Victim.ProcessDirectDamage("))
        self.assertIn("HCDS.Row.policy_type", text)
        for token in ("SetHealth(", "StartCommand_Death(", "dBodyApply", "SetPosition(", "PhysicsSet",
                      "SetAnimationInstance", "SetOrientation", "SetDirection"):
            self.assertNotIn(token, text)
        self.assertNotRegex(text, r"(?m)^\s*(\|\||&&)")
        self.assertEqual(0, len(re.findall(r"@[A-Z]+@", text)))

    def test_policy_receipt_accepts_only_frontal_policy_driven_impulse(self):
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        self.assertEqual("death-selection-observations-complete",
                         self.validate(policy_receipt(self.p, files), files)["status"])
        for case_index, field, value in ((1, "policy_type", 0), (1, "policy_type", 2), (1, "after_type", 0),
                (1, "command_type", 0), (1, "heavy_override", 0), (1, "hit_direction", 61.0),
                (1, "hit_direction", -120.0), (0, "policy_type", 1), (0, "heavy_override", 1)):
            row = policy_receipt(self.p, files)
            row["cases"][case_index][field] = value
            if field == "hit_direction":
                row["cases"][case_index]["command_direction"] = value
            with self.subTest(case=case_index, field=field, value=value), self.assertRaises(ValueError):
                self.validate(row, files)

    def test_policy_and_legacy_receipt_shapes_do_not_cross_validate(self):
        legacy = self.generate()
        policy = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        with self.assertRaises(ValueError): self.validate(policy_receipt(self.p, legacy), legacy)
        with self.assertRaises(ValueError): self.validate(receipt(self.p, policy), policy)

    def test_tampering_with_the_pinned_policy_file_is_rejected(self):
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        files[self.p.POLICY] += b"//tamper"
        with self.assertRaises(ValueError): self.validate(policy_receipt(self.p, files), files)
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        del files[self.p.POLICY]
        with self.assertRaises(ValueError): self.validate(policy_receipt(self.p, files), files)

    def test_pack_addon_is_deterministic_and_matches_the_observed_pbo_layout(self):
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        blob = self.p.pack_addon(files)
        self.assertEqual(blob, self.p.pack_addon(files))
        self.assertTrue(blob.startswith(b"\0sreV"))
        self.assertIn(b"prefix\0HCDeathSelectionProbe\0", blob)
        for name in (b"config.cpp\0", b"scripts\\4_World\\HCDeathSelection.c\0",
                     b"scripts\\4_World\\HCInfectedDeathPolicy.c\0"):
            self.assertIn(name, blob)
        self.assertNotIn(b"PBOPREFIX", blob)
        self.assertNotIn(b"init.c", blob)
        self.assertNotIn(b"HCInfectedDeathPolicy.c\0", self.p.pack_addon(self.generate()))

    def test_stage_writes_fresh_directory_only_and_never_overwrites(self):
        import tempfile
        from pathlib import Path
        files = self.generate(spawn_profile="surface-initai")
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "stage"
            written = self.p.stage(dest, files)
            self.assertEqual(sorted(list(files) + [self.p.STAGED_PBO]), sorted(written))
            for name, data in files.items():
                self.assertEqual(data, (dest / name).read_bytes())
            self.assertEqual(self.p.pack_addon(files), (dest / self.p.STAGED_PBO).read_bytes())
            with self.assertRaises(ValueError): self.p.stage(dest, files)
            for bad in (Path(root) / "x" / ".." / "y", Path("relative-stage")):
                with self.subTest(bad=str(bad)), self.assertRaises(ValueError):
                    self.p.stage(bad, files)
            files["../escape"] = b"x"
            with self.assertRaises(ValueError): self.p.stage(Path(root) / "other", files)
            self.assertFalse((Path(root) / "other").exists())

    def test_module_never_launches_processes(self):
        with open(self.p.__file__) as stream:
            text = stream.read()
        for token in ("subprocess", "os.system", "Popen", "os.exec"):
            self.assertNotIn(token, text, token)

    def cli_fixture(self, root):
        from pathlib import Path
        (root / "init.c").write_bytes(STOCK)
        interfaces = root / "native"
        for name, tokens in self.p.INTERFACES.items():
            (interfaces / name).parent.mkdir(parents=True, exist_ok=True)
            (interfaces / name).write_text("\n".join(tokens))
        return ["--stock-init", str(root / "init.c"), "--interfaces", str(interfaces),
                "--destination", str(root / "stage"), "--victim", "100", "100", "--source", "102", "100",
                "--run-id", "c"*32]

    def test_cli_reads_the_production_policy_from_the_checkout_with_the_documented_relative_path(self):
        import contextlib, io, os, tempfile
        from pathlib import Path
        checkout = Path(self.p.__file__).resolve().parents[2]
        production = checkout / "mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c"
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            args = self.cli_fixture(root) + ["--selection", "policy", "--policy-source",
                "mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c"]
            cwd = os.getcwd()
            os.chdir(checkout)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(0, self.p.main(args))
            finally:
                os.chdir(cwd)
            self.assertEqual(production.read_bytes(), (root / "stage" / self.p.POLICY).read_bytes())

    def test_cli_policy_source_still_refuses_symlinks_traversal_and_oversize(self):
        import contextlib, io, os, tempfile
        from pathlib import Path
        checkout = Path(self.p.__file__).resolve().parents[2]
        production = checkout / "mods/HollowCountry/scripts/4_World/Infected/HCInfectedDeathPolicy.c"
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            base = self.cli_fixture(root)
            link = root / "link.c"
            link.symlink_to(production)
            big = root / "big.c"
            big.write_bytes(b"x" * (self.p.MAX_POLICY_BYTES + 1))
            for bad in (str(link), str(big), str(production.parent / ".." / "Infected" / production.name)):
                with self.assertRaises(ValueError, msg=bad):
                    self.p.main(base + ["--selection", "policy", "--policy-source", bad])
            self.assertFalse((root / "stage").exists())

    def test_policy_reader_refuses_a_parent_swapped_to_a_symlink(self):
        """SYNTHETIC parent swap preserves the leaf inode to defeat leaf-only identity checks."""
        import os, tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = root / 'checkout'
            parent.mkdir()
            policy = parent / 'policy.c'
            policy.write_bytes(b'// SYNTHETIC policy source')
            moved = root / 'outside'
            native_open = os.open
            swapped = False
            def swap_then_open(path, flags, mode=0o777, *, dir_fd=None):
                nonlocal swapped
                if not swapped and Path(path).name == policy.name:
                    parent.rename(moved)
                    parent.symlink_to(moved, target_is_directory=True)
                    swapped = True
                return native_open(path, flags, mode, dir_fd=dir_fd)
            # Preserve the mocked function's real dir_fd capability for the helper's platform guard.
            supported = os.supports_dir_fd | {swap_then_open}
            with mock.patch.object(os, 'open', swap_then_open), mock.patch.object(os, 'supports_dir_fd', supported):
                with self.assertRaisesRegex(ValueError, 'symlink|changed'):
                    self.p._read_policy_file(policy)
            self.assertTrue(swapped)

    def test_cli_policy_source_and_selection_require_each_other(self):
        import contextlib, io, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            policy = root / "policy.c"
            policy.write_bytes(POLICY_SOURCE)
            base = self.cli_fixture(root)
            for extra in (["--policy-source", str(policy)], ["--selection", "policy"]):
                with self.assertRaises(SystemExit) as raised:
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.p.main(base + extra)
                self.assertNotEqual(0, raised.exception.code, extra)
                self.assertFalse((root / "stage").exists(), extra)

    def test_receipt_must_contain_the_claimed_post_command_observation_window(self):
        files = self.generate(selection="policy", policy_source=POLICY_SOURCE)
        def mutate(change):
            row = policy_receipt(self.p, files)
            change(row["cases"][1])
            return row
        def last_on_command_frame(case):
            case["samples"][-1]["frame"] = case["command_frame"]
        def last_before_command_time(case):
            case["command_elapsed"] = case["samples"][-1]["elapsed"] + 0.05
            case["delete_elapsed"] = case["command_elapsed"] + 0.05
            case["cleanup_elapsed"] = case["delete_elapsed"] + 0.1
        def delete_before_window(case):
            case["delete_elapsed"] = case["damage_elapsed"] + 1.0
            case["cleanup_elapsed"] = case["delete_elapsed"] + 0.1
            for sample in case["samples"]:
                sample["elapsed"] = min(sample["elapsed"], case["delete_elapsed"])
        for change in (last_on_command_frame, last_before_command_time, delete_before_window):
            with self.assertRaises(ValueError, msg=change.__name__):
                self.validate(mutate(change), files)
        self.assertEqual("death-selection-observations-complete",
                         self.validate(policy_receipt(self.p, files), files)["status"])

    def test_cli_stages_from_installed_interfaces_without_executing_anything(self):
        import contextlib, io, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "init.c").write_bytes(STOCK)
            interfaces = root / "native"
            for name, tokens in self.p.INTERFACES.items():
                (interfaces / name).parent.mkdir(parents=True, exist_ok=True)
                (interfaces / name).write_text("\n".join(tokens))
            policy = root / "policy.c"
            policy.write_bytes(POLICY_SOURCE)
            dest = root / "stage"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = self.p.main(["--stock-init", str(root / "init.c"), "--interfaces", str(interfaces),
                    "--destination", str(dest), "--victim", "100", "100", "--source", "102", "100",
                    "--spawn-profile", "surface-initai", "--selection", "policy",
                    "--policy-source", str(policy), "--run-id", "b"*32])
            self.assertEqual(0, code)
            manifest = json.loads((dest / self.p.MARKER).read_text())
            self.assertEqual("surface-initai", manifest["request"]["spawn_profile"])
            self.assertEqual("b"*32, manifest["run_id"])
            self.assertEqual(POLICY_SOURCE, (dest / self.p.POLICY).read_bytes())
            self.assertTrue((dest / self.p.STAGED_PBO).is_file())
            self.assertIn("staged", out.getvalue())
            self.assertNotIn(str(Path.home()), out.getvalue())
            with self.assertRaises(SystemExit):
                with contextlib.redirect_stderr(io.StringIO()):
                    self.p.main(["--stock-init", str(root / "init.c")])

if __name__=="__main__": unittest.main()
