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

if __name__=="__main__": unittest.main()
