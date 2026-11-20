"""Synthetic stock/native metadata and receipts. No world/fit/eligibility proof."""
import copy
import importlib
import json
import unittest
from tools.setup import interior_measurement_probe as probe
from tests.slow import test_interior_measurement_probe as fixture

STOCK = fixture.STOCK
POSITIONS = b'<map><group name="Land_House_1W01" pos="100 10 200" rpy="0 0 90" a="0"/></map>'
PROTO = fixture.PROTOTYPES

def stock(positions=POSITIONS, proto=PROTO):
    return dict(zip(probe.STOCK_NAMES, (STOCK, positions, proto)))

def row(name="Land_House_1W01", model="\\DZ\\House_1W01.p3d", root="CfgVehicles"):
    return dict(ConfigRoot=root, ItemClass=name, ParentClass="House",
        ConfigAncestors=["House","Static","All"],
        Fields=[dict(ConfigPath="model", ReadAs="text", ConfigTypeName="CT_STRING",
            ValueCaptured=1, ValueText=model)])

def admission(rows, complete=True):
    roots=[]
    for name in ("CfgWeapons","CfgVehicles","CfgMagazines","CfgAmmo"):
        n=sum(r["ConfigRoot"]==name for r in rows)
        roots.append(dict(ConfigRoot=name,AdvertisedChildren=n,VisitedChildren=n,
            RowsWritten=n,EnumerationComplete=1))
    return dict(status="complete" if complete else "partial",EnumerationComplete=complete,
        FullCoverage=False,manifest_pin_checked=True,ActualWorld="chernarusplus",
        ActualBuild="1.30.164289.70",RowsWritten=len(rows),
        AdvertisedChildren=len(rows),VisitedChildren=len(rows),NonClassChildren=0,
        Roots=roots,files=[dict(file="manifest.json",bytes=30,sha256="b"*64)])

class InteriorSurveyTests(unittest.TestCase):
    def setUp(self):
        self.s=importlib.import_module("tools.audit.interior_survey")

    def inventory(self, sources=None, rows=None, admitted=None):
        rows=[row()] if rows is None else rows
        return self.s.build_inventory(stock() if sources is None else sources,
            rows, admission(rows) if admitted is None else admitted)

    def review(self, inv, explicit=None):
        mapping=(dict(kind="explicit-native",orientations=explicit) if explicit is not None
            else dict(kind="reviewed-rpy",components=[2,1,0],signs=[1,1,1],
                      classes=["Land_House_1W01"]))
        return dict(schema=1,inventory_sha256=inv["inventory_sha256"],
            reviewed=True,evidence_sha256="c"*64,area_policy="stock-origin-radius-v1",
            radius=10,mapping=mapping)

    def plan(self, inv=None, review=None):
        inv=self.inventory() if inv is None else inv
        return self.s.plan_survey(inv,self.review(inv) if review is None else review)

    def evidence(self, plan, index=0, nonce="a"*32):
        batch=plan["batches"][index]
        interfaces={n:"\n".join(v).encode() for n,v in probe.INTERFACES.items()}
        files=probe.generate_probe(STOCK, self.sources["mapgrouppos.xml"]
            if hasattr(self,"sources") else POSITIONS,
            self.sources["mapgroupproto.xml"] if hasattr(self,"sources") else PROTO,
            batch["request"],interfaces,run_id=nonce)
        receipt=fixture.receipt(probe,files)
        return dict(batch_id=batch["id"],files=files,receipt=json.dumps(receipt).encode(),
            outer_timed_out=False,outer_elapsed_seconds=80,external_run_sha256="d"*64)

    def test_inventory_keeps_all_three_denominators_and_does_not_close_feature(self):
        rows=[row(),row("NativeUnplaced"),row("Bullet","",root="CfgAmmo")]
        proto=PROTO.replace(b"</prototype>",b'<group name="UnusedProto"/></prototype>')
        inv=self.inventory(stock(proto=proto),rows)
        self.assertEqual(1,inv["coverage"]["placement_rows"])
        self.assertEqual(2,inv["coverage"]["prototype_rows"])
        self.assertEqual(3,inv["coverage"]["native_rows"])
        self.assertEqual(2,len(inv["classes"]))
        self.assertFalse(inv["gameplay_acceptance"])
        self.assertFalse(inv["world_object_census_complete"])
        self.assertEqual(rows,inv["native_rows"])

    def test_no_review_never_creates_implicitly_reviewed_requests(self):
        inv=self.inventory()
        review=self.review(inv); review["reviewed"]=False
        with self.assertRaises(ValueError):self.plan(inv,review)
        review=self.review(inv); review["inventory_sha256"]="0"*64
        with self.assertRaises(ValueError):self.plan(inv,review)
        review=self.review(inv); review["mapping"]["classes"]=[]
        plan=self.plan(inv,review)
        self.assertEqual([],plan["batches"])
        self.assertIn("coordinate-mapping-unreviewed",plan["rows"][0]["reasons"])

    def test_live_orientation_input_is_explicit_and_rpy_mapping_is_reviewed(self):
        inv=self.inventory()
        planned=self.plan(inv)
        self.assertEqual([90,0,0],planned["batches"][0]["request"]["areas"][0]["expected"][0]["orientation"])
        explicit=self.review(inv,[dict(stock_row=0,orientation=[12,3,4])])
        planned=self.plan(inv,explicit)
        self.assertEqual([12,3,4],planned["batches"][0]["request"]["areas"][0]["expected"][0]["orientation"])
        explicit["mapping"]["orientations"][0]["orientation"][0]=float("nan")
        with self.assertRaises(ValueError):self.plan(inv,explicit)

    def test_ambiguity_and_missing_sources_remain_in_placement_denominator(self):
        positions=POSITIONS.replace(b"</map>",b'<group name="Missing" pos="5 0 5" rpy="0 0 0"/></map>')
        inv=self.inventory(stock(positions),[row(),row()])
        self.assertEqual(2,inv["coverage"]["placement_rows"])
        self.assertIn("ambiguous-native-class",inv["placements"][0]["reasons"])
        self.assertIn("native-class-missing",inv["placements"][1]["reasons"])
        self.assertEqual([],self.plan(inv)["batches"])

    def test_duplicate_physical_rows_and_duplicate_prototypes_never_disappear(self):
        duplicated=POSITIONS.replace(b"</map>",POSITIONS[len(b"<map>"):])
        inv=self.inventory(stock(duplicated))
        self.assertEqual(2,len(inv["placements"]))
        self.assertTrue(all("duplicate-placement-origin" in p["reasons"] for p in inv["placements"]))
        proto=PROTO.replace(b"</prototype>",PROTO[len(b"<prototype>"):])
        inv=self.inventory(stock(proto=proto))
        self.assertEqual(2,inv["coverage"]["prototype_rows"])
        self.assertIn("duplicate-prototype",inv["placements"][0]["reasons"])

    def test_unsupported_geometry_request_caps_remain_backlog_not_exclusions(self):
        points=b"".join(f'<point pos="{i} 0 0"/>'.encode() for i in range(129))
        proto=b'<prototype><group name="Land_House_1W01"><container name="x">'+points+b'</container></group></prototype>'
        inv=self.inventory(stock(proto=proto))
        plan=self.plan(inv)
        self.assertEqual(1,len(plan["rows"]))
        self.assertEqual([],plan["batches"])
        self.assertIn("measurement-generator-unsupported",plan["rows"][0]["reasons"])

    def test_spatial_batches_respect_all_generator_limits(self):
        poses=[f'<group name="Land_House_1W01" pos="{100+i*.2} 10 200" rpy="0 0 90"/>'
               for i in range(33)]
        self.sources=stock(("<map>"+"".join(poses)+"</map>").encode())
        inv=self.inventory(self.sources); plan=self.plan(inv)
        self.assertEqual(33,plan["coverage"]["planned_placements"])
        seen=set()
        for b in plan["batches"]:
            request=b["request"]
            self.assertLessEqual(len(request["areas"]),4)
            expected=[h for a in request["areas"] for h in a["expected"]]
            self.assertLessEqual(len(expected),16)
            self.assertLessEqual(b["ce_reference_points"],512)
            for a in request["areas"]:self.assertLessEqual(a["radius"],25)
            for h in expected:
                self.assertNotIn(h["stock_row"],seen);seen.add(h["stock_row"])
            probe._request(request,self.sources)
            probe._references(request,self.sources["mapgrouppos.xml"],self.sources["mapgroupproto.xml"])
        self.assertEqual(set(range(33)),seen)

    def test_inventory_hash_and_source_metadata_cannot_be_silently_changed(self):
        inv=self.inventory(); inv["placements"][0]["position"][0]+=1
        with self.assertRaises(ValueError):self.plan(inv)
        with self.assertRaises(ValueError):self.inventory({"init.c":STOCK})
        rows=[row()]; adm=admission(rows);adm["RowsWritten"]=2
        with self.assertRaises(ValueError):self.inventory(rows=rows,admitted=adm)

    def test_partial_native_export_remains_explicit(self):
        rows=[row()]; adm=admission(rows,False)
        adm["AdvertisedChildren"]=2
        adm["Roots"][1]["AdvertisedChildren"]=2
        adm["Roots"][1]["EnumerationComplete"]=0
        inv=self.inventory(rows=rows,admitted=adm)
        self.assertEqual(1,inv["coverage"]["native_unvisited_children"])
        self.assertFalse(inv["coverage"]["native_enumeration_complete"])

    def test_merge_requires_exact_batch_and_keeps_acquisition_scope(self):
        inv=self.inventory();plan=self.plan(inv)
        report=self.s.merge_receipts(inv,plan,[self.evidence(plan)])
        self.assertEqual(1,report["coverage"]["measured_placements"])
        self.assertEqual(0,len(report["unmeasured_rows"]))
        self.assertFalse(report["gameplay_acceptance"])
        self.assertFalse(report["survey_complete"])
        self.assertFalse(report["model_identity_verified"])
        self.assertFalse(report["feature_complete"])

    def test_timeout_bad_pose_and_source_drift_never_raise_coverage(self):
        inv=self.inventory();plan=self.plan(inv)
        for case in ("timeout","pose","pin"):
            evidence=self.evidence(plan)
            if case=="timeout":evidence["outer_timed_out"]=True
            if case=="pose":
                value=json.loads(evidence["receipt"]);value["areas"][0]["houses"][0]["position"][0]+=1
                evidence["receipt"]=json.dumps(value).encode()
            if case=="pin":evidence["files"]["init.c"]+=b" "
            report=self.s.merge_receipts(inv,plan,[evidence])
            self.assertEqual(0,report["coverage"]["measured_placements"])
            self.assertEqual(1,len(report["attempts"]))
            self.assertEqual("rejected",report["attempts"][0]["status"])

    def test_repeated_success_does_not_double_count_and_unplanned_batch_rejected(self):
        inv=self.inventory();plan=self.plan(inv);ev=self.evidence(plan)
        report=self.s.merge_receipts(inv,plan,[ev,ev])
        self.assertEqual(1,report["coverage"]["measured_placements"])
        self.assertEqual("rejected",report["attempts"][1]["status"])
        ev=copy.deepcopy(ev);ev["batch_id"]="not-planned"
        with self.assertRaises(ValueError):self.s.merge_receipts(inv,plan,[ev])

    def test_different_request_cannot_hide_behind_valid_receipt(self):
        inv=self.inventory();plan=self.plan(inv);ev=self.evidence(plan)
        manifest=json.loads(ev["files"][probe.MARKER])
        manifest["request"]["areas"][0]["expected"][0]["orientation"]=[3,0,0]
        manifest["request_sha256"]=probe._sha(probe._encode(manifest["request"]))
        ev["files"][probe.MARKER]=probe._encode(manifest)
        row=json.loads(ev["receipt"]);row["request_sha256"]=manifest["request_sha256"]
        row["areas"][0]["houses"][0]["orientation"]=[3,0,0]
        ev["receipt"]=json.dumps(row).encode()
        report=self.s.merge_receipts(inv,plan,[ev])
        self.assertEqual(0,report["coverage"]["measured_placements"])

    def test_model_and_class_coverage_never_imply_all_instances(self):
        positions=POSITIONS.replace(b"</map>",b'<group name="Land_House_1W01" pos="500 10 200" rpy="0 0 90"/></map>')
        self.sources=stock(positions)
        inv=self.inventory(self.sources)
        review=self.review(inv,[dict(stock_row=0,orientation=[90,0,0])])
        plan=self.plan(inv,review); report=self.s.merge_receipts(inv,plan,[self.evidence(plan)])
        self.assertEqual(2,report["coverage"]["placement_rows"])
        self.assertEqual(1,report["coverage"]["measured_placements"])
        self.assertEqual(1,len(report["unmeasured_rows"]))
        self.assertEqual(1,report["classes"][0]["measured_placements"])
        self.assertEqual(2,report["classes"][0]["placement_rows"])

    def test_unknown_xml_children_and_missing_pose_are_preserved(self):
        positions=b'<map><odd/><group name="Land_House_1W01" pos="100 10 200"/></map>'
        inv=self.inventory(stock(positions))
        self.assertEqual(2,len(inv["placements"]))
        self.assertIn("unsupported-placement-node",inv["placements"][0]["reasons"])
        plan=self.plan(inv)
        self.assertIn("stock-rpy-unavailable",plan["rows"][1]["reasons"])

    def test_work_and_input_budgets_fail_explicitly(self):
        from unittest.mock import patch
        with patch.object(self.s,"MAX_WORK",0):
            with self.assertRaises(ValueError):self.inventory()
        with self.assertRaises(ValueError):
            self.inventory(stock(b"<map>\x00</map>"))
        review=self.review(self.inventory());review["radius"]=25.1
        with self.assertRaises(ValueError):self.plan(review=review)


    def test_inventory_scope_lists_are_not_shared_mutable_globals(self):
        first=self.inventory()
        first["missing_survey_data"].clear()
        second=self.inventory()
        self.assertIn("room-labels",second["missing_survey_data"])

    def test_loader_rechecks_admitted_native_chunk_bytes(self):
        from unittest.mock import patch
        rows=[row()];adm=admission(rows)
        manifest=b'{"manifest":1}'
        chunk=json.dumps({"Rows":rows}).encode()
        adm["files"]=[dict(file="manifest.json",bytes=len(manifest),sha256=self.s.digest(manifest)),
            dict(file="chunk-0.json",bytes=len(chunk),sha256=self.s.digest(chunk))]
        from pathlib import Path
        def read(path,limit):
            return manifest if path.name=="manifest.json" else chunk+b" "
        with patch("tools.audit.item_compatibility.scan_manifest",return_value=adm), \
             patch.object(self.s,"_safe",side_effect=Path),patch.object(self.s,"_read",side_effect=read):
            with self.assertRaises(ValueError):
                self.s.load_native(Path("/synthetic/native/manifest.json"),adm["files"][0]["sha256"])

    def test_report_mutation_and_global_prototype_errors_do_not_plan(self):
        inv=self.inventory()
        review=self.review(inv)
        review["mapping"]["components"]=[True,1,2]
        with self.assertRaises(ValueError):self.plan(inv,review)
        proto=PROTO.replace(b"<prototype>",b"<prototype><defaults/><defaults/>")
        inv=self.inventory(stock(proto=proto))
        self.assertEqual([],self.plan(inv)["batches"])
        self.assertIn("global-prototype-unsupported",inv["placements"][0]["reasons"])

    def test_nonce_replay_across_batches_is_rejected(self):
        poses=[f'<group name="Land_House_1W01" pos="{100+i*100} 10 200" rpy="0 0 90"/>'
               for i in range(5)]
        self.sources=stock(("<map>"+"".join(poses)+"</map>").encode())
        inv=self.inventory(self.sources);plan=self.plan(inv)
        self.assertEqual(2,len(plan["batches"]))
        report=self.s.merge_receipts(inv,plan,[self.evidence(plan,0),self.evidence(plan,1)])
        self.assertEqual(4,report["coverage"]["measured_placements"])
        self.assertEqual("replayed-native-run",report["attempts"][1]["reason"])



    def test_unnamed_global_duplicate_cannot_emit_locally_valid_requests(self):
        proto=PROTO.replace(b"<prototype>",b"<prototype><group/><group/>")
        inv=self.inventory(stock(proto=proto))
        self.assertEqual(3,inv["coverage"]["prototype_rows"])
        self.assertEqual([],self.plan(inv)["batches"])



    def test_total_reference_budget_splits_valid_dense_houses(self):
        points=b"".join(f'<point pos="{i} 0 0"/>'.encode() for i in range(128))
        proto=b'<prototype><group name="Land_House_1W01"><container name="x">'+points+b'</container></group></prototype>'
        positions=("<map>"+"".join(f'<group name="Land_House_1W01" pos="{100+i} 10 200" rpy="0 0 90"/>'
                                   for i in range(5))+"</map>").encode()
        inv=self.inventory(stock(positions,proto));plan=self.plan(inv)
        self.assertEqual(5,plan["coverage"]["planned_placements"])
        self.assertEqual([512,128],[b["ce_reference_points"] for b in plan["batches"]])

if __name__=="__main__":unittest.main()
