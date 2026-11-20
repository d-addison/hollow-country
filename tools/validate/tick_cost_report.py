"""Aggregate [HC TickCost] from an RPT without echoing other (possibly private) text.

Run: python3 -B -m tools.validate.tick_cost_report server.RPT
Rules: python3 -B -m tools.validate.tick_cost_report --rules server.RPT
Weights are integer multipliers of the existing caller costs (default 1), read
from performance.json as TickWeight_<consumer>. The cheapest sampled base unit
sets the quantum. Proposals preserve current caller cost ratios; shared consumer
ids cannot distinguish their individual call sites. No load/runtime acceptance
is inferred. Stream input; rules use temporary disk storage to bound RAM.
"""
import argparse
from contextlib import closing
import json
import math
from pathlib import Path
import re
import sqlite3
import tempfile

from tools.setup.server_report import redact, DROPPED

FIELD = re.compile(r"([a-z_]+)=([^\s;]+)")
CONSUMERS = (
    "INFECTED INTERIORS SEARCH_BIND SEARCH_MAINT SEARCH_REFRESH SEARCH_DETACHED "
    "LOD_CLASSIFY LOD_HERD BASES CONFLICT TRADE SITUATIONS BASE_RAID ROLES "
    "FORMATION CARFIX HEARTH INCIDENTS INCIDENT_RESPONSE AI_RESPAWN "
    "SEARCH_COMPACT SHELTER AI_SITES STORY_INDEX AI_ROUTES POLICE_BIND"
).split()

# Shared slots with several module callers deliberately use the window-3 fallback.
CONSUMER_MODULE = {
    "INFECTED": "Infected", "INTERIORS": "Interiors",
    "SEARCH_BIND": "SearchBinding", "SEARCH_DETACHED": "SearchBinding",
    "SEARCH_REFRESH": "LootRefresh", "SEARCH_COMPACT": "LootRefresh",
    "LOD_CLASSIFY": "InfectedLOD", "LOD_HERD": "InfectedLOD",
    "BASES": "Camps", "CONFLICT": "World", "SHELTER": "Shelters",
    "STORY_INDEX": "Events", "ROLES": "AIRoles", "INCIDENT_RESPONSE": "AIIncidents",
}
PERIODIC = re.compile(r"\[HC (?:Perf|TickCost|Cost|CostTotal|Step|Save)\]")
SCRIPT = re.compile(r"\bSCRIPT(?:\s*\([A-Z]\))?\s*:\s?(.*)")
CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)\b")
PRIVATE = re.compile(r'steam ?id|uid|name=|[0-9]{17}|Player "|id=|admin.?id', re.I)
HOME = re.compile(r"(?:/home/|/Users/|/root(?:/|\b)|/mnt/[a-z]/Users/|[A-Z]:[\\/]+Users[\\/])", re.I)


def safe_rule(line):
    """Never echo identifiers or home paths, including in repeated-line previews."""
    if PRIVATE.search(line) or HOME.search(line):
        return None
    safe = redact(line)
    return None if safe == DROPPED else safe


def rpt_lines(path):
    """Skip oversized records without allocating an unbounded line."""
    with Path(path).open(encoding="utf-8", errors="replace") as stream:
        while True:
            line = stream.readline(16385)
            if not line:
                return
            if len(line) > 16384:
                while line and not line.endswith("\n"):
                    line = stream.readline(16385)
                continue
            yield line.rstrip("\r\n")


def number(fields, key, default=None):
    try:
        value = float(fields[key])
        return value if math.isfinite(value) and value >= 0 else default
    except (KeyError, ValueError, OverflowError):
        return default


def perf_rules(path):
    """Yield deterministic warnings with bounded RAM and temporary disk storage.

    Missing consumer windows are not evidence of starvation. Readiness gates R1
    by the first emitted window after ready=true; unknown owners start at 3.
    R2 uses line order after the final readiness receipt. Tick conversion uses
    the same window's calibration (even when Perf follows Step), then the most
    recent calibration, then the first calibration, then 10000 ticks/ms.
    Clock time starts at the first timestamp in the RPT and handles midnight.
    """
    with tempfile.TemporaryDirectory(prefix="hc-perf-rules-") as temp:
        with closing(sqlite3.connect(str(Path(temp) / "rules.sqlite"))) as db:
            db.execute("PRAGMA cache_size=-1024")
            db.execute("PRAGMA temp_store=FILE")
            db.executescript("""
                CREATE TABLE ready(module TEXT PRIMARY KEY, failed INTEGER, start_window INTEGER);
                CREATE TABLE late(module TEXT PRIMARY KEY, seconds REAL);
                CREATE TABLE windows(w INTEGER PRIMARY KEY);
                CREATE TABLE costs(consumer TEXT, w INTEGER, starved INTEGER, PRIMARY KEY(consumer,w));
                CREATE TABLE calibration(w INTEGER PRIMARY KEY, line INTEGER, rate REAL);
                CREATE INDEX calibration_line ON calibration(line);
                CREATE TABLE spikes(owner TEXT, stage TEXT, heaviest TEXT, w INTEGER,
                                    line INTEGER, cost REAL, raw INTEGER);
                CREATE TABLE saves(job TEXT, op TEXT, w INTEGER, line INTEGER, cost REAL);
                CREATE TABLE repeated(line TEXT PRIMARY KEY, n INTEGER);
            """)
            last_ready = last_window = 0
            previous_clock = start_clock = None
            day = 0
            for index, line in enumerate(rpt_lines(path), 1):
                clock = CLOCK.match(line)
                elapsed = None
                if clock:
                    h, m, s = map(float, clock.groups())
                    current = h * 3600 + m * 60 + s
                    if previous_clock is not None and current < previous_clock - 43200:
                        day += 86400
                    previous_clock = current
                    if start_clock is None:
                        start_clock = current
                    elapsed = day + current - start_clock
                script = SCRIPT.search(line)
                if script and not PERIODIC.search(script[1]):
                    # Keep the original body as the key: no digit collapsing or
                    # redaction before equality/counting. Only safe previews leave disk.
                    db.execute("INSERT INTO repeated VALUES(?,1) ON CONFLICT(line) DO UPDATE SET n=n+1",
                               (line[script.start():],))
                marker = re.search(r"\[HC (Ready|TickCost|Perf|Step|Save)\]", line)
                if not marker:
                    continue
                fields = dict(FIELD.findall(line[marker.end():]))
                tag = marker[1]
                w = number(fields, "window")
                w = int(w) if w is not None and 1 <= w <= 2147483647 and w.is_integer() else None
                if tag == "Ready":
                    last_ready = index
                    module = fields.get("module")
                    if not module:
                        continue
                    db.execute("INSERT OR IGNORE INTO ready VALUES(?,0,NULL)", (module,))
                    if fields.get("ready") == "false":
                        db.execute("UPDATE ready SET failed=1 WHERE module=?", (module,))
                    elif fields.get("ready") == "true":
                        failed, = db.execute("SELECT failed FROM ready WHERE module=?", (module,)).fetchone()
                        if failed and elapsed is not None and elapsed > 180:
                            db.execute("INSERT OR IGNORE INTO late VALUES(?,?)", (module, elapsed))
                        db.execute("UPDATE ready SET start_window=COALESCE(start_window,?) WHERE module=?",
                                   (last_window + 1, module))
                if tag in ("Perf", "TickCost") and w is not None:
                    last_window = max(last_window, w)
                    db.execute("INSERT OR IGNORE INTO windows VALUES(?)", (w,))
                if tag == "TickCost" and w is not None and fields.get("consumer"):
                    granted = number(fields, "granted")
                    values = [number(fields, key) for key in ("used", "starved", "refused")]
                    starved = granted == 0 or (granted is not None and all(v == granted for v in values))
                    db.execute("INSERT INTO costs VALUES(?,?,?) ON CONFLICT(consumer,w) "
                               "DO UPDATE SET starved=MIN(starved,excluded.starved)",
                               (fields["consumer"], w, int(starved)))
                elif tag == "Perf":
                    rate = number(fields, "ticks_per_ms")
                    if rate and w is not None:
                        db.execute("INSERT OR REPLACE INTO calibration VALUES(?,?,?)", (w, index, rate))
                    cost = number(fields, "slowest_module_max_ms")
                    if cost is not None:
                        db.execute("INSERT INTO spikes VALUES(?,?,?,?,?,?,0)",
                                   (fields.get("slowest_module", "unknown"), "module", "unknown", w, index, cost))
                elif tag == "Step":
                    cost = number(fields, "worst_tick_ticks")
                    if cost is not None:
                        stages = [(number(fields, key), key) for key in fields
                                  if key not in {"window", "ticks", "worst_tick_ticks", "worst_tick_items",
                                                 "heaviest_item_ticks", "deferred_n", "deferred_max_ticks"}
                                  and number(fields, key) is not None]
                        stage = max(stages)[1] if stages else "unknown"
                        db.execute("INSERT INTO spikes VALUES(?,?,?,?,?,?,1)",
                                   (fields.get("owner", "unknown"), stage, fields.get("heaviest", "unknown"),
                                    w, index, cost))
                elif tag == "Save":
                    cost = number(fields, "max_stage_ticks")
                    if cost is not None:
                        db.execute("INSERT INTO saves VALUES(?,?,?,?,?)",
                                   (fields.get("job", "unknown"), fields.get("op", "unknown"),
                                    last_window + 1, index, cost))
            db.commit()
            for consumer, in db.execute("SELECT DISTINCT consumer FROM costs ORDER BY consumer"):
                module = CONSUMER_MODULE.get(consumer, consumer)
                row = db.execute("SELECT start_window FROM ready WHERE module=?", (module,)).fetchone()
                if row and row[0] is None:
                    continue
                start = row[0] if row and row[0] is not None else 3
                total, = db.execute("SELECT COUNT(*) FROM windows WHERE w>=?", (start,)).fetchone()
                count, = db.execute("SELECT COUNT(*) FROM costs WHERE consumer=? AND w>=? AND starved=1",
                                    (consumer, start)).fetchone()
                if total and count == total:
                    yield f"perf_rule=R1 consumer {consumer} starved in {count}/{total} windows"
            # Correlated lookups avoid an in-memory window/calibration history.
            rate_sql = """COALESCE((SELECT rate FROM calibration WHERE w=e.w),
                (SELECT rate FROM calibration WHERE line<=e.line ORDER BY line DESC LIMIT 1),
                (SELECT rate FROM calibration ORDER BY line LIMIT 1), 10000.0)"""
            query = f"""WITH measured AS (
                SELECT *, CASE WHEN raw=1 THEN cost/({rate_sql}) ELSE cost END AS ms
                FROM spikes e WHERE line>?
            ), ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY owner ORDER BY ms DESC,line) AS rank FROM measured
            ) SELECT owner,stage,heaviest,ms,w FROM ranked WHERE rank=1 AND ms>16 ORDER BY owner"""
            for owner, stage, heaviest, ms, window in db.execute(query, (last_ready,)):
                yield (f"perf_rule=R2 owner={owner} stage={stage} heaviest={heaviest} "
                       f"ms={ms:.3f} window={window if window is not None else 'unknown'}")
            for line, count in db.execute("SELECT line,n FROM repeated WHERE n>20 ORDER BY line"):
                safe = safe_rule(line)
                if safe is None:
                    safe = "[private line omitted]"
                    tag = None
                else:
                    tag = re.search(r"\[[^\]]+\]", safe)
                yield f"perf_rule=R3 tag={tag[0] if tag else 'SCRIPT'} count={count} text={safe[:80]}"
            for module, seconds in db.execute("SELECT module,seconds FROM late ORDER BY module"):
                yield f"perf_rule=R4 module={module} seconds={seconds:.3f}"
            for job, op, ms in db.execute(
                    f"SELECT job,op,cost/({rate_sql}) AS ms FROM saves e WHERE ms>16 ORDER BY line"):
                yield f"perf_rule=R5 job={job} op={op} ms={ms:.3f}"


def print_rules(path):
    """Warnings never decide the boot result; failures to inspect are warnings too."""
    count = 0
    try:
        for line in perf_rules(path):
            safe = safe_rule(line)
            if safe:
                print(safe)
                count += 1
    except (OSError, sqlite3.Error):
        print("perf_rules=warn count=" + str(count) + " inspection=incomplete")
        return
    print(f"perf_rules={'warn' if count else 'pass'} count={count}")


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
    parser.add_argument("--rules", action="store_true", help="report provisional runtime rule warnings")
    args = parser.parse_args(argv)
    if args.rules:
        print_rules(args.rpt)
        return 0
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
