"""Measured-pack coverage report for the interior template pack (audit #199 / #197).

    python3 tools/package/interiors_profile.py coverage --proto mapgroupproto.xml --pos mapgrouppos.xml \
        [--census census.json ...] [--census-dir RUN_DIR ...] [--batch-plan batch-plan.json] [--json]

Unmeasured rooms retain a native clearance queue; the builder can admit search-only defaults at vanilla
CE points using native House bounds. This report states, from the stock XML and the census files
passed in, exactly how much of the stock denominator is measured, why each census file was rejected, and how
many native sampler runs (at most 64 targets each, the existing tools/setup/interior_sampler.py plan) are
still needed. It reuses the builder's own census admission (interior_templates.load_census), so it cannot
disagree with `templates build`. It reads inputs only and writes nothing. It never shows how DayZ lays out,
renders or spawns an interior; runtime acceptance of every interior stays pending.
"""
import json
from pathlib import Path
import sys

try:
    from tools.package import interior_templates as tpl
    from tools.setup import interior_sampler as sampler
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tools.package import interior_templates as tpl
    from tools.setup import interior_sampler as sampler

STATE_PENDING = "pending-measurement"
STATE_PARTIAL = "partial-pending-acceptance"
STATE_MEASURED = "measured-pending-acceptance"
# (substring of the builder's refusal, reason code), first match wins.
REASONS = (("door_phase_contract", "door_phase_contract"),
           ("native_run_id", "native_run_id"),
           ("incomplete", "incomplete"),
           ("share one native_run_id", "duplicate_run"))


def _label(value):
    return Path(str(value)).name or "census"


def _reason(error):
    text = str(error)
    for needle, code in REASONS:
        if needle in text:
            return code
    if isinstance(error, tpl.TemplateError) or isinstance(error, (KeyError, TypeError)):
        return "invalid"
    return "unreadable"


def classify_census(label, data):
    """Admit or reject one census file by the builder's own rules; never raises on bad input."""
    verdict = {"label": _label(label), "accepted": False, "reason": "", "run": "", "measured": []}
    try:
        loaded = tpl.load_census(data)
    except ValueError as error:  # TemplateError and json errors are ValueError subclasses
        verdict["reason"] = _reason(error)
        return verdict
    except (KeyError, TypeError, AttributeError) as error:
        verdict["reason"] = _reason(error)
        return verdict
    document = loaded["doc"]
    if document.get("Synthetic") is True:
        found = {row["class"] for row in document["placements"] if row.get("found") is True}
    else:
        found = {row["class"] for row in loaded["houses"]}
    verdict.update(accepted=True, run=loaded["run"], measured=sorted(found & set(loaded["classes"])))
    return verdict


def census_inputs(paths=(), directories=()):
    """Discover sampler layouts once; directory inputs require the completion sentinel.

    Preserve the original bytes/run ids for the builder rather than inventing a combined
    native run. Labels contain runtime leaf names only, never operator profile paths.
    Explicit --census retains its historical admission rules.
    """
    candidates = {}
    for path in paths:
        path = Path(path)
        candidates.setdefault(path.resolve(), [path, False])
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            raise ValueError("census directory not found: " + directory.name)
        for path in sampler._census_files(directory):
            key = path.resolve()
            candidates.setdefault(key, [path, True])[1] = True
    if len(candidates) > sampler.MAX_CENSUS_FILES:
        raise ValueError("too many census files")
    inputs, rejected = [], []
    for path, needs_sentinel in candidates.values():
        root = path.parent
        if root.name == sampler.PROFILE_DIRECTORY:
            root = root.parent.parent if root.parent.name == "profiles" else root.parent
        label = root.name + "_" + path.name
        if needs_sentinel and not (path.parent / sampler.SENTINEL_NAME).is_file():
            rejected.append({"label": label, "reason": "no_sentinel"})
            continue
        try:
            data = tpl._read(path, tpl.pts.MAX_CENSUS_BYTES)
        except (ValueError, OSError):
            rejected.append({"label": label, "reason": "unreadable"})
            continue
        inputs.append((label, data))
    return inputs, rejected


def batch_progress(path, accepted):
    """Match admitted native ids to validated deterministic batch runs."""
    document = json.loads(tpl._read(path, sampler.MAX_BATCH_PLAN_BYTES))
    if not isinstance(document, dict) or document.get("kind") != sampler.BATCH_PLAN_KIND:
        raise ValueError("not an interior sampler batch plan")
    runs = document.get("runs")
    if not isinstance(runs, list) or len(runs) > sampler.MAX_BATCH_CLASSES:
        raise ValueError("invalid batch plan runs")
    indices, ids, done, missing = set(), set(), [], []
    admitted = {row["run"] for row in accepted}
    for run in runs:
        sampler._checked_run(run)
        index, run_id = run["index"], run["native_run_id"]
        if index in indices or run_id in ids:
            raise ValueError("duplicate batch run index or native_run_id")
        indices.add(index)
        ids.add(run_id)
        (done if run_id in admitted else missing).append(index)
    return {"runs": len(runs), "done": sorted(done), "missing": sorted(missing),
            "unplanned": sorted(admitted - ids)}


def coverage_inputs(proto, pos, paths=(), directories=(), batch_plan=None):
    """Shared admission for coverage and templates build; return report and accepted bytes."""
    inputs, rejected = census_inputs(paths, directories)
    report = coverage(proto, pos, inputs)
    report["rejected"].extend(rejected)
    report["census_rejected"] = len(report["rejected"])
    # coverage() admits in input order, including cross-run House consistency.
    admitted = {row["run"] for row in report["accepted"]}
    selected, seen = [], set()
    for label, data in inputs:
        verdict = classify_census(label, data)
        if verdict["accepted"] and verdict["run"] in admitted and verdict["run"] not in seen:
            selected.append(data)
            seen.add(verdict["run"])
    if batch_plan is not None:
        report["batch_plan"] = batch_progress(batch_plan, report["accepted"])
    return report, selected


def _stock_positions(pos_bytes):
    placed = {}
    for name, position, _yaw in tpl.parse_pos(pos_bytes):
        placed.setdefault(name, []).append(position)
    return placed


def coverage(proto_bytes, pos_bytes, censuses, per_class=1, run_size=sampler.MAX_TARGETS):
    """Coverage of the stock denominator by the qualifying censuses; ``censuses`` is [(label, bytes)]."""
    stock = sorted(tpl.parse_proto(proto_bytes))
    original_rows = tpl.parse_pos(pos_bytes)
    joined_rows, aliases = tpl.reconcile_positions(tpl.parse_proto(proto_bytes), original_rows)
    placed = {}
    for name, position, _yaw in joined_rows:
        placed.setdefault(name, []).append(position)
    exact_placed = set(stock) & {name for name, _p, _y in original_rows}
    queue = [name for name in stock if placed.get(name)]
    unplaced = [name for name in stock if not placed.get(name)]
    accepted, rejected, runs, measured = [], [], set(), set()
    admitted_bytes = []
    for label, data in censuses:
        verdict = classify_census(label, data)
        if verdict["accepted"] and verdict["run"] in runs:
            verdict.update(accepted=False, reason="duplicate_run")
        if verdict["accepted"]:
            try:
                tpl.load_censuses(admitted_bytes + [data], proto_bytes)
            except (ValueError, KeyError, TypeError, AttributeError):
                verdict.update(accepted=False, reason="conflicting_house_config")
        if verdict["accepted"]:
            admitted_bytes.append(data)
            runs.add(verdict["run"])
            measured.update(verdict["measured"])
            accepted.append(verdict)
        else:
            rejected.append(verdict)
    measured_stock = sorted(measured & set(stock))
    plan = {"runs": []}
    todo = [name for name in queue if name not in measured]
    if todo:
        plan = sampler.plan_batches(queue, placed, per_class=per_class, run_size=run_size, measured=measured_stock)
    state = STATE_PENDING
    if measured_stock:
        state = STATE_PARTIAL
    if queue and not todo:
        state = STATE_MEASURED
    return {"stock_classes": len(stock), "placed_classes": len(queue), "unplaced": unplaced,
            "denominator_kind": "CE prototype/placement metadata; physical enterability unverified",
            "exact_placed_classes": len(exact_placed), "case_aliases": aliases,
            "census_accepted": len(accepted), "census_rejected": len(rejected),
            "accepted": [{"label": v["label"], "run": v["run"], "measured": len(v["measured"])} for v in accepted],
            "rejected": [{"label": v["label"], "reason": v["reason"]} for v in rejected],
            "measured_classes": len(measured_stock), "unmeasured_classes": len(todo),
            "survey_runs_needed": len(plan["runs"]), "run_size": run_size, "per_class": per_class,
            "state": state}


def lines(report):
    """Human lines; every one keeps the runtime acceptance wording."""
    out = ["[HC Interiors] coverage state=%s stock=%d placed=%d measured=%d unmeasured=%d survey_runs=%d "
           "census_accepted=%d census_rejected=%d runtime=PENDING"
           % (report["state"], report["stock_classes"], report["placed_classes"], report["measured_classes"],
              report["unmeasured_classes"], report["survey_runs_needed"], report["census_accepted"],
              report["census_rejected"])]
    if "batch_plan" in report:
        batch = report["batch_plan"]
        out.append("[HC Interiors] batch plan runs=%d done=%s missing=%s runtime=PENDING"
                   % (batch["runs"], json.dumps(batch["done"]), json.dumps(batch["missing"])))
        if batch["unplanned"]:
            out.append("accepted runs outside batch plan: " + ",".join(batch["unplanned"]))
    for row in report["rejected"]:
        out.append("rejected %s: %s" % (row["label"], row["reason"]))
    for row in report["accepted"]:
        out.append("accepted %s: run=%s measured=%d" % (row["label"], row["run"], row["measured"]))
    if report["unplaced"]:
        out.append("unplaced stock classes (not queued, no mapgrouppos row): %d" % len(report["unplaced"]))
    out.append("Stock metadata exact placed classes=%d case-folded=%d aliases=%d; physical enterability remains pending."
               % (report["exact_placed_classes"], report["placed_classes"], len(report["case_aliases"])))
    out.append("Unmeasured rooms retain clearance follow-up; CE-point search defaults are provisional. Queue sized with "
               "interior_sampler plan (runs of at most %d targets)." % report["run_size"])
    return out
