"""Rerun each earlier mutation against isolated fix-round modules and current tests."""
import importlib.util,sys,unittest,contextlib,io
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'head'))
import tempfile
tempfile.tempdir=str(ROOT/'tmp')
from tests.unit import test_flashlight_matrix as mt,test_taped_light_probe as pt,test_taped_light_report as rt
from tools.setup import taped_light_probe as p
from tools.audit import taped_light_report as r
mutants=[
('delete_never_executes',p,'GetGame().ObjectDelete(releaseItem);','if (false) GetGame().ObjectDelete(releaseItem);'),
('watchdog_does_not_cleanup',p,'        HCTLFinish("partial");','        m_HCTLDone = true;'),
('census_scans_nothing',p,'int scanLimit = m_HCTLCensusTotal;','int scanLimit = 0;'),
('create_attachment_arguments_reversed',p,'CreateAttachmentEx(lightName, slotId)','CreateAttachmentEx(slotId, lightName)'),
('timeout_does_not_break',p,'                m_HCTLClassTimedOut = true;\n                break;','                m_HCTLClassTimedOut = true;'),
('found_type_guard_disabled',r,'if attempt["found_type"] != light:','if False:'),
('handguard_untracked',p,'                m_HCTLLive.Insert(handguard);','                // removed by review mutation'),
('live_after_release_zeroed',p,'m_HCTLLiveAfterRelease = m_HCTLLiveAfterRelease + 1;','m_HCTLLiveAfterRelease = 0;'),
]
for name,original,before,after in mutants:
    src=Path(original.__file__).read_text()
    assert src.count(before)==1,(name,src.count(before))
    path=ROOT/(name+'.py');path.write_text(src.replace(before,after))
    spec=importlib.util.spec_from_file_location('tools.setup.review_mutant' if original is p else 'tools.audit.review_mutant',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pt.probe=rt.probe=module if original is p else p
    rt.report=module if original is r else r
    log=io.StringIO()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (mt,pt,rt))
    with contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        result=unittest.TextTestRunner(stream=log,verbosity=1).run(suite)
    (ROOT/(name+'.log')).write_text(log.getvalue())
    print(f'{name}: {"SURVIVED" if result.wasSuccessful() else "KILLED"}; ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}')
    for test,_ in result.failures+result.errors:print('  '+str(test))
