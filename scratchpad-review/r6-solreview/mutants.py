"""Own source mutations, loaded in memory; tracked files are never edited."""
import contextlib
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock
HERE=Path(__file__).resolve().parent
SOURCE=HERE/'source'
sys.path.insert(0,str(SOURCE))
from tests.unit import test_interior_points as tp
from tests.unit import test_interior_sampler as ts

MUTANTS=[
 ('M1-ignore-invalid-door-rows','points','and doors["invalid_rows"] == 0','and True',tp.Round6DoorRunEvidenceTests,
  'test_one_bad_row_among_valid_rows_is_enough_to_refuse'),
 ('M2-ignore-restoration-count','points','if record["restored"] != opened:','if False:',tp.Round6DoorRunEvidenceTests,
  'test_contradictory_or_missing_door_runs_are_refused_as_door_semantics_unobserved'),
 ('M3-wanted-open-phase','sampler','if (m_HCProbeBuilding.IsDoorOpened(door))','if (m_HCProbeBuilding.IsDoorOpen(door))',ts.Round6DoorPhaseTests,
  'test_a_door_that_moves_slower_than_the_fixed_delay_is_waited_for_with_a_bounded_settle'),
 ('M4-omit-close','sampler','m_HCProbeBuilding.CloseDoor(m_HCProbeOpenedDoors.Get(index));','m_HCProbeDoorDelay = 0;',ts.Round5DoorRunTests,
  'test_closed_doors_are_opened_the_codes_are_recorded_again_and_the_doors_are_closed_again'),
 ('M5-accept-overflow','points','except OverflowError:\n        return False','except OverflowError:\n        return True',tp.Round6NumericOverflowTests,
  'test_an_oversized_integer_is_a_census_invalid_refusal_not_an_overflow'),
 ('M6-parse-exit-without-report','points','raise _UsageError(message)','raise SystemExit(2)',tp.Round6CliTests,
  'test_a_command_line_parse_failure_writes_a_refusal_report_when_the_report_path_is_safe'),
 ('M7-ignore-unobserved-open','sampler','if (observed < total)','if (false)',ts.Round6DoorPhaseTests,
  'test_an_open_that_never_completes_skips_the_open_pass_and_still_closes'),
]
# Resolve the exact numeric test name without guessing it.
MUTANTS[4]=(*MUTANTS[4][:-1],next(n for n in dir(tp.Round6NumericOverflowTests) if n.startswith('test_') and 'cli' not in n))
results=[]
for label,kind,old,new,case,method in MUTANTS:
    original=tp.pts if kind=='points' else ts.samp
    source=Path(original.__file__).read_text()
    assert source.count(old)==1,(label,source.count(old))
    mutated=source.replace(old,new)
    (HERE/(label+'.py')).write_text(mutated)
    module=types.ModuleType(original.__name__)
    module.__file__=original.__file__
    module.__package__=original.__package__
    exec(compile(mutated,module.__file__,'exec'),module.__dict__)
    stream=io.StringIO()
    target=tp if kind=='points' else ts
    attr='pts' if kind=='points' else 'samp'
    with mock.patch.object(target,attr,module),contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite([case(method)]))
    (HERE/(label+'.log')).write_text(stream.getvalue())
    record={'mutant':label,'test':case.__name__+'.'+method,'killed':not result.wasSuccessful(),
            'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}
    results.append(record)
    print(json.dumps(record))
(HERE/'mutants-results.json').write_text(json.dumps(results,indent=2)+'\n')
