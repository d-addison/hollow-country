"""Synthetic bytes/OS fixtures execute the real consumer; no engine acceptance."""
import copy
from contextlib import ExitStack, redirect_stdout
import errno
import hashlib
import io
import json
import os
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools.audit import item_compatibility as audit


def encoded(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


class MemoryFiles:
    """Explicit read-only kernel boundary, including NOFOLLOW and descriptor leaks."""
    def __init__(self):
        self.files, self.links, self.handles, self.sizes = {}, set(), {}, {}
        self.serial = 10

    def open(self, name, flags, dir_fd=None):
        assert flags & os.O_NOFOLLOW
        assert flags & os.O_ACCMODE == os.O_RDONLY
        base = self.handles[dir_fd][0] if dir_fd is not None else ""
        path = str(name) if str(name).startswith("/") else base.rstrip("/") + "/" + str(name)
        if path in self.links:
            raise OSError(errno.ELOOP, "synthetic symlink")
        directory = path in ("/", "/synthetic")
        if not directory and path not in self.files:
            raise FileNotFoundError(path)
        if flags & os.O_DIRECTORY and not directory:
            raise NotADirectoryError(path)
        self.serial += 1
        self.handles[self.serial] = (path, io.BytesIO(self.files.get(path, b"")))
        return self.serial

    def read(self, fd, amount):
        return self.handles[fd][1].read(amount)

    def fstat(self, fd):
        path = self.handles[fd][0]
        return SimpleNamespace(st_mode=stat.S_IFREG | 0o400,
                               st_size=self.sizes.get(path, len(self.files[path])),
                               st_mtime_ns=1, st_ctime_ns=1)

    def close(self, fd):
        del self.handles[fd]


def header(chunk=False):
    return dict(SchemaVersion=1,
        Acquisition="effective_native_config_all_classes_in_selected_roots",
        ActualWorld="synthetic_world", ActualBuild="synthetic_build",
        ConfigProvenance="synthetic fixture, not native evidence", RunId="synthetic",
        ProvenancePolicy="caller_supplied_not_independently_verified",
        FieldPolicy="whitelist_present_only_missing_paths_omitted_no_eligibility_inference",
        ArrayPolicy="schema_typed_native_array_reads_element_kind_unverified_per_field",
        BytePolicy="conservative_four_UTF8_bytes_per_string_unit",
        FilePolicy="isolated_profile_single_writer_no_atomic_exclusive_create_API",
        EnumerationOrder="native_child_index_CfgWeapons_then_CfgVehicles",
        FullCoverage=0, Partial=0, StopReason="", StopClassPath="",
        UnresolvedFields=0, KindVariantFields=0, RowsWritten=0, VisitedChildren=0,
        MaxRows=512 if chunk else 16384, MaxBytes=(16 if chunk else 256) << 20,
        MaxFields=96, MaxArrayValues=128, MaxValueUnits=512, MaxAncestors=64,
        MaxVisitedChildren=512 if chunk else 16384, RowByteBound=0,
        SchemaFields=["inventorySlot", "attachments"], Unknowns=["live_geometry"],
        Roots=[])


def field(array=False):
    return dict(ConfigPath="attachments" if array else "inventorySlot",
        ReadAs="text_array" if array else "text", ExpectedReadAs="text_array",
        ConfigType=3 if array else 2, ConfigTypeName="CT_ARRAY" if array else "CT_STRING",
        Status="captured_unresolved" if array else "kind_variant", ValueCaptured=1,
        UnresolvedReasons=["array_element_kind_unverified" if array else "schema_kind_variant"],
        ValueText="", ValueInt=0, ValueFloat=0, TextValues=["fixture"] if array else [],
        IntValues=[], FloatValues=[])


class UnsupportedPlatformTests(unittest.TestCase):
    def test_secure_open_unavailable_fails_before_any_file_open(self):
        with patch.object(audit.os, "supports_dir_fd", set()):
            with patch.object(audit.os, "open") as opened:
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    audit.scan_manifest("manifest.json")
                opened.assert_not_called()


class ManifestTests(unittest.TestCase):
    def setUp(self):
        if not (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
                and hasattr(os, "O_NONBLOCK") and os.open in os.supports_dir_fd):
            self.skipTest("secure POSIX directory-relative reads unavailable")
        self.fs, self.stack = MemoryFiles(), ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.multiple(audit.os, open=self.fs.open,
            read=self.fs.read, fstat=self.fs.fstat, close=self.fs.close,
            supports_dir_fd={self.fs.open}))
        self.path = "/synthetic/manifest.json"
        h = header()
        h.update(RowsWritten=2, VisitedChildren=4, UnresolvedFields=2, KindVariantFields=1)
        h["Roots"] = [dict(ConfigRoot=root, AdvertisedChildren=2, VisitedChildren=2,
                           RowsWritten=1, EnumerationComplete=1)
                      for root in ("CfgWeapons", "CfgVehicles")]
        plan = [dict(RootIndex=i // 2, ChildIndex=i % 2,
                     ChildName=("access", "FixtureA", "FixtureB", "access")[i],
                     ConfigType=4 if i in (1, 2) else 0,
                     ConfigTypeName="CT_CLASS" if i in (1, 2) else "CT_INT")
                for i in range(4)]
        self.chunks = []
        refs = []
        for seq, index in enumerate((1, 2)):
            row = dict(ConfigRoot=h["Roots"][seq]["ConfigRoot"], ItemClass=plan[index]["ChildName"],
                ParentClass="", ConfigAncestors=[], Fields=[field(), field(True)] if seq == 0 else [],
                UnresolvedFields=2 if seq == 0 else 0, KindVariantFields=1 if seq == 0 else 0)
            ch = header(True)
            ch.update(RowsWritten=1, VisitedChildren=2, UnresolvedFields=row["UnresolvedFields"],
                      KindVariantFields=row["KindVariantFields"],
                      RowByteBound=4 * (len(encoded(row)) + 1))
            chunk = dict(ArtifactKind="item_compatibility_chunk", Header=ch, Sequence=seq,
                StartPlanIndex=seq * 2, NextPlanIndex=seq * 2 + 2,
                BoundaryReason="byte_target" if seq == 0 else "end_plan",
                RowPlanIndices=[index], NonClassPlanIndices=[0 if seq == 0 else 3])
            self.chunks.append(dict(Chunk=chunk, Rows=[row]))
            refs.append(dict(FileName=f"chunk-{seq}.json", Sequence=seq, StartPlanIndex=seq * 2,
                NextPlanIndex=seq * 2 + 2, RowsWritten=1, NonClassChildren=1,
                ByteBound=0, ReadbackVerified=1))
        h["RowByteBound"] = sum(c["Chunk"]["Header"]["RowByteBound"] for c in self.chunks)
        self.m = dict(SchemaVersion=1, ArtifactKind="item_compatibility_manifest",
            IntegrityPolicy="readback_equality_only_external_SHA256_required", Header=h,
            FullCoverage=0, IndexPlanComplete=1, EnumerationComplete=1, AdvertisedChildren=4,
            ExpectedClassRows=2, NonClassChildren=2, CommittedChunkByteBound=0,
            UncommittedFile="", UncommittedByteBound=0, MaxChildren=16384, MaxChunks=64,
            MaxChunkBytes=16 << 20, MaxTotalBytes=256 << 20, TargetChildrenPerChunk=512,
            MaxManifestBytes=8 << 20, IndexPlan=plan, Chunks=refs)
        self.save()

    def tearDown(self):
        self.assertEqual({}, self.fs.handles, "all descriptors must close on rejection")

    def save(self):
        for seq, data in enumerate(self.chunks):
            raw = encoded(data)
            self.fs.files[f"/synthetic/chunk-{seq}.json"] = raw
            self.m["Chunks"][seq]["ByteBound"] = len(raw) * 4
        self.m["CommittedChunkByteBound"] = sum(c["ByteBound"] for c in self.m["Chunks"])
        self.fs.files[self.path] = encoded(self.m)

    def scan(self, pin=None):
        return audit.scan_manifest(self.path, expected_sha256=pin)

    def test_complete_report_pins_exact_bytes_without_feature_claims(self):
        pin = hashlib.sha256(self.fs.files[self.path]).hexdigest()
        report = self.scan(pin)
        self.assertEqual(("complete", 2, 4, 2, 1),
            (report["status"], report["RowsWritten"], report["VisitedChildren"],
             report["UnresolvedFields"], report["KindVariantFields"]))
        self.assertIs(report["FullCoverage"], False)
        self.assertEqual({"array_element_kind_unverified": 1, "schema_kind_variant": 1},
                         report["UnresolvedReasons"])
        self.assertEqual(3, len(report["files"]))
        for record in report["files"]:
            raw = self.fs.files["/synthetic/" + record["file"]]
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()),
                             (record["bytes"], record["sha256"]))
        self.assertNotIn("Rows", report)

    def test_missing_and_truncated_committed_chunks_rejected(self):
        raw = self.fs.files.pop("/synthetic/chunk-1.json")
        with self.assertRaises((ValueError, OSError)):
            self.scan()
        self.fs.files["/synthetic/chunk-1.json"] = raw[:-1]
        with self.assertRaises(ValueError):
            self.scan()

    def test_row_identity_corruption_rejected_even_with_correct_byte_bound(self):
        self.chunks[0]["Rows"][0]["ItemClass"] = "DifferentFixture"
        self.save()
        with self.assertRaisesRegex(ValueError, "row identity"):
            self.scan()

    def test_duplicate_nonfinite_invalid_utf8_and_depth_rejected(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b"\xff",
                    b"[" * 33 + b"0" + b"]" * 33):
            self.fs.files[self.path] = raw
            with self.subTest(raw=raw[:32]), self.assertRaises(ValueError):
                self.scan()

    def test_partial_prefix_remains_partial(self):
        self.chunks = self.chunks[:1]
        self.m["Chunks"] = self.m["Chunks"][:1]
        self.m.update(EnumerationComplete=0, NonClassChildren=1)
        h = self.m["Header"]
        h.update(Partial=1, StopReason="synthetic source failure", RowsWritten=1,
                 VisitedChildren=2, RowByteBound=self.chunks[0]["Chunk"]["Header"]["RowByteBound"])
        h["Roots"][1].update(VisitedChildren=0, RowsWritten=0, EnumerationComplete=0)
        self.save()
        report = self.scan()
        self.assertEqual("partial", report["status"])
        self.assertIs(report["EnumerationComplete"], False)
        self.assertIs(report["FullCoverage"], False)
        self.m.update(EnumerationComplete=1)
        self.save()
        with self.assertRaises(ValueError):
            self.scan()

    def test_gaps_overlaps_partitions_and_per_root_denominators_rejected(self):
        original = copy.deepcopy((self.m, self.chunks))
        for change in ("gap", "partition", "root", "child", "duplicate"):
            self.m, self.chunks = copy.deepcopy(original)
            if change == "gap":
                self.m["Chunks"][1]["StartPlanIndex"] = 1
            elif change == "partition":
                self.chunks[0]["Chunk"]["NonClassPlanIndices"] = []
            elif change == "root":
                self.m["Header"]["Roots"][1]["AdvertisedChildren"] = 1
            elif change == "child":
                self.m["IndexPlan"][1]["ChildIndex"] = 0
            else:
                self.m["IndexPlan"][0].update(ConfigType=4, ConfigTypeName="CT_CLASS",
                                             ChildName="fixturea")
            self.save()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.scan()

    def test_exact_header_and_uncertainty_counts_are_required(self):
        original = copy.deepcopy((self.m, self.chunks))
        for key in ("RunId", "ActualWorld", "ActualBuild", "SchemaFields", "UnresolvedFields"):
            self.m, self.chunks = copy.deepcopy(original)
            ch = self.chunks[0]["Chunk"]["Header"]
            ch[key] = ["other"] if key == "SchemaFields" else 3 if key == "UnresolvedFields" else "other"
            self.save()
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.scan()

    def test_only_explicit_native_boolean_values_accepted(self):
        for value in (2, "0", 0.0, None):
            self.m["FullCoverage"] = value
            self.save()
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.scan()
        self.m["FullCoverage"] = False
        self.save()
        self.assertFalse(self.scan()["FullCoverage"])

    def test_pin_mismatch_and_invalid_pin_rejected(self):
        for value in ("0" * 64, "../wrong", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.scan(value)

    def test_traversal_and_symlink_components_rejected(self):
        with self.assertRaises(ValueError):
            audit.scan_manifest("/synthetic/../synthetic/manifest.json")
        for path in ("/synthetic", self.path, "/synthetic/chunk-0.json"):
            self.fs.links.add(path)
            with self.subTest(path=path), self.assertRaises(OSError):
                self.scan()
            self.fs.links.clear()
        self.m["Chunks"][0]["FileName"] = "../chunk-0.json"
        self.save()
        with self.assertRaises(ValueError):
            self.scan()

    def test_nodes_files_chunks_and_aggregate_bytes_are_bounded(self):
        for name in ("MAX_NODES", "MAX_TOTAL_NODES"):
            with patch.object(audit, name, 1), self.assertRaisesRegex(ValueError, "node budget"):
                self.scan()
        self.fs.sizes["/synthetic/chunk-0.json"] = (16 << 20) + 1
        with self.assertRaisesRegex(ValueError, "file byte budget"):
            self.scan()
        self.fs.sizes.clear()
        self.m["Chunks"] *= 33
        self.fs.files[self.path] = encoded(self.m)
        with self.assertRaises(ValueError):
            self.scan()
        state = dict(bytes=audit.MAX_TOTAL_BYTES, pins=[])
        directory, _ = audit.parent_handle(self.path)
        try:
            with self.assertRaisesRegex(ValueError, "aggregate byte"):
                audit.read_file(directory, "manifest.json", 8 << 20, state)
        finally:
            audit.os.close(directory)

    def test_full_coverage_and_corrupt_uncertainty_claims_rejected(self):
        for target in (self.m, self.m["Header"], self.chunks[0]["Chunk"]["Header"]):
            target["FullCoverage"] = 1
            self.save()
            with self.assertRaises(ValueError):
                self.scan()
            target["FullCoverage"] = 0
        self.chunks[0]["Rows"][0]["Fields"][0]["UnresolvedReasons"] = []
        self.save()
        with self.assertRaisesRegex(ValueError, "uncertainty"):
            self.scan()

    def test_cli_json_stdout_success_and_failure(self):
        for pin, code in ((None, 0), ("0" * 64, 1)):
            output = io.StringIO()
            args = ["--manifest", self.path]
            if pin:
                args += ["--expect-manifest-sha256", pin]
            with redirect_stdout(output):
                actual = audit.main(args)
            self.assertEqual(code, actual)
            report = json.loads(output.getvalue())
            self.assertIs(report["FullCoverage"], False)
            self.assertEqual("invalid" if code else "complete", report["status"])
