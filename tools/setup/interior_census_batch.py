"""Prepare issue #227's five disposable native census runtimes; never launch processes.

Run from a session with write access to /mnt/d/HollowCountryLocal. All destinations
must be fresh. A failed/partial preparation is retained for inspection, never overwritten.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.package import interior_templates as templates
from tools.setup import interior_sampler as sampler
from tools.setup import probe_runtime as runtime


def prepare(wait_minutes=30):
    if not 5 <= wait_minutes <= 120:
        raise ValueError("wait minutes must be 5..120")
    parent = runtime.WSL_PARENT
    if os.statvfs(parent).f_flag & os.ST_RDONLY:
        raise OSError(errno.EROFS, "Read-only file system")
    batch = parent / "interior-batch-227"
    destinations = [parent / ("interior-sampler-227-" + str(i)) for i in range(5)]
    if any(p.exists() or p.is_symlink() for p in [batch] + destinations):
        raise ValueError("all issue 227 batch and runtime destinations must be fresh")
    # Use the existing launcher's pinned install. Never modify the friend runtime.
    executable = Path("/mnt/d/SteamLibrary/steamapps/common/DayZServer/DayZServer_x64.exe")
    if hashlib.sha256(executable.read_bytes()).hexdigest() != runtime.SERVER_EXE_SHA256:
        raise ValueError("the launcher's pinned server executable changed")
    source = runtime.verify_source(Path(runtime.DEFAULT_SOURCE_RUNTIME), runtime.BATTLEYE_SHA256,
                                   hold=("mapgroupproto.xml", "mapgrouppos.xml"))
    classes = sorted(templates.parse_proto(source["held"]["mapgroupproto.xml"]))
    placements = sampler.placements_tool.parse_placements(source["held"]["mapgrouppos.xml"], wanted=set(classes))
    plan = sampler.plan_batches(classes, placements, run_size=64, per_class=1)
    if [len(r["targets"]) for r in plan["runs"]] != [64, 64, 64, 64, 7]:
        raise ValueError("stock inputs changed: expected issue 227's five runs / 263 targets")
    # Source/destination preflights perform reads only, before the first mkdir.
    for destination in destinations:
        runtime.windows_runtime_root(destination)
    native = Path.home() / ".cache/hollow-country/native-scripts/scripts-1.30.164289"
    if not (native / "3_Game").is_dir():
        raise ValueError("pinned native scripts cache required for hook lint")
    batch.mkdir()
    with (batch / "classes.json").open("x", encoding="ascii") as handle:
        json.dump(classes, handle, indent=2)
        handle.write("\n")
    sampler.write_batch_plan(plan, batch)
    launcher = Path(__file__).with_name("Start-CEProbeServer.ps1").read_bytes()
    with (batch / "Start-CEProbeServer.ps1").open("xb") as handle:
        handle.write(launcher)
    for run, destination in zip(plan["runs"], destinations):
        staged = sampler.stage(runtime.DEFAULT_SOURCE_RUNTIME, destination, run=run,
                               wait_minutes=wait_minutes, native_scripts=native)
        print("[HC Interiors] census staged run=%d targets=%d native_run_id=%s runtime=PENDING"
              % (run["index"], staged["probe"]["target_count"], run["native_run_id"]))
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-minutes", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        prepare(args.wait_minutes)
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
