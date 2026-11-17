"""Run changed tests against scratch copies; repository modules are never edited."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest
from tests.unit import test_flashlight_matrix as matrix_tests
from tests.unit import test_taped_light_probe as probe_tests
from tests.unit import test_taped_light_report as report_tests
from tools.setup import taped_light_probe as original_probe
from tools.audit import taped_light_report as original_report

root = Path(__file__).resolve().parent
mutants = [
    ('delete_never_executes', original_probe,
     'GetGame().ObjectDelete(releaseItem);', 'if (false) GetGame().ObjectDelete(releaseItem);'),
    ('watchdog_does_not_cleanup', original_probe,
     '        HCTLFinish("partial");', '        m_HCTLDone = true;'),
    ('census_scans_nothing', original_probe,
     'int scanLimit = nearObjects.Count();', 'int scanLimit = 0;'),
    ('create_attachment_arguments_reversed', original_probe,
     'CreateAttachmentEx(lightName, slotId)', 'CreateAttachmentEx(slotId, lightName)'),
    ('timeout_does_not_break', original_probe,
     '                m_HCTLClassTimedOut = true;\n                break;',
     '                m_HCTLClassTimedOut = true;'),
    ('found_type_guard_disabled', original_report,
     'if light_slot.get("found_type") != light:', 'if False:'),
]

for name, original, before, after in mutants:
    source = Path(original.__file__).read_text()
    assert source.count(before) == 1, (name, source.count(before))
    path = root / (name + '.py')
    path.write_text(source.replace(before, after))
    spec = importlib.util.spec_from_file_location('tools.setup.review_mutant' if original is original_probe
                                                 else 'tools.audit.review_mutant', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    probe_tests.probe = report_tests.probe = module if original is original_probe else original_probe
    report_tests.report = module if original is original_report else original_report
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                               for m in (matrix_tests, probe_tests, report_tests))
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        result = unittest.TextTestRunner(stream=log, verbosity=1).run(suite)
    (root / (name + '.log')).write_text(log.getvalue())
    print(f'{name}: {"SURVIVED" if result.wasSuccessful() else "KILLED"}; '
          f'ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}')
    for test, _ in result.failures + result.errors:
        print('  ' + str(test))
