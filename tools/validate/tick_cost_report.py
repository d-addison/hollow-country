"""Aggregate [HC TickCost] from an RPT without echoing other (possibly private) text.

Run: python3 -B -m tools.validate.tick_cost_report server.RPT
Weights are integer multipliers of the existing caller costs (default 1), read
from performance.json as TickWeight_<consumer>. The cheapest sampled base unit
sets the quantum. Proposals preserve current caller cost ratios; shared consumer
ids cannot distinguish their individual call sites. No load/runtime acceptance
is inferred. Stream input; retain at most 31 consumers, even for a large RPT.
"""
import argparse
import json
import math
from pathlib import Path
import re

FIELD = re.compile(r"([a-z_]+)=([^\s;]+)")
CONSUMERS = (
    "INFECTED INTERIORS SEARCH_BIND SEARCH_MAINT SEARCH_REFRESH SEARCH_DETACHED "
    "LOD_CLASSIFY LOD_HERD BASES CONFLICT TRADE SITUATIONS BASE_RAID ROLES "
    "FORMATION CARFIX HEARTH INCIDENTS INCIDENT_RESPONSE AI_RESPAWN "
    "SEARCH_COMPACT SHELTER AI_SITES STORY_INDEX"
).split()


def aggregate(path):
    rows = {}
    rejected = 0
    # Line length is bounded too: skip oversized lines, never retain the RPT.
    with path.open(encoding="utf-8", errors="replace") as stream:
        while True:
            line = stream.readline(16385)
            if not line:
                break
            if len(line) > 16384:
                while line and not line.endswith("\n"):
                    line = stream.readline(16385)
                continue
            marker = line.find("[HC TickCost] ")
            if marker < 0:
                continue
            fields = dict(FIELD.findall(line[marker:]))
            name = fields.get("consumer", "")
            if name not in CONSUMERS and name not in {f"UNASSIGNED_{i}" for i in range(23, 31)}:
                rejected += 1
                continue
            try:
                values = {key: float(fields[key]) for key in (
                    "weight", "granted", "used", "starved", "ticks_sum", "ticks_max"
                )}
                if any(not math.isfinite(v) or v < 0 for v in values.values()):
                    raise ValueError
                weight = values["weight"]
                if not weight.is_integer() or not 1 <= weight <= 64 or values["used"] <= 0 or values["granted"] <= 0:
                    raise ValueError
                window = int(fields["window"])
                if window < 1:
                    raise ValueError
            except (KeyError, ValueError, OverflowError):
                rejected += 1
                continue
            row = rows.setdefault(name, dict(windows=0, granted=0.0, used=0.0,
                                            base_units=0.0, starved=0.0, ticks=0.0,
                                            ticks_max=0.0, weights=set(), current=1))
            row["windows"] += 1
            row["granted"] += values["granted"]
            row["used"] += values["used"]
            row["base_units"] += values["used"] / weight
            row["starved"] += values["starved"]
            row["ticks"] += values["ticks_sum"]
            row["ticks_max"] = max(row["ticks_max"], values["ticks_max"])
            row["weights"].add(int(weight))
            row["current"] = int(weight)
    return rows, rejected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rpt", type=Path)
    args = parser.parse_args(argv)
    try:
        rows, rejected = aggregate(args.rpt)
    except OSError:
        parser.exit(2, "Cannot read RPT input.\n")
    costs = {name: row["ticks"] / row["base_units"] for name, row in rows.items() if row["ticks"] > 0}
    print("Provisional consumer multipliers; runtime=PENDING (raw TickCount units).")
    print("Normalised to cheapest measured base unit; defaults=1; unmeasured weights retained.")
    print("current=last logged weight; mixed weights are marked; rows=observed window lines.")
    print("consumer current rows used starved ticks_sum ticks_max ticks/base_unit relative proposed")
    quantum = min(costs.values(), default=0)
    proposed = {}
    for name in CONSUMERS + sorted(set(rows) - set(CONSUMERS)):
        row = rows.get(name)
        if row is None:
            print(f"{name} unknown 0 - - - - - - retain")
            continue
        cost = costs.get(name, 0)
        relative = cost / quantum if quantum else 0
        weight = min(64, max(1, math.floor(relative + 0.5))) if cost else row["current"]
        suffix = "*" if len(row["weights"]) > 1 else ""
        print(f"{name} {row['current']}{suffix} {row['windows']} {row['used']:.0f} "
              f"{row['starved']:.0f} {row['ticks']:.0f} {row['ticks_max']:.0f} "
              f"{cost:.3f} {relative:.3f} {weight}")
        if cost:
            proposed[f"TickWeight_{name}"] = weight
    if proposed:
        print("Proposed performance.json fields (merge after reviewing sampling/attribution; range 1..64):")
        print(json.dumps(proposed, indent=2))
    else:
        print("no_data: no positive measured consumer cost; retain current weights.")
    if rejected:
        print(f"Ignored malformed/unsupported TickCost lines: {rejected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
