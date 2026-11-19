"""Measured-pack coverage report for the interior template pack (audit #199 / #197).

    python3 tools/package/interiors_profile.py coverage --proto mapgroupproto.xml --pos mapgrouppos.xml \
        [--census census.json ...] [--json]

Unmeasured rooms retain a native clearance queue; the builder can admit search-only defaults at vanilla
CE points using native House bounds. This report states, from the stock XML and the census files
passed in, exactly how much of the stock denominator is measured, why each census file was rejected, and how
many native sampler runs (at most 64 targets each, the existing tools/setup/interior_sampler.py plan) are
still needed. It reuses the builder's own census admission (interior_templates.load_census), so it cannot
disagree with `templates build`. It reads inputs only and writes nothing. It never shows how DayZ lays out,
renders or spawns an interior; runtime acceptance of every interior stays pending.
"""
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
    for label, data in censuses:
        verdict = classify_census(label, data)
        if verdict["accepted"] and verdict["run"] in runs:
            verdict.update(accepted=False, reason="duplicate_run")
        if verdict["accepted"]:
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
