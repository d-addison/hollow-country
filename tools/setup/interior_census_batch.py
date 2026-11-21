"""Prepare disposable native census runtimes; never launch processes.

Default/--issue 227 preserves the original five runs. --issue 317 includes the
refused/ungrouped WRP buildings and a commit-derived packaged CE treatment.
--classes NAME [NAME ...] --tag TAG stages an explicit native class census.

Run from a session with write access to /mnt/d/HollowCountryLocal. All destinations
must be fresh. A failed/partial preparation is retained for inspection, never overwritten.
"""
import argparse
import errno
import json
import os
import re
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import interior_templates as templates
from tools.setup import interior_sampler as sampler
from tools.setup import probe_runtime as runtime
from tools.setup import interior_census_support as support


LEGACY_RUN_TARGET_COUNTS = (64, 64, 64, 64, 7)


def prepare(wait_minutes=30, *, issue=None, classes=None, tag=None, run_size=64, treatment_per_class=3):
    if not 5 <= wait_minutes <= 120:
        raise ValueError("wait minutes must be 5..120")
    if type(treatment_per_class) is not int or not 1 <= treatment_per_class <= sampler.MAX_PER_CLASS:
        raise ValueError(f"treatment per class must be 1..{sampler.MAX_PER_CLASS}")
    if issue is not None and classes is not None:
        raise ValueError("choose an issue or explicit classes")
    issue = 227 if issue is None and classes is None else issue
    if issue not in (None, 227, *support.ISSUES):
        raise ValueError("unknown issue preset")
    if classes is not None:
        classes = sampler.parse_class_list(json.dumps(classes).encode("ascii"))
    if isinstance(run_size, bool) or not 1 <= run_size <= sampler.MAX_TARGETS:
        raise ValueError("run size must be 1..64")
    if issue == 227 and run_size != 64:
        raise ValueError("issue 227 keeps its original run size")
    tag = str(issue) if tag is None and issue is not None else tag
    if not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", tag):
        raise ValueError("a plain tag of at most 32 characters is required")
    parent = runtime.WSL_PARENT
    if os.statvfs(parent).f_flag & os.ST_RDONLY:
        raise OSError(errno.EROFS, "Read-only file system")
    batch = parent / ("interior-batch-" + tag)
    if batch.exists() or batch.is_symlink():
        raise ValueError("all batch and runtime destinations must be fresh")
    # Use the existing launcher's pinned install. Never modify the friend runtime.
    executable = Path("/mnt/d/SteamLibrary/steamapps/common/DayZServer/DayZServer_x64.exe")
    if runtime._hash_file(executable)[0] != runtime.SERVER_EXE_SHA256:
        raise ValueError("the launcher's pinned server executable changed")
    source = runtime.verify_source(Path(runtime.DEFAULT_SOURCE_RUNTIME), runtime.BATTLEYE_SHA256,
                                   hold=("mapgroupproto.xml", "mapgrouppos.xml"))
    stock_classes = sorted(templates.parse_proto(source["held"]["mapgroupproto.xml"]))
    evidence, treatment, replacements = {}, None, None
    if issue == 227:
        classes = stock_classes
        placements = sampler.placements_tool.parse_placements(source["held"]["mapgrouppos.xml"], wanted=set(classes))
    else:
        preset = support.ISSUES.get(issue, {})
        requested = list(preset.get("census", classes or ()))
        if preset.get("calibration"):
            requested.extend(name for name, role in sampler.SAMPLE_CLASSES if role == "calibration")
        treatment_classes = support.treatment_classes() if preset.get("treatment") else ()
        all_requested = sorted(set(requested + list(treatment_classes)))
        names, placements, evidence = support.world_placements(
            source["held"]["mapgrouppos.xml"], stock_classes, all_requested,
            include_wrecks=preset.get("ungrouped_wrecks", False))
        classes = names
    plan = sampler.plan_batches(classes, placements, run_size=run_size, per_class=1)
    if issue == 227 and [len(r["targets"]) for r in plan["runs"]] != list(LEGACY_RUN_TARGET_COUNTS):
        raise ValueError("stock inputs changed: expected issue 227's five runs / 263 targets")
    if not plan["runs"] or (issue != 227 and plan["unplaced"]):
        raise ValueError("requested census classes missing from admitted placements")
    destinations = [parent / ("interior-sampler-" + tag + "-" + str(r["index"])) for r in plan["runs"]]
    treatment_destination = parent / ("ce-probe-" + tag + "-treatment") if issue in support.ISSUES else None
    all_destinations = destinations + ([treatment_destination] if treatment_destination else [])
    if any(p.exists() or p.is_symlink() for p in all_destinations):
        raise ValueError("all batch and runtime destinations must be fresh")
    # Source/destination preflights perform reads only, before the first mkdir.
    for destination in all_destinations:
        runtime.windows_runtime_root(destination)
    native = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
    if not (native / "3_Game").is_dir():
        raise ValueError("pinned native scripts cache required for hook lint")
    if treatment_destination:
        replacements, treatment = support.treatment_files(source)
        treatment_positions = sampler.placements_tool.parse_placements(replacements["mapgrouppos.xml"])
        proto_classes = templates.parse_proto(replacements["mapgroupproto.xml"])
        if any(name not in proto_classes or not treatment_positions.get(name) for name in treatment_classes):
            raise ValueError("packaged treatment lacks requested groups or placements")
        targets, sampling = support.treatment_targets(treatment_positions, treatment_classes, treatment_per_class)
        treatment["sampling"] = sampling
    batch.mkdir()
    with (batch / "classes.json").open("x", encoding="ascii") as handle:
        json.dump(classes, handle, indent=2)
        handle.write("\n")
    sampler.write_batch_plan(plan, batch)
    launcher = Path(__file__).with_name("Start-CEProbeServer.ps1").read_bytes()
    with (batch / "Start-CEProbeServer.ps1").open("xb") as handle:
        handle.write(launcher)
    for run, destination in zip(plan["runs"], destinations):
        if issue == 227:
            staged = sampler.stage(runtime.DEFAULT_SOURCE_RUNTIME, destination, run=run,
                                   wait_minutes=wait_minutes, native_scripts=native)
        else:
            staged = support.stage_observation(destination, run["targets"], run=run,
                                               wait_minutes=wait_minutes, native=native, evidence=evidence)
        print("[HC Interiors] census staged run=%d targets=%d native_run_id=%s runtime=PENDING"
              % (run["index"], staged["probe"]["target_count"], run["native_run_id"]))
    launches = [("interior-sampler", destination) for destination in destinations]
    if treatment_destination:
        support.stage_observation(treatment_destination, targets, wait_minutes=wait_minutes,
                                  native=native, evidence=evidence, replacements=replacements, treatment=treatment)
        launches.append(("ce-probe", treatment_destination))
        print("[HC Interiors] treatment staged targets=%d commit=%s runtime=PENDING" % (len(targets), treatment["commit"]))
    if issue != 227:
        receipt = {"issue": issue, "tag": tag, "world": evidence, "treatment": treatment}
        with (batch / "evidence.json").open("x", encoding="ascii") as handle:
            json.dump(receipt, handle, indent=2)
            handle.write("\n")
    # One lead command launches the existing pinned launcher sequentially; no process here.
    commands = ["#requires -Version 5.1", "$ErrorActionPreference = 'Stop'",
                "$launcher = Join-Path $PSScriptRoot 'Start-CEProbeServer.ps1'"]
    for kind, destination in launches:
        root = runtime.windows_runtime_root(destination)
        commands.extend([f"$result = @(& $launcher -Kind '{kind}' -Runtime '{root}')",
                         "$result | Write-Output",
                         "if (-not ($result -match '^Outcome: sentinel-seen[.]')) { throw 'Native observation incomplete; inspect logs.' }"])
    with (batch / "Run-Census.ps1").open("x", encoding="ascii", newline="\r\n") as handle:
        handle.write("\n".join(commands) + "\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-minutes", type=int, default=30)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--issue", type=int, choices=(227, *support.ISSUES))
    selection.add_argument("--classes", nargs="+", help="explicit canonical config class names; requires --tag")
    parser.add_argument("--tag", help="fresh destination suffix; defaults to issue number")
    parser.add_argument("--run-size", type=int, default=64, help="at most 64 targets per native run")
    parser.add_argument("--treatment-per-class", type=int, default=3,
                        help=f"treatment placements per class (1..{sampler.MAX_PER_CLASS}; default 3); "
                             "use all available when fewer exist; refuse above the CE probe target cap")
    args = parser.parse_args(argv)
    try:
        prepare(args.wait_minutes, issue=args.issue, classes=args.classes, tag=args.tag, run_size=args.run_size,
                treatment_per_class=args.treatment_per_class)
    except support.TreatmentCapacityError as error:
        print(f"interior_census_batch: {error}. No process was launched.", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        # Do not include operator home paths or source configuration in errors.
        reason = "read-only host mount" if isinstance(error, OSError) and error.errno == errno.EROFS else type(error).__name__
        print("interior_census_batch: preparation refused (%s); inspect destination freshness, mount writability, "
              "pinned executable, stock runtime and native cache. No process was launched."
              % reason, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
