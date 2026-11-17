"""Source-census behavior with invented inline scripts; never DayZ acceptance."""
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class MemoryTree:
    """Inline synthetic filesystem: tests require no disk writes or game files.

    Only filesystem boundaries are substituted; traversal, bounded reading,
    lexing, ancestry, reconciliation, hashing and CLI serialization execute.
    """

    def __init__(self):
        self.nodes = {}
        self.handles = {}

    def directory(self, path, *args, **kwargs):
        for parent in reversed((path, *path.parents)):
            self.nodes.setdefault(str(parent), (stat.S_IFDIR | 0o755, b""))

    def metadata(self, path, *, follow_symlinks=True):
        mode, data = self.nodes[str(path)] if str(path) in self.nodes else self.missing(path)
        if follow_symlinks and stat.S_ISLNK(mode):
            return self.metadata(Path(data))
        return SimpleNamespace(st_mode=mode, st_size=len(data), st_dev=1,
                               st_ino=sorted(self.nodes).index(str(path)) + 1,
                               st_mtime_ns=0, st_file_attributes=0)

    def missing(self, path):
        raise FileNotFoundError(str(path))

    def open(self, path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        writable = any(flag in mode for flag in "wax+")
        if not writable:
            self.metadata(path)
        data = self.nodes.get(str(path), (0, b""))[1]
        fs = self

        class Handle(io.BytesIO):
            def close(self):
                if writable and not self.closed:
                    fs.nodes[str(path)] = (stat.S_IFREG | 0o644, self.getvalue())
                super().close()

            def fileno(self):
                number = id(self)
                fs.handles[number] = path
                return number

        handle = Handle(b"" if "w" in mode else data)
        if "a" in mode:
            handle.seek(0, io.SEEK_END)
        if "b" in mode:
            return handle
        return io.TextIOWrapper(handle, encoding=encoding or "utf-8", errors=errors, newline=newline)

    def scandir(self, path):
        self.metadata(Path(path))
        children = [Path(name) for name in self.nodes if Path(name).parent == Path(path)]
        fs = self

        class Scan:
            def __enter__(self):
                return iter(self)

            def __exit__(self, *args):
                return False

            def __iter__(self):
                for child in children:
                    yield SimpleNamespace(name=child.name, path=str(child),
                                          stat=lambda follow_symlinks=True, p=child: fs.metadata(p, follow_symlinks=follow_symlinks))

        return Scan()

    def copy(self, source, destination):
        for name, node in list(self.nodes.items()):
            if Path(name) == source or source in Path(name).parents:
                self.nodes[str(destination / Path(name).relative_to(source))] = node


SYNTHETIC_BASE = "class RecipeBase { void Init(); };\n"
SYNTHETIC_RECIPES = '''
class SyntheticParent extends RecipeBase {
    override void Init() {
        InsertIngredient(0, "SyntheticCloth");
        InsertIngredientEx(1, "SyntheticKnife", "synthetic_sound");
        AddResult("SyntheticStrip");
        m_ResultSetFullQuantity[0] = false;
    }
};
class SyntheticChild : SyntheticParent {
    override bool CanDo(ItemBase ingredients[], PlayerBase player) {
        return SyntheticPolicy.Check(ingredients, player);
    }
    override void Do() { SyntheticPolicy.Mutate(); }
};
class SyntheticDisabled extends RecipeBase {};
class SyntheticUnregistered extends RecipeBase {};
'''
SYNTHETIC_REGISTRY = '''
class SyntheticManager {
    protected void RegisterRecipe(RecipeBase recipe);
    void RegisterRecipies() {
        RegisterRecipe(new SyntheticParent);
        RegisterRecipe(new SyntheticChild());
        // RegisterRecipe(new SyntheticDisabled);
    }
};
'''


class CraftingAuditTests(unittest.TestCase):
    def setUp(self):
        # Import first: missing implementation is the actual initial RED.
        self.module = importlib.import_module("tools.audit.crafting_audit")
        self.fs = MemoryTree()
        self.workspace = ROOT / "__synthetic_crafting__"
        boundaries = [
            patch.object(Path, "mkdir", lambda p, *a, **kw: self.fs.directory(p)),
            patch.object(Path, "stat", lambda p, **kw: self.fs.metadata(p, **kw)),
            patch.object(Path, "lstat", lambda p: self.fs.metadata(p, follow_symlinks=False)),
            patch.object(Path, "resolve", lambda p, **kw: p.absolute()),
            patch.object(Path, "open", lambda p, *a, **kw: self.fs.open(p, *a, **kw)),
            patch.object(Path, "symlink_to", lambda p, target, **kw: self.fs.nodes.__setitem__(str(p), (stat.S_IFLNK | 0o777, str(target)))),
            patch.object(Path, "unlink", lambda p: self.fs.nodes.pop(str(p))),
            patch.object(Path, "rglob", lambda p, pattern: (Path(n) for n in self.fs.nodes if p in Path(n).parents and Path(n).name == pattern)),
            patch.object(self.module.os, "scandir", self.fs.scandir),
            patch.object(self.module.os, "fstat", lambda fd: self.fs.metadata(self.fs.handles[fd])),
        ]
        for boundary in boundaries:
            boundary.start()
            self.addCleanup(boundary.stop)
        self.tree = self.workspace / "scripts"
        self.tree.mkdir()
        self.write("RecipeBase.c", SYNTHETIC_BASE)
        self.write("Recipes/Definitions.c", SYNTHETIC_RECIPES)
        self.write("Elsewhere/Registry.c", SYNTHETIC_REGISTRY)

    def write(self, relative, content):
        path = self.tree / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def audit(self, **kwargs):
        return self.module.audit_tree(self.tree, **kwargs)

    def rows(self, report):
        return {row["class"]: row for row in report["recipes"]}

    def codes(self, report):
        return {row["code"] for row in report["diagnostics"]}

    def cli(self, *args):
        return self.run_cli(["--root", str(self.tree), *map(str, args)])

    def run_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "stdout", stdout), patch.object(sys, "stderr", stderr):
            try:
                code = self.module.main(args)
            except SystemExit as error:
                code = error.code
        return SimpleNamespace(returncode=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    def test_declared_registered_disabled_and_runtime_unknown_are_distinct(self):
        report = self.audit()
        self.assertTrue(report["valid"], report["diagnostics"])
        self.assertTrue(report["inputs_complete"])
        self.assertEqual(report["coverage"]["declared_recipe_classes"], 4)
        self.assertEqual(report["coverage"]["source_registered_names"], 2)
        rows = self.rows(report)
        self.assertEqual(rows["SyntheticParent"]["source_status"], "registered")
        self.assertEqual(rows["SyntheticDisabled"]["source_status"], "disabled")
        self.assertEqual(rows["SyntheticUnregistered"]["source_status"], "unregistered")
        self.assertTrue(all(row["runtime_status"] == "unknown" for row in rows.values()))
        self.assertIsNone(report["coverage"]["runtime_registered_recipes"])
        self.assertIsNone(report["coverage"]["merged_item_config_classes"])
        self.assertFalse(report["coverage"]["full_native_crafting_coverage"])

    def test_native_attachment_combinations_proxies_power_and_actions_stay_unknown(self):
        report = self.audit()
        self.assertEqual(report["coverage"]["attachment_utility"], {
            "status": "unknown", "combinations": None,
            "scope": ["native_attachments", "proxies", "power", "actions"],
        })

    def test_legacy_encoding_requires_explicit_policy_and_pins_raw_bytes(self):
        content = b"class SyntheticLegacy extends RecipeBase {}; // invented trademark \x99\n"
        self.write("Legacy.c", content)
        self.assertFalse(self.audit()["valid"])
        report = self.audit(fallback_encoding="cp1252")
        self.assertTrue(report["valid"], report["diagnostics"])
        source = next(row for row in report["sources"] if row["path"] == "Legacy.c")
        self.assertEqual(source["encoding"], "cp1252")
        self.assertEqual(source["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(self.cli("--fallback-encoding", "cp1252").returncode, 0)
        self.assertIn("invalid_encoding_policy", self.codes(self.audit(fallback_encoding="guess")))

    def test_registered_nonrecipe_is_a_candidate_not_an_extra_derived_declaration(self):
        self.write("NotRecipe.c", '''class SyntheticNotRecipe {};
            class NotRecipeRegistry { void Run() { RegisterRecipe(new SyntheticNotRecipe); } };''')
        report = self.audit()
        self.assertEqual(report["coverage"]["declared_recipe_classes"], 4)
        self.assertFalse(self.rows(report)["SyntheticNotRecipe"]["recipe_ancestry_resolved"])

    def test_full_tree_inherited_colon_and_case_insensitive_suffix(self):
        self.write("Other/Deep/Extra.C", '''class SyntheticExtra : SyntheticChild {};
            class ExtraRegistry { void Run() { RegisterRecipe(new SyntheticExtra); } };''')
        report = self.audit()
        row = self.rows(report)["SyntheticExtra"]
        self.assertEqual(row["source_status"], "registered")
        self.assertEqual(row["ancestry"], ["SyntheticExtra", "SyntheticChild", "SyntheticParent", "RecipeBase"])
        self.assertEqual(report["coverage"]["declared_recipe_classes"], 5)
        self.assertIn("Other/Deep/Extra.C", {row["path"] for row in report["sources"]})

    def test_strings_comments_and_disabled_evidence_do_not_create_live_calls(self):
        self.write("Noise.c", r'''
            // RegisterRecipe(new SyntheticCommentOnly);
            /* RegisterRecipe(new SyntheticBlockOnly); */
            class Noise { void Run() {
                string text = "RegisterRecipe(new SyntheticStringOnly); // not a comment";
                string escaped = "quote: \" /* still text */";
            } };
        ''')
        report = self.audit()
        rows = self.rows(report)
        self.assertNotIn("SyntheticStringOnly", rows)
        self.assertEqual(rows["SyntheticCommentOnly"]["source_status"], "disabled")
        self.assertEqual(rows["SyntheticBlockOnly"]["source_status"], "disabled")
        self.assertEqual(report["coverage"]["source_registration_calls"], 2)
        self.assertEqual(report["coverage"]["disabled_registration_calls"], 3)
        self.assertEqual(report["coverage"]["unresolved_registration_calls"], 0)

    def test_literal_inputs_are_source_facts_not_executed_or_inherited_outputs(self):
        report = self.audit()
        row = self.rows(report)["SyntheticParent"]
        facts = row["literal_references"]
        self.assertEqual([(fact["call"], fact["slot"], fact["item"]) for fact in facts], [
            ("InsertIngredient", 0, "SyntheticCloth"),
            ("InsertIngredientEx", 1, "SyntheticKnife"),
            ("AddResult", None, "SyntheticStrip"),
        ])
        self.assertTrue(all(fact["method"] == "Init" for fact in facts))
        self.assertEqual(self.rows(report)["SyntheticChild"]["literal_references"], [])
        self.assertEqual(report["item_literals"], ["SyntheticCloth", "SyntheticKnife", "SyntheticStrip"])
        self.assertFalse(row["semantics_resolved"])

    def test_custom_and_inherited_methods_remain_unresolved_with_locations(self):
        row = self.rows(self.audit())["SyntheticChild"]
        self.assertEqual({method["name"] for method in row["methods"]}, {"CanDo", "Do"})
        self.assertTrue(all(method["sha256"] and method["source"] for method in row["methods"]))
        self.assertIn("custom_method_semantics", {issue["code"] for issue in row["unresolved"]})
        self.assertIn("inherited_semantics", {issue["code"] for issue in row["unresolved"]})
        self.assertFalse(row["semantics_resolved"])

    def test_dynamic_literal_arguments_and_registration_are_not_guessed(self):
        self.write("Dynamic.c", '''class SyntheticDynamic extends RecipeBase {
            override void Init() {
                InsertIngredient(ChooseSlot(), "SyntheticMaybe");
                AddResult("Synthetic" + PickSuffix());
            }
        };
        class DynamicRegistry { void Run() { RegisterRecipe(BuildRecipe()); } };''')
        report = self.audit()
        row = self.rows(report)["SyntheticDynamic"]
        self.assertEqual(row["literal_references"], [])
        self.assertIn("dynamic_item_reference", {issue["code"] for issue in row["unresolved"]})
        self.assertEqual(report["coverage"]["unresolved_registration_calls"], 1)
        self.assertNotIn("SyntheticMaybe", report["item_literals"])
        self.assertTrue(any(row["class"] is None and row["unresolved"] for row in report["registrations"]))

    def test_conditional_registration_and_declaration_are_not_claimed_active(self):
        self.write("Conditional.c", '''#ifdef SYNTHETIC_BUILD
        class SyntheticConditional extends RecipeBase {};
        class ConditionalRegistry { void Run() {
            RegisterRecipe(new SyntheticConditional);
        } };
        #else
        // RegisterRecipe(new SyntheticConditional);
        #endif
        ''')
        report = self.audit()
        row = self.rows(report)["SyntheticConditional"]
        self.assertEqual(row["source_status"], "conditional")
        self.assertTrue(row["definitions"][0]["conditions"])
        self.assertEqual(report["coverage"]["conditional_registration_calls"], 1)
        self.assertEqual(report["coverage"]["source_registered_names"], 2)

    def test_preprocessor_include_is_unresolved_and_never_followed(self):
        outside = self.workspace / "outside.c"
        outside.write_text("class DoNotRead extends RecipeBase {};", encoding="utf-8")
        self.write("Include.c", '#include "../outside.c"\n')
        report = self.audit()
        self.assertIn("preprocessor_not_evaluated", self.codes(report))
        self.assertNotIn("DoNotRead", self.rows(report))
        self.assertFalse(report["coverage"]["preprocessor_resolved"])

    def test_unregister_duplicates_and_missing_declarations_are_explicit(self):
        self.write("Mutations.c", '''class MutationRegistry { void Run() {
            RegisterRecipe(new SyntheticParent);
            UnregisterRecipe("SyntheticParent");
            RegisterRecipe(new SyntheticMissing);
        } };''')
        report = self.audit()
        row = self.rows(report)["SyntheticParent"]
        self.assertEqual(row["source_status"], "unresolved")
        self.assertEqual(len(row["registrations"]), 2)
        self.assertEqual(len(row["unregistrations"]), 1)
        self.assertIn("duplicate_registration", {issue["code"] for issue in row["unresolved"]})
        missing = self.rows(report)["SyntheticMissing"]
        self.assertEqual(missing["declaration_status"], "missing")
        self.assertFalse(missing["semantics_resolved"])

    def test_modded_and_ambiguous_recipe_declarations_are_not_silently_merged(self):
        self.write("Overlay.c", '''modded class SyntheticParent { override void Init() { super.Init(); } };
            class SyntheticChild extends RecipeBase {};''')
        rows = self.rows(self.audit())
        self.assertEqual(len(rows["SyntheticParent"]["definitions"]), 2)
        self.assertIn("modded_definition", {issue["code"] for issue in rows["SyntheticParent"]["unresolved"]})
        self.assertIn("ambiguous_definition", {issue["code"] for issue in rows["SyntheticChild"]["unresolved"]})

    def test_unregistered_conditional_duplicates_retain_both_declarations(self):
        # Independent P2 reproduction: no registration can rescue this name.
        source = ("class RecipeBase {};\n#ifdef X\nclass Twin extends RecipeBase {};\n"
                  "#else\nclass Twin extends RecipeBase {};\n#endif\n")
        definitions, calls, _ = self.module._parse(source, "synthetic.c", [0])
        rows = self.rows({"recipes": self.module._reconcile(definitions, calls)})
        self.assertIn("Twin", rows)
        twin = rows["Twin"]
        self.assertEqual(len(twin["definitions"]), 2)
        self.assertTrue(all(row["conditions"] for row in twin["definitions"]))
        self.assertEqual(twin["source_status"], "unregistered")
        self.assertFalse(twin["recipe_ancestry_resolved"])
        self.assertFalse(twin["semantics_resolved"])
        self.assertIn("unresolved_ancestry", {issue["code"] for issue in twin["unresolved"]})
        self.assertIn("ambiguous_definition", {issue["code"] for issue in twin["unresolved"]})

    def test_unregistered_descendants_of_ambiguous_recipe_remain_in_coverage(self):
        self.write("Ambiguous.c", '''#ifdef X
            class SyntheticTwin extends RecipeBase {};
            #else
            class SyntheticTwin extends RecipeBase {};
            #endif
            class SyntheticDescendant extends SyntheticTwin {};
            class SyntheticGrandchild extends SyntheticDescendant {};
        ''')
        report = self.audit()
        rows = self.rows(report)
        for name in ("SyntheticTwin", "SyntheticDescendant", "SyntheticGrandchild"):
            with self.subTest(name=name):
                self.assertIn(name, rows)
                self.assertEqual(rows[name]["source_status"], "unregistered")
                self.assertFalse(rows[name]["recipe_ancestry_resolved"])
                self.assertIn("unresolved_ancestry", {issue["code"] for issue in rows[name]["unresolved"]})
        self.assertEqual(len(rows["SyntheticTwin"]["definitions"]), 2)
        self.assertEqual(report["coverage"]["declared_recipe_classes"], 4)
        self.assertEqual(report["coverage"]["declared_recipe_candidate_classes"], 7)
        self.assertEqual(report["coverage"]["unresolved_ancestry_classes"], 3)

    def test_possible_recipe_edges_retain_branching_cycles_but_not_unrelated_duplicates(self):
        self.write("Branches.c", '''class SyntheticBranch extends RecipeBase {};
            class SyntheticBranch extends SyntheticCycle {};
            class SyntheticCycle extends SyntheticBranch {};
            class SyntheticLeaf extends SyntheticCycle {};
            class SyntheticUnrelated {};
            class SyntheticUnrelated {};
        ''')
        rows = self.rows(self.audit())
        for name in ("SyntheticBranch", "SyntheticCycle", "SyntheticLeaf"):
            with self.subTest(name=name):
                self.assertIn(name, rows)
                self.assertFalse(rows[name]["recipe_ancestry_resolved"])
        self.assertNotIn("SyntheticUnrelated", rows)

    def test_cycle_or_missing_parent_cannot_hang_or_resolve_semantics(self):
        self.write("BrokenAncestry.c", '''class SyntheticCycleA extends SyntheticCycleB {};
            class SyntheticCycleB extends SyntheticCycleA {};
            class SyntheticOrphan extends SyntheticAbsent {};
            class CycleRegistry { void Run() {
                RegisterRecipe(new SyntheticCycleA);
                RegisterRecipe(new SyntheticOrphan);
            } };''')
        rows = self.rows(self.audit())
        for name in ("SyntheticCycleA", "SyntheticOrphan"):
            with self.subTest(name=name):
                self.assertIn("unresolved_ancestry", {issue["code"] for issue in rows[name]["unresolved"]})
                self.assertFalse(rows[name]["semantics_resolved"])

    def test_hashes_are_exact_deterministic_and_portable(self):
        report = self.audit()
        self.assertEqual(report, self.audit())
        relocated = self.workspace / "relocated"
        self.fs.copy(self.tree, relocated)
        self.assertEqual(report, self.module.audit_tree(relocated))
        self.assertNotIn(str(self.workspace), json.dumps(report))
        for source in report["sources"]:
            content = (self.tree / source["path"]).read_bytes()
            self.assertEqual(source["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(source["bytes"], len(content))
        original = report["manifest_sha256"]
        with (self.tree / "RecipeBase.c").open("a", encoding="utf-8") as handle:
            handle.write("// synthetic provenance change\n")
        self.assertNotEqual(original, self.audit()["manifest_sha256"])

    def test_manifest_pin_matches_and_mismatch_fails_without_leaking_paths(self):
        digest = self.audit()["manifest_sha256"]
        self.assertTrue(self.audit(expected_manifest_sha256=digest)["valid"])
        report = self.audit(expected_manifest_sha256="0" * 64)
        self.assertFalse(report["valid"])
        self.assertIn("manifest_mismatch", self.codes(report))
        self.assertFalse(report["coverage"]["source_census_complete"])
        self.assertIn("invalid_manifest_pin", self.codes(self.audit(expected_manifest_sha256="not-a-hash")))

    def test_all_sources_including_unrelated_code_are_hashed_and_parse_checked(self):
        self.write("Unrelated.c", "class SyntheticUnrelated {};")
        self.write("ignored.txt", "not a script")
        report = self.audit()
        self.assertEqual(report["coverage"]["source_files"], 4)
        self.write("Unrelated.c", "class SyntheticUnrelated { /* unfinished")
        report = self.audit()
        self.assertFalse(report["inputs_complete"])
        self.assertFalse(report["valid"])
        self.assertIsNone(report["manifest_sha256"])
        self.assertIn("invalid_source", self.codes(report))

    def test_invalid_utf8_unbalanced_delimiters_strings_and_directives_fail_closed(self):
        for source in (b"\xff", "class Broken {", 'class Broken { string x = "oops; };',
                       "class Broken { void X() { a(]; } };", "#endif\n", "#ifdef X\n"):
            with self.subTest(source=source):
                self.write("Invalid.c", source)
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertFalse(report["inputs_complete"])
                self.assertFalse(report["coverage"]["source_census_complete"])

    def test_resource_limits_fail_closed_instead_of_truncating_success(self):
        for constant, value in (("MAX_FILE_BYTES", 32), ("MAX_TOTAL_BYTES", 64),
                                ("MAX_SOURCE_FILES", 1), ("MAX_TREE_ENTRIES", 2),
                                ("MAX_PATH_DEPTH", 1), ("MAX_PATH_CHARS", 8),
                                ("MAX_TOKENS", 10), ("MAX_NESTING", 1),
                                ("MAX_CLASSES", 1), ("MAX_ANCESTRY", 1)):
            with self.subTest(constant=constant), patch.object(self.module, constant, value):
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertFalse(report["inputs_complete"])
                self.assertIn("resource_limit", self.codes(report))
                self.assertIsNone(report["manifest_sha256"])

    def test_symlink_files_directories_and_special_inputs_are_rejected(self):
        outside = self.workspace / "outside.c"
        outside.write_text("class SyntheticEscape extends RecipeBase {};", encoding="utf-8")
        for directory in (False, True):
            with self.subTest(directory=directory):
                link = self.tree / "link"
                try:
                    link.symlink_to(self.workspace if directory else outside, target_is_directory=directory)
                except (OSError, NotImplementedError):
                    self.skipTest("symlink creation unavailable")
                report = self.audit()
                self.assertFalse(report["valid"])
                self.assertIn("unsafe_source_path", self.codes(report))
                self.assertNotIn("SyntheticEscape", self.rows(report))
                link.unlink()
        if hasattr(os, "mkfifo"):
            fifo = self.tree / "pipe.c"
            self.fs.nodes[str(fifo)] = (stat.S_IFIFO | 0o644, b"")
            self.assertIn("unsafe_source_path", self.codes(self.audit()))

    def test_missing_file_root_and_empty_tree_return_json_failures(self):
        for path in (self.workspace / "absent", self.tree / "RecipeBase.c"):
            with self.subTest(path=path):
                report = self.module.audit_tree(path)
                self.assertFalse(report["valid"])
                self.assertIn("invalid_root", self.codes(report))
        empty = self.workspace / "empty"
        empty.mkdir()
        self.assertIn("no_sources", self.codes(self.module.audit_tree(empty)))

    def test_cli_is_stdout_only_deterministic_and_reports_pin_failure(self):
        first, second = self.cli(), self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        report = json.loads(first.stdout)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["evidence_layer"], "T0_source_only")
        self.assertIn("runtime", " ".join(report["limitations"]).lower())
        self.assertFalse(list(self.tree.rglob("__pycache__")))
        result = self.cli("--expect-manifest-sha256", "0" * 64)
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest_mismatch", self.codes(json.loads(result.stdout)))
        result = self.run_cli([])
        self.assertEqual(result.returncode, 2)
        self.assertIn("--root", result.stderr)


if __name__ == "__main__":
    unittest.main()
