"""Issue census adapters: pinned world targets and commit-derived CE treatment.

Uses existing observation hooks verbatim; adds no engine APIs or acceptance verdicts.
"""
from pathlib import Path
import subprocess

from tools.package import interior_points_gen, loot_boost, new_buildings
from tools.setup import ce_probe, interior_sampler as sampler, probe_runtime as runtime

# Issue #317 (gh issue view 317 --json body): explicit refusals/upper floors.
# All additional WRP wreck classes without a stock group are included dynamically.
ISSUES = {
    317: {
        "census": ("Land_Misc_Toilet_Mobile", "Land_CementWorks_MillA", "Land_Castle_Donjon",
                   "Land_Wreck_C130J_2", "Land_Office_Municipal1", "Land_Wreck_Harverster"),
        "treatment": ("Land_Mil_Tower_Small", "Land_Church2_1", "Land_Cementworks_Conveyorhall",
                      "Land_CementWorks_SiloBig1B", "Land_Office_Municipal1",
                      "Land_Wreck_Uaz", "Land_Wreck_Tractor", "Land_Wreck_Trailer_Closed"),
        "ungrouped_wrecks": True,
        "calibration": True,
    },
}
ADDONS = Path("/mnt/d/SteamLibrary/steamapps/common/DayZServer/addons")
REPO = Path(__file__).resolve().parents[2]


def world_placements(stock_pos, stock_classes, requested, *, include_wrecks=False):
    """Resolve config spelling and positions from the hash-pinned installed WRP.

    These are observation targets, never synthetic CE placement rows. Census
    missions retain stock XML; the hook resolves the actual world object there.
    """
    if runtime.sha256(stock_pos) != new_buildings.STOCK_POS_SHA256:
        raise ValueError("world census requires pinned stock placements")
    world, digest = new_buildings.read_world(ADDONS)
    validation = new_buildings.validate_world(world, stock_pos)
    if not validation["rows"] or validation["matched"] != validation["rows"] or validation["max_pos_m"] > .001:
        raise ValueError("pinned world does not reproduce stock placements")
    config = {name.casefold(): name for name in interior_points_gen.Assets(ADDONS).classes}
    stock = {name.casefold() for name in stock_classes}
    names = list(requested)
    if include_wrecks:
        names.extend(config[cls.casefold()] for cls, *_ in world
                     if cls.casefold() in config and "wreck" in cls.casefold() and cls.casefold() not in stock)
    names = sorted(set(names))
    # Require the requested canonical spelling, rather than silently guessing aliases.
    if any(config.get(name.casefold()) != name for name in names):
        raise ValueError("requested class missing or differs from installed config spelling")
    placements = {}
    wanted = set(names)
    for cls, _model, x, y, z, _matrix in world:
        name = config.get(cls.casefold())
        if name in wanted:
            placements.setdefault(name, []).append((x, y, z))
    return names, placements, {"wrp_sha256": digest, "stock_validation": validation,
                               "placement_source": "pinned-installed-wrp"}


def clean_commit():
    """Packaging code and committed data must come from one clean commit."""
    def git(*args):
        try:
            return subprocess.run(["git", "--no-optional-locks", "-C", str(REPO), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        except subprocess.CalledProcessError as error:
            raise ValueError("could not identify clean packaging commit") from error
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("treatment requires a clean committed checkout")
    return git("rev-parse", "HEAD")


def treatment_files(source):
    """Use the same loot_boost.plan and shipped overlay as bundle installation.

    Read only verified stock-backup mission inputs, never a live server profile.
    Stage all planned XML deltas: positions and type tags are required alongside
    the prototype for the added groups and floor policy to work.
    """
    commit = clean_commit()
    result = loot_boost.plan(source["mission"], points=loot_boost.shipped_points())
    if not result["counts"]["new_buildings"].get("applied"):
        raise ValueError("packaging did not apply the new-buildings layer")
    files = {name: after for name, _before, after in result["files"]}
    if "mapgroupproto.xml" not in files or "mapgrouppos.xml" not in files:
        raise ValueError("treatment requires packaged prototype and placement deltas")
    runtime.check_unchanged(source)
    if clean_commit() != commit:
        raise ValueError("checkout changed while generating treatment")
    return files, {"commit": commit, "generator": "tools.package.loot_boost.plan",
                   "files": {name: runtime.sha256(data) for name, data in sorted(files.items())},
                   "runtime_acceptance": "pending"}


def stage_observation(destination, targets, *, wait_minutes, native, evidence,
                      run=None, replacements=None, treatment=None):
    """Shared runtime admission/launcher checks with the existing hooks unchanged."""
    context = runtime.begin(runtime.DEFAULT_SOURCE_RUNTIME, destination, parent=runtime.WSL_PARENT,
                            battleye_sha256=runtime.BATTLEYE_SHA256,
                            hold=("mapgroupproto.xml",) if run is not None else ())
    native_types = runtime.native_type_names(native) if native else frozenset()
    if run is not None:
        targets = sampler._checked_run(run)
        names = {target["class"] for target in targets}
        calibration = [name for name, role in sampler.SAMPLE_CLASSES if role == "calibration" and name in names]
        frame = sampler.stock_frame_points(context["source"]["held"]["mapgroupproto.xml"], calibration)
        points = [(name, *point) for name in calibration for point in frame[name]]
        hook = sampler.render_hook(targets, native_run_id=run["native_run_id"], frame_points=points)
        kind, profile, plan_name = "interior-sampler", sampler.PROFILE_DIRECTORY, sampler.PLAN_NAME
        problems = sampler.lint_sampler_hook(hook.decode("ascii"), native_types=native_types)
    else:
        hook = ce_probe.render_hook(targets)
        kind, profile, plan_name = "ce-probe", "HCCEProbe", ce_probe.PLAN_NAME
        problems = runtime.lint_hook(hook.decode("ascii"), native_types=native_types)
    if problems:
        raise ValueError("generated hook violates native compile rules")
    built = runtime.build_runtime(context, hook, purpose="ce-probe", replacements=replacements)
    plan = runtime.plan_header(kind, None, after={"variant": "sampler" if run else "treatment"})
    plan.update(runtime.plan_runtime_fields(context, built))
    plan.update({"probe": {"wait_minutes": wait_minutes, "target_count": len(targets),
                           "hook_sha256": runtime.sha256(hook), "hook_bytes": len(hook),
                           "census_relative_path": f"profiles/{profile}/census.json",
                           "sentinel_relative_path": f"profiles/{profile}/complete.txt"},
                 "targets": targets, "target_classes": sorted({t["class"] for t in targets}),
                 "world_evidence": evidence, "treatment": treatment,
                 "mission_files": built["mission_files"], "staged_files": built["staged"]})
    if run is not None:
        plan["probe"]["native_run_id"] = run["native_run_id"]
        plan["batch"] = {"index": run["index"], "classes": len(run["classes"])}
    return runtime.write_plan(destination, plan_name, plan)
