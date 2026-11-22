"""Coverage, human-review and blocker report for one sealed run (spec 002 AV-T027).

The report is built from the sealed artifact store plus tests/catalog.json. It lists every
catalogue row (all original IDs and every extension), not only the runnable ones, each with
PASS/FAIL/BLOCKED/NOTRUN, one result per submethod (the row's modes) and an explicit
acceptance state. Rules that keep it honest:

- Nothing is promoted. Acceptance is always "not_accepted" here; an autotest store ranks below
  the owner one-client smoke and never proves multiplayer. Human review defaults to
  "not reviewed" and counts only when a decision cites an artifact of the sealed store by hash.
- A submethod passes only through a driver registered as qualified for that exact mode (QUALIFIED,
  empty today: no existing driver observes gameplay). A framework check that passed supports a
  row; it never passes a submethod and never hides an unsupported one.
- Every attempt of a covering task is listed in its chain; a failed retry stays visible even
  when a later attempt passed, and a failing latest attempt fails the row.
- Every BLOCKED item names a concrete next capability, task id or input, and its kind
  (access, implementation or human_review).
- Reconciliation is exact: catalogue ids, declared original ids, the original-ID constant and the
  reported ids must agree, with each missing or extra id an error; the original criterion text and
  its sources are traced per item.

Output is coverage.json plus a short coverage.md in the run's out dir, never in the repository.
Offline only; this module starts nothing.
"""
import hashlib
import json
from pathlib import Path
import re

from tools.testing import artifacts, automation, discovery
from tools.validate import evidence

REPORT_VERSION = 1
OUTCOMES = ("PASS", "FAIL", "BLOCKED", "NOTRUN")
MODES = ("measurement", "engine", "server", "client-pair", "human-judgment")
ACCEPTANCE_STATE = "not_accepted"
ACCEPTANCE_BASIS = ("autotest evidence is synthetic or zero-client; it ranks below the owner one-client "
                    "smoke and never proves multiplayer")
NOT_REVIEWED = "not reviewed"
REVIEW_DECISIONS = {"yes": "reviewed_yes", "no": "reviewed_no"}
BLOCKER_KINDS = ("access", "implementation", "human_review")
MAX_ATTEMPTS = 4096
MAX_REVIEWS = 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")

# Drivers qualified to observe a mode: driver id -> modes. Empty: no registered driver observes
# engine, server, client or measurement behaviour of a catalogue row; framework checks only support.
# "human-judgment" is never a driver mode, only a verified review decision.
QUALIFIED = {}

# capability -> (submethod it gates, blocker kind, concrete next step)
CAPABILITY_NEXT = {
    "pinned_inputs": ("measurement", "implementation", "AV-T001 pin every catalogue source with sha256"),
    "qualified_measurement": ("measurement", "implementation", "AV-T021 raw native telemetry and benchmark adapter"),
    "schema_validator": ("measurement", "implementation", "AV-T005 offline schema validator"),
    "secret_scan": ("measurement", "implementation", "AV-T005 offline secret scan"),
    "surveyed_geometry": ("measurement", "implementation", "AV-T012 map and build geometry survey adapter"),
    "qualified_map_adapter": ("measurement", "implementation", "AV-T012 map and build qualification"),
    "validated_policy_bounds": ("measurement", "human_review", "owner supplies validated policy bounds as input"),
    "native_ce_accounting": ("measurement", "implementation", "AV-T013 native CE coverage observations"),
    "native_inventory_ledger": ("measurement", "implementation", "AV-T014 native search and craft ledger"),
    "complete_recipe_audit": ("measurement", "implementation", "AV-T014 complete recipe audit"),
    "resource_conservation_oracle": ("measurement", "implementation", "AV-T014 material conservation oracle"),
    "separate_six_and_ninety_player_load": ("measurement", "implementation",
                                            "AV-T022 co-op-6 and public-90 load qualification"),
    "signed_package": ("server", "implementation", "AV-T007 isolated compile, sign and launch adapter"),
    "normal_server": ("server", "implementation", "AV-T007 isolated normal-server adapter"),
    "qualified_network_fault_driver": ("server", "implementation", "AV-T018 network fault adapter"),
    "qualified_scenario_driver": ("engine", "implementation", "AV-T008 diagnostic native probe and subcase adapter"),
    "native_state_capture": ("engine", "implementation", "AV-T008 native state capture"),
    "dayzdiag": ("engine", "implementation", "AV-T008 diagnostic native adapter"),
    "qualified_native_provider": ("engine", "implementation", "AV-T008 qualified native provider"),
    "qualified_production_horde_provider": ("engine", "implementation", "AV-T020 production horde provider capture"),
    "qualified_persistence_fault_driver": ("engine", "implementation", "AV-T010 reached-boundary fault schedules"),
    "complete_fresh_observer_coverage": ("engine", "implementation", "AV-T020 fresh observer fairness captures"),
    "licensed_authenticated_rendered_client": ("client-pair", "access",
                                               "AV-T015 licensed existing-account client provisioning"),
    "licensed_authenticated_rendered_client_pair": ("client-pair", "access",
                                                    "AV-T017 two licensed clients with distinct accounts"),
    "synchronized_client_capture": ("client-pair", "implementation", "AV-T017 synchronized two-client capture"),
    "paired_rendered_audio_capture": ("client-pair", "implementation", "AV-T019 rendered audio capture and review"),
    "criterion_reviewer": ("human-judgment", "human_review", "human review of the criterion against its artifacts"),
    "recorded_scope_decisions": ("human-judgment", "human_review", "owner records the scope decision for the row"),
    "rights_review": ("human-judgment", "human_review", "rights review by the owner"),
    "complete_feature_audit": ("human-judgment", "human_review", "AV-T028 independent complete feature audit"),
}
# When a mode has no missing capability but no qualified driver either.
MODE_NEXT = {
    "measurement": ("implementation", "AV-T021 register a qualified measurement driver"),
    "engine": ("implementation", "AV-T008 register a qualified native engine driver"),
    "server": ("implementation", "AV-T007 register a qualified server driver"),
    "client-pair": ("access", "AV-T015 provision licensed real clients and register a qualified client driver"),
    "human-judgment": ("human_review", "human review decision citing a sealed artifact"),
}
DEFERRED_NEXT = {
    "licensed_authenticated_rendered_client_pair": "AV-T017",
    "synchronized_client_capture": "AV-T017",
    "qualified_network_fault_driver": "AV-T018",
    "paired_rendered_audio_capture": "AV-T019",
    "separate_six_and_ninety_player_load": "AV-T022",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_store(root):
    """Manifest attempts, or None when the manifest cannot be read as strict JSON."""
    try:
        data = evidence._load_json(Path(root) / evidence.STORE_MANIFEST)
    except (OSError, ValueError, RuntimeError, RecursionError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("attempts"), list):
        return None
    return data


def _chains(manifest):
    """task id -> attempt chain as sealed, oldest first. Nothing is filtered or merged."""
    chains = {}
    for entry in manifest["attempts"] if manifest else []:
        if not isinstance(entry, dict) or not isinstance(entry.get("task"), str):
            continue
        chains.setdefault(entry["task"], []).append({
            "attempt": entry.get("attempt"), "outcome": entry.get("outcome"), "reason": entry.get("reason"),
            "driver": entry.get("driver"), "actor": entry.get("actor"), "presented_as": entry.get("presented_as"),
            "client_count": entry.get("client_count"), "entry_sha256": entry.get("entry_sha256"),
            "previous": entry.get("previous")})
    return chains


def _qualifies(attempt, mode, qualified):
    """A passing attempt supports a mode only through a driver registered for exactly that mode."""
    if mode == "human-judgment" or mode not in qualified.get(attempt["driver"], ()):
        return False
    if mode == "client-pair":
        return (attempt["presented_as"] == "real_client" and attempt["actor"] == "real_client"
                and type(attempt["client_count"]) is int and attempt["client_count"] >= 2)
    return True


def _task_view(task, chain):
    failed = [a for a in chain if a["outcome"] == "FAIL"]
    latest = chain[-1] if chain else None
    return {"task": task, "latest_outcome": latest["outcome"] if latest else None,
            "latest_reason": latest["reason"] if latest else None,
            "driver": latest["driver"] if latest else None, "attempts": chain,
            "failed_attempts": len(failed), "passed_after_failure": bool(failed) and bool(latest) and latest["outcome"] == "PASS"}


def _verified_reviews(reviews, manifest, store_valid):
    """id -> verified decision. A decision counts only when it cites an artifact of the valid sealed store."""
    listed = {}
    for entry in manifest["attempts"] if manifest else []:
        for item in entry.get("artifacts", []) if isinstance(entry, dict) else []:
            if isinstance(item, dict):
                listed[(item.get("path"), item.get("sha256"))] = entry.get("task")
    verified, rejected = {}, {}
    if not isinstance(reviews, dict) or len(reviews) > MAX_REVIEWS:
        return verified, {"$": "reviews_not_a_bounded_mapping"}
    for identifier, review in sorted(reviews.items()):
        cited = review.get("artifact") if isinstance(review, dict) else None
        if not store_valid:
            rejected[identifier] = "evidence_store_invalid"
        elif not isinstance(review, dict) or review.get("decision") not in REVIEW_DECISIONS:
            rejected[identifier] = "decision_must_be_yes_or_no"
        elif not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
            rejected[identifier] = "reviewer_missing"
        elif not isinstance(cited, dict) or (cited.get("path"), cited.get("sha256")) not in listed:
            rejected[identifier] = "artifact_not_in_sealed_store"
        else:
            verified[identifier] = {"state": REVIEW_DECISIONS[review["decision"]], "reviewer": review["reviewer"],
                                    "artifact": {"path": cited["path"], "sha256": cited["sha256"]}}
    return verified, rejected


def _blocker(mode, missing, row_id):
    """(kind, next steps, capabilities) for one blocked submethod; always concrete."""
    steps, kinds = [], []
    for name in missing:
        _, kind, step = CAPABILITY_NEXT.get(name, (mode, "implementation", "define an adapter task for capability " + name))
        steps.append(f"{name}: {step}")
        kinds.append(kind)
    if not missing:
        kind, step = MODE_NEXT[mode]
        steps.append(f"{mode} of {row_id}: {step}")
        kinds.append(kind)
    order = {name: position for position, name in enumerate(BLOCKER_KINDS)}
    return min(kinds, key=order.__getitem__), steps


def _submethod(row, mode, capabilities, selected, views, qualified, review, deferred_names):
    base = {"mode": mode, "qualified_by": [], "capabilities_missing": [], "next": [], "blocker_kind": None}
    if not selected:
        return dict(base, outcome="NOTRUN", reason="not_selected")
    if mode == "human-judgment" and review is not None:
        outcome = "PASS" if review["state"] == REVIEW_DECISIONS["yes"] else "FAIL"
        return dict(base, outcome=outcome, reason="human_review_" + review["state"], review=review)
    mine = [name for name in row["requires"]
            if CAPABILITY_NEXT.get(name, (mode,))[0] == mode and capabilities.get(name) != "available"]
    supporting = []
    for view in views:
        if view["attempts"] and _qualifies(view["attempts"][-1], mode, qualified):
            supporting.append(view)
    if any(view["latest_outcome"] == "FAIL" for view in supporting):
        return dict(base, outcome="FAIL", reason="qualified_task_failed",
                    qualified_by=sorted(view["task"] for view in supporting if view["latest_outcome"] == "FAIL"))
    passed = [view["task"] for view in supporting if view["latest_outcome"] == "PASS"]
    if passed and not mine:
        return dict(base, outcome="PASS", reason="qualified_task_passed", qualified_by=sorted(passed))
    if mine and set(mine) & deferred_names:
        steps = [f"{name}: {DEFERRED_NEXT.get(name, 'deferred')} {automation.DEFERRED_REASON}"
                 for name in mine if name in deferred_names]
        others = [name for name in mine if name not in deferred_names]
        if others:
            steps += _blocker(mode, others, row["id"])[1]
        return dict(base, outcome="NOTRUN", reason=automation.DEFERRED_REASON, capabilities_missing=mine, next=steps)
    if mine:
        kind, steps = _blocker(mode, mine, row["id"])
        return dict(base, outcome="BLOCKED", reason="missing_capability:" + ",".join(mine),
                    capabilities_missing=mine, next=steps, blocker_kind=kind)
    kind, steps = _blocker(mode, [], row["id"])
    reason = "human_review_required" if mode == "human-judgment" else "no_qualified_driver"
    return dict(base, outcome="BLOCKED", reason=reason, next=steps, blocker_kind=kind)


def _item(row, trace, capabilities, selected, chains, covers, qualified, review, source_paths, deferred_names):
    views = [_task_view(task, chains.get(task, [])) for task, ids in sorted(covers.items()) if row["id"] in ids]
    submethods = [_submethod(row, mode, capabilities, selected, views, qualified, review, deferred_names)
                  for mode in row["modes"]]
    results = [s["outcome"] for s in submethods]
    failing = [v["task"] for v in views if v["latest_outcome"] == "FAIL"]
    if not selected:
        outcome, reason = "NOTRUN", "not_selected"
    elif "FAIL" in results or failing:
        outcome, reason = "FAIL", "submethod_failed" if "FAIL" in results else "covering_task_failed"
    elif any(s["reason"] == automation.DEFERRED_REASON for s in submethods):
        outcome, reason = "NOTRUN", automation.DEFERRED_REASON
    elif all(value == "PASS" for value in results):
        outcome, reason = "PASS", "all_submethods_passed"
    elif "BLOCKED" in results:
        outcome, reason = "BLOCKED", "unsupported_submethod:" + ",".join(
            s["mode"] for s in submethods if s["outcome"] == "BLOCKED")
    else:
        outcome, reason = "NOTRUN", "submethod_not_run"
    nexts, kinds = [], []
    for sub in submethods:
        if sub["outcome"] in ("BLOCKED", "NOTRUN"):
            nexts.extend(f"[{sub['mode']}] {step}" for step in sub["next"])
        if sub["blocker_kind"]:
            kinds.append(sub["blocker_kind"])
    return {
        "id": row["id"], "origin": row["origin"], "scenario": row["scenario"],
        "outcome": outcome, "reason": reason, "submethods": submethods,
        "tasks": views, "next": nexts, "blocker_kinds": sorted(set(kinds)),
        "acceptance": {"state": ACCEPTANCE_STATE, "basis": ACCEPTANCE_BASIS},
        "human_review": review if review is not None else {"state": NOT_REVIEWED},
        "evidence_class": {
            "synthetic_supporting": sorted(v["task"] for v in views if v["latest_outcome"] == "PASS"
                                           and v["attempts"][-1]["presented_as"] == "offline_framework"),
            "native_zero_client_supporting": sorted(v["task"] for v in views if v["latest_outcome"] == "PASS"
                                                    and v["attempts"][-1]["presented_as"] == "zero_client_native"),
            "human": review["state"] if review is not None else NOT_REVIEWED,
            "accepted": False},
        "trace": {"criterion": row["criterion"], "assertions": list(row["assertions"]),
                  "modes": list(row["modes"]), "requires": list(row["requires"]),
                  "related_ids": list(row["related_ids"]),
                  "sources": [dict(s, **source_paths.get(s.get("source"), {})) for s in trace]},
    }


def reconcile(catalog, items, covers, chains):
    """Exact reconciliation; every disagreement is an error naming the id or count."""
    errors = []
    rows = catalog["tests"]
    catalogue = [row["id"] for row in rows]
    reported = [item["id"] for item in items]
    for identifier in sorted(set(catalogue) - set(reported)):
        errors.append({"code": "missing_from_report", "id": identifier})
    for identifier in sorted(set(reported) - set(catalogue)):
        errors.append({"code": "extra_in_report", "id": identifier})
    if len(reported) != len(set(reported)) or len(reported) != len(catalogue):
        errors.append({"code": "count_mismatch", "catalogue": len(catalogue), "reported": len(reported)})
    original = {row["id"] for row in rows if row["origin"] == "original"}
    declared = catalog["coverage"].get("original", {}) if isinstance(catalog["coverage"], dict) else {}
    declared_ids = declared.get("ids", []) if isinstance(declared, dict) else []
    for identifier in sorted(automation.ORIGINAL_IDS - original):
        errors.append({"code": "missing_original", "id": identifier})
    for identifier in sorted(original - automation.ORIGINAL_IDS):
        errors.append({"code": "extra_original", "id": identifier})
    for identifier in sorted(set(declared_ids) ^ automation.ORIGINAL_IDS):
        errors.append({"code": "declared_original_mismatch", "id": identifier})
    if declared.get("expected_count") != len(automation.ORIGINAL_IDS) or declared.get("mapped_count") != len(original):
        errors.append({"code": "original_count_mismatch", "expected": len(automation.ORIGINAL_IDS),
                       "declared": declared.get("expected_count"), "mapped": len(original)})
    extensions = catalog["coverage"].get("extensions", {}) if isinstance(catalog["coverage"], dict) else {}
    if isinstance(extensions, dict) and extensions.get("mapped_count") != len(rows) - len(original):
        errors.append({"code": "extension_count_mismatch", "declared": extensions.get("mapped_count"),
                       "listed": len(rows) - len(original)})
    sources = catalog["coverage"].get("row_sources", {}) if isinstance(catalog["coverage"], dict) else {}
    for identifier in sorted(set(catalogue) ^ set(sources)):
        errors.append({"code": "criterion_trace_mismatch", "id": identifier})
    for item in items:
        if not item["trace"]["criterion"].strip():
            errors.append({"code": "criterion_trace_empty", "id": item["id"]})
        if item["outcome"] == "BLOCKED" and not item["next"]:
            errors.append({"code": "blocked_without_next", "id": item["id"]})
        for sub in item["submethods"]:
            if sub["outcome"] == "BLOCKED" and not sub["next"]:
                errors.append({"code": "blocked_without_next", "id": item["id"], "mode": sub["mode"]})
            if sub["outcome"] == "PASS" and sub["mode"] != "human-judgment" and not sub["qualified_by"]:
                errors.append({"code": "unsupported_pass", "id": item["id"], "mode": sub["mode"]})
        if item["outcome"] == "PASS" and any(s["outcome"] != "PASS" for s in item["submethods"]):
            errors.append({"code": "unsupported_pass", "id": item["id"]})
        if item["acceptance"]["state"] != ACCEPTANCE_STATE:
            errors.append({"code": "promoted_acceptance", "id": item["id"]})
    for task, ids in sorted(covers.items()):
        if task not in chains:
            errors.append({"code": "covering_task_missing", "task": task})
        for identifier in sorted(set(ids) - set(catalogue)):
            errors.append({"code": "covers_unknown_id", "task": task, "id": identifier})
    return {"ok": not errors, "catalogue_count": len(catalogue), "reported_count": len(reported),
            "original_expected": len(automation.ORIGINAL_IDS), "original_catalogue": len(original),
            "errors": errors}


def build_report(catalog, store_root, *, run_id, covers=None, capabilities=None, selected=None,
                 pins=None, manifest_sha256=None, reviews=None, qualified=None, expected_tasks=None):
    """Coverage report for one sealed store. covers maps a task id to the catalogue ids it covers."""
    encoded = automation.validate_catalog(catalog)
    covers = {task: list(ids) for task, ids in (covers or {}).items()}
    capabilities = dict(capabilities or {})
    qualified = QUALIFIED if qualified is None else qualified
    identifiers = {row["id"] for row in catalog["tests"]}
    selection = identifiers if selected is None else set(selected)
    sealed = evidence.validate_store(store_root, pins=pins, expected_tasks=expected_tasks, manifest_sha256=manifest_sha256)
    manifest = _load_store(store_root)
    store_errors = [{"code": e["code"], "field": e["field"]} for e in sealed["errors"]]
    if manifest is not None and len(manifest["attempts"]) > MAX_ATTEMPTS:
        manifest = None
        store_errors.append({"code": "store_manifest", "field": "attempts"})
    store_valid = sealed["valid"] and manifest is not None and not store_errors
    chains = _chains(manifest)
    verified, rejected = _verified_reviews(reviews or {}, manifest, store_valid)
    sources = catalog["sources"] if isinstance(catalog["sources"], list) else []
    source_paths = {s["id"]: {"path": s.get("path"), "sha256": s.get("sha256")}
                    for s in sources if isinstance(s, dict) and isinstance(s.get("id"), str)}
    row_sources = catalog["coverage"].get("row_sources", {}) if isinstance(catalog["coverage"], dict) else {}
    deferred_names = set(discovery.DEFERRED_CAPABILITIES)
    items = [_item(row, row_sources.get(row["id"], []), capabilities, row["id"] in selection, chains, covers,
                   qualified, verified.get(row["id"]), source_paths, deferred_names) for row in catalog["tests"]]
    if not store_valid:  # a store that fails its strict check supports nothing
        for item in items:
            if item["outcome"] == "PASS":
                item["outcome"], item["reason"] = "BLOCKED", "evidence_store_invalid"
                item["next"] = ["evidence store: rerun the run in a new output directory and repair the listed store errors"]
    reconciliation = reconcile(catalog, items, covers, chains)
    counts = {name: sum(1 for item in items if item["outcome"] == name) for name in OUTCOMES}
    submethods = {mode: {name: sum(1 for item in items for s in item["submethods"]
                                   if s["mode"] == mode and s["outcome"] == name) for name in OUTCOMES} for mode in MODES}
    complete = store_valid and reconciliation["ok"]
    if counts["FAIL"]:
        status = "FAIL"
    elif not complete:
        status = "INCOMPLETE"
    else:
        status = next((name for name in ("BLOCKED", "NOTRUN") if counts[name]), "PASS")
    blockers = {}
    for item in items:
        for step in item["next"]:
            blockers.setdefault(step, []).append(item["id"])
    framework = [_task_view(task, chain) for task, chain in sorted(chains.items())]
    return {
        "report_version": REPORT_VERSION, "kind": "coverage-report", "mode": "execution-coverage",
        "evidence_label": artifacts.EVIDENCE_LABEL, "acceptance": "not_evaluated", "clients": 0,
        "multiplayer": "never_proven", "run_id": run_id,
        "catalog_id": catalog["catalog_id"], "catalog_sha256": hashlib.sha256(encoded).hexdigest(),
        "covers_sha256": _sha(covers), "complete": complete, "status": status,
        "store": {"valid": store_valid, "manifest_sha256": manifest_sha256, "errors": store_errors},
        "reconciliation": reconciliation, "counts": counts, "submethod_counts": submethods,
        "capabilities": dict(sorted(capabilities.items())),
        "human_review": {"default": NOT_REVIEWED, "verified": len(verified), "rejected": rejected},
        "next_steps": [{"next": step, "items": ids} for step, ids in sorted(blockers.items())],
        "framework_tasks": framework, "items": items,
    }


def markdown(report):
    """Short summary; no paths, no criterion text."""
    counts, recon = report["counts"], report["reconciliation"]
    lines = [
        f"# Coverage report: {report['run_id']}", "",
        f"Status {report['status']}; complete {str(report['complete']).lower()}; acceptance not evaluated; "
        f"evidence {report['evidence_label']}, 0 clients, multiplayer never proven.", "",
        f"Catalogue {recon['catalogue_count']} rows, reported {recon['reported_count']}, "
        f"original {recon['original_catalogue']} of {recon['original_expected']}; "
        f"reconciliation {'exact' if recon['ok'] else 'ERRORS ' + str(len(recon['errors']))}; "
        f"store {'valid' if report['store']['valid'] else 'INVALID'}.", "",
        "| Outcome | Rows |", "| --- | ---: |",
    ]
    lines += [f"| {name} | {counts[name]} |" for name in OUTCOMES]
    lines += ["", "| Submethod | " + " | ".join(OUTCOMES) + " |", "| --- | " + " | ".join("---:" for _ in OUTCOMES) + " |"]
    lines += [f"| {mode} | " + " | ".join(str(report["submethod_counts"][mode][name]) for name in OUTCOMES) + " |"
              for mode in MODES]
    lines += ["", f"Acceptance: every row is {ACCEPTANCE_STATE}; human review is \"{NOT_REVIEWED}\" "
              f"unless a decision cites a sealed artifact ({report['human_review']['verified']} verified)."]
    failing = [item["id"] for item in report["items"] if item["outcome"] == "FAIL"]
    retried = sorted({view["task"] for view in report["framework_tasks"] if view["failed_attempts"]})
    if failing:
        lines += ["", "Failing rows: " + ", ".join(failing)]
    if retried:
        lines += ["", "Tasks with a failed attempt in their chain: " + ", ".join(retried)]
    if recon["errors"]:
        lines += ["", "Reconciliation errors: " + ", ".join(
            sorted({error["code"] + (":" + error["id"] if "id" in error else "") for error in recon["errors"]})[:20])]
    lines += ["", "Next steps (rows each):"]
    lines += [f"- {entry['next']} ({len(entry['items'])})" for entry in report["next_steps"][:25]]
    if len(report["next_steps"]) > 25:
        lines.append(f"- and {len(report['next_steps']) - 25} more in coverage.json")
    return "\n".join(lines) + "\n"


def write_outputs(out_dir, report):
    """Write coverage.json and coverage.md into the run's out dir; refuse the repository and any overwrite."""
    out = Path(out_dir).absolute()
    if out.resolve().is_relative_to(automation.ROOT.resolve()):
        raise ValueError("coverage output must not be written into the repository")
    out.mkdir(parents=True, exist_ok=True)
    names = {"coverage.json": json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
             "coverage.md": markdown(report)}
    if any((out / name).exists() or (out / name).is_symlink() for name in names):
        raise ValueError("coverage output already exists; it is never overwritten")
    for name, text in names.items():
        with open(out / name, "x", encoding="utf-8") as stream:
            stream.write(text)
    return {"json": "coverage.json", "markdown": "coverage.md",
            "sha256": hashlib.sha256(names["coverage.json"].encode("utf-8")).hexdigest()}


def sealed_capabilities(run_dir, run_id):
    """Capabilities recorded in a run's report.json, but only when that report is sealed to its store.

    A report counts only when it names this run, says its store validated, and its recorded store
    hash equals the hash of the manifest now on disk; anything else is refused with a reason, since
    an edited or foreign report must never decide which capabilities were available. A run directory
    with no report.json yields no capabilities (nothing is claimed available).
    """
    run_dir = Path(run_dir)
    path = run_dir / "report.json"
    if not path.exists() and not path.is_symlink():
        return {}
    try:
        report = evidence._load_json(path)
    except (OSError, ValueError, RuntimeError, RecursionError):
        raise ValueError("report.json is not readable strict JSON; refusing to read capabilities from it") from None
    store = report.get("store") if isinstance(report, dict) else None
    if not isinstance(store, dict) or store.get("valid") is not True or not isinstance(store.get("sha256"), str):
        raise ValueError("report.json is not sealed (its store did not validate); refusing to read capabilities")
    if report.get("run_id") != run_id:
        raise ValueError("report.json belongs to another run; refusing to read capabilities")
    try:
        on_disk = hashlib.sha256((run_dir / "evidence" / evidence.STORE_MANIFEST).read_bytes()).hexdigest()
    except OSError:
        raise ValueError("sealed store manifest is unreadable; refusing to read capabilities") from None
    if on_disk != store["sha256"]:
        raise ValueError("report.json does not match the sealed store manifest; refusing to read capabilities")
    capabilities = report.get("capabilities")
    if not isinstance(capabilities, dict) or not all(isinstance(key, str) and isinstance(value, str)
                                                     for key, value in capabilities.items()):
        raise ValueError("sealed report.json holds no capability map; refusing to read capabilities")
    return dict(capabilities)


def covers_from_manifest(manifest, identifiers):
    """task id -> covered ids from a run manifest; unknown ids are refused."""
    covers = {}
    tasks = manifest.get("tasks") if isinstance(manifest, dict) else None
    if not isinstance(tasks, list):
        raise ValueError("manifest tasks: expected a list")
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str):
            raise ValueError("manifest task: expected an object with an id")
        ids = task.get("covers", [])
        if not isinstance(ids, list) or not set(ids) <= identifiers:
            raise ValueError("covers contains unknown test IDs")
        covers[task["id"]] = list(ids)
    return covers


def pins_for_run(registry):
    """Method pins the runner used, including the deferred-task producer."""
    extra = {automation.DEFERRED_DRIVER: artifacts.text_pin(automation.DEFERRED_DRIVER + automation.DEFERRED_REASON)}
    return artifacts.pins_for(registry, extra)
