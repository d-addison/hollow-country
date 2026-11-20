"""Behavioural tests for tools/package/search_context.py (contract section 6).

Every XML fixture below is explicit synthetic data, never stock data: FIXTURE_META marks it.
Offline tests prove the schema, the caps and the refusals only, never DayZ behaviour."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.package import search_context as sc  # noqa: E402

FIXTURE_META = {"Synthetic": True, "Purpose": "search_context unit tests"}


def proto(groups):
    """groups: [(name, [usage], [(container, [category], [tag], npoints)])] -> bytes."""
    out = ["<prototype>"]
    for name, usages, containers in groups:
        out.append('<group name="%s" lootmax="3">' % name)
        out += ['<usage name="%s"/>' % u for u in usages]
        for cname, cats, tags, count in containers:
            out.append('<container name="%s" lootmax="2">' % cname)
            out += ['<category name="%s"/>' % c for c in cats]
            out += ['<tag name="%s"/>' % t for t in tags]
            out += ['<point pos="%d 0 %d" range="0.4" height="1.0"/>' % (i, i) for i in range(count)]
            out.append("</container>")
        out.append("</group>")
    out.append("</prototype>")
    return "\n".join(out).encode()


def types(rows):
    """rows: [(name, nominal, category, [usage], [tag])] -> bytes."""
    out = ["<types>"]
    for name, nominal, cat, usages, tags in rows:
        out.append('<type name="%s"><nominal>%d</nominal>' % (name, nominal))
        if cat:
            out.append('<category name="%s"/>' % cat)
        out += ['<usage name="%s"/>' % u for u in usages]
        out += ['<tag name="%s"/>' % t for t in tags]
        out.append("</type>")
    out.append("</types>")
    return "\n".join(out).encode()


BASIC_PROTO = proto([
    ("Land_A", ["Village"], [("lootshelves", ["tools"], ["shelves"], 3), ("loot", ["tools", "food"], [], 2)]),
    ("Land_B", ["Village", "Farm"], [("lootshelves", ["tools"], ["shelves"], 1)]),
    ("Land_C", ["Police"], [("lootFloor", ["weapons"], ["floor"], 4)]),
])
BASIC_TYPES = types([
    ("Hammer", 5, "tools", ["Village"], ["shelves"]),
    ("Pliers", 5, "tools", ["Village", "Police"], []),
    ("Rag", 5, "tools", [], ["shelves"]),            # no usage -> matches any usage
    ("Wrench", 0, "tools", ["Village"], ["shelves"]),  # nominal 0 -> excluded
    ("Bread", 5, "food", ["Village"], []),
    ("Rifle", 5, "weapons", ["Police"], ["floor"]),
    ("Shelfless", 5, "tools", ["Village"], ["floor"]),  # tag does not intersect
    ("Farmtool", 5, "tools", ["Farm"], ["shelves"]),   # usage does not intersect Village
])


class BuildTests(unittest.TestCase):
    def test_unsupported_containers_stay_vanilla_and_are_counted(self):
        pr = proto([("Land_A", [], [("lootFactory", ["tools"], [], 2),
                                    ("lootFactory", ["tools"], [], 1),
                                    ("loot", ["tools"], [], 1),
                                    ("lootweapons", [], [], 1)])])
        chunks, report = sc.build_search_groups(pr, types([("Hammer", 1, "tools", [], [])]))
        groups = [g for c in chunks for g in json.loads(c)["Groups"]]
        self.assertEqual([g["Container"] for g in groups], ["loot"])
        self.assertEqual(report["UnsupportedContainersDropped"], 2)
        self.assertTrue(all(g["Categories"] for g in groups))

    def test_group_chunks_split_at_512_even_when_byte_budget_allows_more(self):
        groups = [{"Id": "g-%04d" % i} for i in range(513)]
        with mock.patch.object(sc, "MAX_CHUNK_BYTES", 1000000):
            docs = [json.loads(c) for c in sc._chunk(groups)]
        self.assertEqual([len(d["Groups"]) for d in docs], [512, 1])
        self.assertEqual(sc._chunk([]), [])

    def test_groups_are_distinct_keys_with_filtered_sorted_items(self):
        chunks, report = sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)
        docs = [json.loads(c) for c in chunks]
        self.assertEqual([d["Chunk"] for d in docs], list(range(len(docs))))
        for d in docs:
            self.assertEqual(d["SchemaVersion"], 2)
        groups = [g for d in docs for g in d["Groups"]]
        by_key = {(tuple(g["Usages"]), g["Container"], tuple(g["Categories"]), tuple(g["Tags"])): g for g in groups}
        shelves = by_key[(("Village",), "lootshelves", ("tools",), ("shelves",))]
        self.assertEqual(shelves["Items"], ["Hammer", "Pliers", "Rag"])
        self.assertEqual(by_key[(("Farm", "Village"), "lootshelves", ("tools",), ("shelves",))]["Items"],
                         ["Farmtool", "Hammer", "Pliers", "Rag"])
        self.assertEqual(by_key[(("Village",), "loot", ("food", "tools"), ())]["Items"],
                         ["Bread", "Pliers"])
        self.assertEqual(by_key[(("Police",), "lootFloor", ("weapons",), ("floor",))]["Items"], ["Rifle"])
        self.assertEqual(len(groups), 4)
        for g in groups:
            self.assertTrue(1 <= len(g["Items"]) <= 256)
            self.assertEqual(g["Items"], sorted(set(g["Items"])))

    def test_identical_keys_share_one_group_and_the_class_map_lists_it(self):
        two = proto([("Land_A", ["Village"], [("loot", ["tools"], [], 2)]),
                     ("Land_B", ["Village"], [("loot", ["tools"], [], 5)])])
        chunks, report = sc.build_search_groups(two, BASIC_TYPES)
        groups = json.loads(chunks[0])["Groups"]
        self.assertEqual(len(groups), 1)
        gid = groups[0]["Id"]
        self.assertEqual(report["ClassGroups"]["Land_A"], [{"Container": "loot", "Group": gid, "Points": 2}])
        self.assertEqual(report["ClassGroups"]["Land_B"], [{"Container": "loot", "Group": gid, "Points": 5}])

    def test_ids_are_sequential_and_output_is_deterministic(self):
        first = sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)
        second = sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)
        self.assertEqual(first[0], second[0])
        self.assertEqual(first[1], second[1])
        ids = [g["Id"] for c in first[0] for g in json.loads(c)["Groups"]]
        self.assertEqual(ids, ["g-%04d" % i for i in range(len(ids))])
        # input order must not change the pack
        shuffled = proto([("Land_C", ["Police"], [("lootFloor", ["weapons"], ["floor"], 4)]),
                          ("Land_B", ["Village", "Farm"], [("lootshelves", ["tools"], ["shelves"], 1)]),
                          ("Land_A", ["Village"], [("lootshelves", ["tools"], ["shelves"], 3),
                                                   ("loot", ["tools", "food"], [], 2)])])
        self.assertEqual(sc.build_search_groups(shuffled, BASIC_TYPES)[0], first[0])

    def test_chunks_are_compact_ascii_json_under_the_byte_cap(self):
        chunks, report = sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)
        for chunk in chunks:
            chunk.decode("ascii")
            self.assertLessEqual(len(chunk), sc.MAX_CHUNK_BYTES)
            self.assertNotIn(b"\n", chunk)
            self.assertNotIn(b": ", chunk)
        self.assertEqual(sc.MAX_CHUNK_BYTES, 32767)
        self.assertEqual(sc.MAX_CHUNKS, 64)
        self.assertEqual([c["Bytes"] for c in report["Chunks"]], [len(c) for c in chunks])

    def test_many_groups_split_into_several_chunks_each_under_the_cap(self):
        many = [("Land_%03d" % i, ["U%03d" % i], [("loot", ["tools"], [], 1)]) for i in range(120)]
        rows = [("Item%03d" % i, 5, "tools", ["U%03d" % i], []) for i in range(120)]
        rows += [("Common%03d" % i, 5, "tools", [], []) for i in range(120)]
        chunks, report = sc.build_search_groups(proto(many), types(rows))
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks), sc.MAX_CHUNKS)
        total = 0
        for chunk in chunks:
            self.assertLessEqual(len(chunk), sc.MAX_CHUNK_BYTES)
            total += len(json.loads(chunk)["Groups"])
        self.assertEqual(total, 120)

    def test_group_with_more_than_1024_items_is_refused_not_emitted(self):
        rows = [("Bulk%04d" % i, 5, "tools", [], []) for i in range(1025)]
        rows.append(("Hammer", 5, "food", ["Village"], []))
        pr = proto([("Land_Big", ["Village"], [("loot", ["tools"], [], 2)]),
                    ("Land_Ok", ["Village"], [("loot", ["food"], [], 1)])])
        chunks, report = sc.build_search_groups(pr, types(rows))
        groups = [g for c in chunks for g in json.loads(c)["Groups"]]
        self.assertEqual([g["Items"] for g in groups], [["Hammer"]])
        self.assertEqual(len(report["OverBudget"]), 1)
        self.assertEqual(report["OverBudget"][0]["Items"], 1025)
        self.assertEqual(report["ClassGroups"]["Land_Big"],
                         [{"Container": "loot", "Group": None, "Points": 2, "Refused": "over_budget"}])
        self.assertIn("Land_Big", report["OverBudgetClasses"])

    def test_exactly_1024_items_is_kept_by_default(self):
        rows = [("Bulk%04d" % i, 5, "tools", [], []) for i in range(1024)]
        chunks, report = sc.build_search_groups(proto([("Land_X", ["Village"], [("loot", ["tools"], [], 1)])]),
                                                types(rows))
        self.assertEqual(sum(len(g["Items"]) for c in chunks for g in json.loads(c)["Groups"]), 1024)
        self.assertEqual(report["OverBudget"], [])
        self.assertEqual(report["MaxItemsPerGroup"], 1024)

    def test_operator_may_raise_the_item_cap_up_to_the_runtime_limit_only(self):
        rows = [("Bulk%04d" % i, 5, "tools", [], []) for i in range(300)]
        pr = proto([("Land_X", ["Village"], [("loot", ["tools"], [], 1)])])
        self.assertEqual(sc.build_search_groups(pr, types(rows), max_items=256)[1]["OverBudget"][0]["Items"], 300)
        chunks, report = sc.build_search_groups(pr, types(rows))
        self.assertEqual(len(json.loads(chunks[0])["Groups"][0]["Items"]), 300)
        self.assertEqual(report["MaxItemsPerGroup"], 1024)
        for bad in (0, 1025, True, "9"):
            with self.assertRaises(sc.SearchContextError):
                sc.build_search_groups(pr, types(rows), max_items=bad)

    def test_group_without_items_is_omitted_and_reported(self):
        pr = proto([("Land_Empty", ["Nowhere"], [("loot", ["nothing"], [], 1)])])
        chunks, report = sc.build_search_groups(pr, BASIC_TYPES)
        self.assertEqual(sum(len(json.loads(c)["Groups"]) for c in chunks), 0)
        self.assertEqual(len(report["EmptyGroups"]), 1)
        self.assertIn("Land_Empty", report["EmptyClasses"])
        self.assertEqual(report["ClassGroups"]["Land_Empty"][0]["Refused"], "empty")

    def test_report_pins_inputs_chunks_and_generator(self):
        chunks, report = sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)
        import hashlib
        self.assertEqual(report["Sources"]["mapgroupproto"], hashlib.sha256(BASIC_PROTO).hexdigest())
        self.assertEqual(report["Sources"]["types"], hashlib.sha256(BASIC_TYPES).hexdigest())
        self.assertEqual(report["Sources"]["search-generator"], sc.generator_sha256())
        self.assertEqual(len(report["Sources"]["search-generator"]), 64)
        for row, chunk in zip(report["Chunks"], chunks):
            self.assertEqual(row["Sha256"], hashlib.sha256(chunk).hexdigest())
            self.assertRegex(row["File"], r"^search-groups-\d{3}\.json$")


class RefusalTests(unittest.TestCase):
    def refuses(self, pr, ty, text):
        with self.assertRaises(sc.SearchContextError) as ctx:
            sc.build_search_groups(pr, ty)
        self.assertIn(text, str(ctx.exception))

    def test_malformed_xml_is_refused(self):
        self.refuses(b"<prototype><group", BASIC_TYPES, "malformed")
        self.refuses(BASIC_PROTO, b"<types><type", "malformed")

    def test_dtd_and_entities_are_refused(self):
        evil = b'<!DOCTYPE x [<!ENTITY a "b">]><prototype/>'
        self.refuses(evil, BASIC_TYPES, "DTD")

    def test_utf16_encoded_dtd_and_entities_are_refused(self):
        for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
            def evil(root):
                text = '<?xml version="1.0" encoding="%s"?><!DOCTYPE x [<!ENTITY a "b">]><%s/>' % (encoding, root)
                return text.encode(encoding)
            # utf-16 with a BOM is the byte-search bypass: it must be refused for its DTD.
            # The -le/-be names are not expat encodings, so they are refused as unreadable.
            word = "DTD" if encoding == "utf-16" else "mapgroupproto"
            self.refuses(evil("prototype"), BASIC_TYPES, word)
            self.refuses(BASIC_PROTO, evil("types"), "DTD" if encoding == "utf-16" else "types.xml")

    def test_wrong_root_is_refused(self):
        self.refuses(b"<other/>", BASIC_TYPES, "root")
        self.refuses(BASIC_PROTO, b"<other/>", "root")

    def test_duplicate_group_name_is_refused(self):
        dup = proto([("Land_A", ["Village"], [("loot", ["tools"], [], 1)]),
                     ("Land_A", ["Village"], [("loot", ["tools"], [], 1)])])
        self.refuses(dup, BASIC_TYPES, "duplicate group")

    def test_duplicate_type_name_is_refused(self):
        dup = types([("Hammer", 5, "tools", [], []), ("Hammer", 5, "tools", [], [])])
        self.refuses(BASIC_PROTO, dup, "duplicate type")

    def test_unsafe_names_are_refused(self):
        bad = types([("Bad Name", 5, "tools", ["Village"], [])])
        self.refuses(BASIC_PROTO, bad, "unsafe")
        badp = proto([("Land_A", ["Vill age"], [("loot", ["tools"], [], 1)])])
        self.refuses(badp, BASIC_TYPES, "unsafe")

    def test_bad_nominal_is_refused(self):
        bad = b'<types><type name="Hammer"><nominal>many</nominal></type></types>'
        self.refuses(BASIC_PROTO, bad, "nominal")

    def test_oversize_input_is_refused(self):
        self.refuses(b"<prototype>" + b" " * (sc.interior_points.MAX_STOCK_BYTES + 1) + b"</prototype>",
                     BASIC_TYPES, "too large")

    def test_more_than_64_chunks_is_refused(self):
        old = sc.MAX_CHUNK_BYTES
        try:
            sc.MAX_CHUNK_BYTES = 200  # force many tiny chunks, each group alone still fits
            many = [("Land_%03d" % i, ["U%03d" % i], [("loot", ["tools"], [], 1)]) for i in range(70)]
            rows = [("Item%03d" % i, 5, "tools", ["U%03d" % i], []) for i in range(70)]
            self.refuses(proto(many), types(rows), "chunks")
        finally:
            sc.MAX_CHUNK_BYTES = old

    def test_single_group_larger_than_the_cap_is_refused(self):
        old = sc.MAX_CHUNK_BYTES
        try:
            sc.MAX_CHUNK_BYTES = 60
            self.refuses(BASIC_PROTO, BASIC_TYPES, "chunk")
        finally:
            sc.MAX_CHUNK_BYTES = old


class CliTests(unittest.TestCase):
    def test_cli_writes_chunks_and_report_outside_the_checkout_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            pr, ty = Path(tmp, "proto.xml"), Path(tmp, "types.xml")
            pr.write_bytes(BASIC_PROTO)
            ty.write_bytes(BASIC_TYPES)
            out = Path(tmp, "out")
            code = sc.main(["--mapgroupproto", str(pr), "--types", str(ty), "--output-dir", str(out)])
            self.assertEqual(code, 0)
            names = sorted(p.name for p in out.iterdir())
            self.assertIn("search-groups-000.json", names)
            self.assertIn("search-context-report.json", names)
            report = json.loads(Path(out, "search-context-report.json").read_text())
            self.assertEqual(report["Chunks"][0]["File"], "search-groups-000.json")
            self.assertEqual(Path(out, "search-groups-000.json").read_bytes(),
                             sc.build_search_groups(BASIC_PROTO, BASIC_TYPES)[0][0])
            self.assertNotEqual(sc.main(["--mapgroupproto", str(pr), "--types", str(ty),
                                         "--output-dir", str(out)]), 0)

    def test_cli_refuses_an_output_inside_the_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            pr, ty = Path(tmp, "proto.xml"), Path(tmp, "types.xml")
            pr.write_bytes(BASIC_PROTO)
            ty.write_bytes(BASIC_TYPES)
            inside = ROOT / "templates-should-not-exist"
            self.assertNotEqual(sc.main(["--mapgroupproto", str(pr), "--types", str(ty),
                                         "--output-dir", str(inside)]), 0)
            self.assertFalse(inside.exists())

    def test_cli_refuses_malformed_input_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            pr, ty = Path(tmp, "proto.xml"), Path(tmp, "types.xml")
            pr.write_bytes(b"<prototype")
            ty.write_bytes(BASIC_TYPES)
            out = Path(tmp, "out")
            self.assertNotEqual(sc.main(["--mapgroupproto", str(pr), "--types", str(ty),
                                         "--output-dir", str(out)]), 0)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
