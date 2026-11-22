"""Disposable native ReadFile/NUL experiment: stage and ingest only, never launch.

Stage emits an actor-free CE-disabled mission overlay and three binary fixtures.
The lead runs it in a fresh disposable runtime under the normal host lock and
external watchdog. It never belongs in a production mission/profile. Ingest
reports observations, not a native behavior verdict or gameplay acceptance.
"""
import argparse
import json
from pathlib import Path

from tools.setup.probe_core import safe

FIXTURES = {"ascii": b"abcdef", "nul": b"ab\x00def", "torn": b"\xff\x00x\x01"}
RESULT = "hc-custody-read-observations.json"
HOOK = '''// Disposable CE-disabled mission; no entities, hive, or player state.
void main() {}
class HCNulReadRow
{
    string name;
    int string_count;
    int string_length;
    int raw_count;
    ref array<int> raw_head = new array<int>;
}
class HCNulReadReceipt
{
    string kind = "custody-native-read-observations";
    ref array<ref HCNulReadRow> cases = new array<ref HCNulReadRow>;
}
class CustomMission : MissionServer
{
    override void OnMissionStart()
    {
        super.OnMissionStart();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(this.HCNulRead, 1000, false);
    }
    void HCNulRead()
    {
        string names[] = {"ascii", "nul", "torn"};
        HCNulReadReceipt receipt = new HCNulReadReceipt;
        for (int i = 0; i < 3; i++)
        {
            string path = "$mission:hc-read-" + names[i] + ".bin";
            FileHandle handle = OpenFile(path, FileMode.READ);
            if (!handle) { Print("[HC NulRead] open_failed"); return; }
            string text;
            HCNulReadRow row = new HCNulReadRow;
            row.name = names[i];
            row.string_count = ReadFile(handle, text, 4096);
            row.string_length = text.Length();
            CloseFile(handle);
            handle = OpenFile(path, FileMode.READ);
            if (!handle) { Print("[HC NulRead] raw_open_failed"); return; }
            int raw[4096];
            row.raw_count = ReadFile(handle, raw, 4096);
            CloseFile(handle);
            for (int j = 0; j < 8; j++) { row.raw_head.Insert(raw[j]); }
            receipt.cases.Insert(row);
        }
        string error;
        if (!JsonFileLoader<HCNulReadReceipt>.SaveFile("$profile:hc-custody-read-observations.json", receipt, error))
        {
            Print("[HC NulRead] result_write_failed");
            return;
        }
        Print("[HC NulRead] complete observations_only=true");
    }
}
Mission CreateCustomMission(string path) { return new CustomMission(); }
'''


def stage(destination):
    """Write a fresh mission overlay only; no installed/runtime paths are touched."""
    destination = safe(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, blob in FIXTURES.items():
        (destination / f"hc-read-{name}.bin").write_bytes(blob)
    (destination / "init.c").write_text(HOOK, encoding="ascii")
    (destination / "custody-read-plan.json").write_text(json.dumps({
        "kind": "custody-native-read-plan", "max_owned_entities": 0,
        "ce_enabled": False, "lead_only": True, "external_watchdog_seconds": 180,
        "fixtures": {name: list(blob) for name, blob in FIXTURES.items()},
        "result": RESULT, "acceptance": "PENDING",
    }, indent=2) + "\n", encoding="ascii")


def ingest(receipt):
    """Accept bounded numeric observations without asserting expected engine results."""
    with safe(receipt).open("rb") as stream:
        blob = stream.read(4097)
    if len(blob) > 4096:
        raise ValueError("receipt exceeds cap")
    data = json.loads(blob)
    if not isinstance(data, dict) or data.get("kind") != "custody-native-read-observations":
        raise ValueError("unexpected receipt kind")
    rows = data.get("cases")
    if not isinstance(rows, list) or len(rows) != len(FIXTURES):
        raise ValueError("fixture observations missing")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("name") not in FIXTURES or row["name"] in seen:
            raise ValueError("invalid or duplicate fixture")
        seen.add(row["name"])
        for field in ("string_count", "string_length", "raw_count"):
            if type(row.get(field)) is not int or not -1 <= row[field] <= 4096:
                raise ValueError("invalid read observation")
        head = row.get("raw_head")
        if not isinstance(head, list) or len(head) != 8 or any(
                type(value) is not int or not -(2**31) <= value < 2**31 for value in head):
            raise ValueError("invalid raw sample")
    return {"observations": data, "native_behavior_acceptance": "PENDING"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("stage").add_argument("--destination", required=True)
    commands.add_parser("ingest").add_argument("--receipt", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            stage(args.destination)
            print("staged disposable custody read probe; lead native run pending")
        else:
            print(json.dumps(ingest(args.receipt), sort_keys=True))
    except (OSError, ValueError):
        # Do not disclose runtime/profile paths in public worker output.
        parser.exit(1, "custody_read_probe: invalid input or filesystem failure\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
