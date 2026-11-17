"""Finite JSON extremes: tooling validation only, explicitly synthetic."""
import contextlib
import io
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'source'))
from tests.unit import test_interior_points as tp
from tools.audit import interior_points as pts
results=[]
for label in ('finite-overflow','tiny-grid'):
    doc=tp.full_census()
    row=doc['placements'][0]
    if label=='finite-overflow':
        row['hits'][0][0]=1e308
        row['box_min'][0]=-1e308
    else:
        row['grid']['step']=1e-320
    directory=HERE/label
    directory.mkdir(exist_ok=True)
    census=directory/'census.json'
    stock=directory/'stock.xml'
    output=directory/'treatment.xml'
    report=directory/'report.json'
    census.write_bytes(tp.encode(doc))
    stock.write_bytes(tp.STOCK)
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            code=pts.main(['--census',str(census),'--stock-proto',str(stock),'--output',str(output),'--report',str(report),'--min-calibration','0.4'])
        results.append({'probe':label,'exit':code,'report':report.exists(),'treatment':output.exists()})
    except Exception as e:
        results.append({'probe':label,'exception':type(e).__name__,'message':str(e),'has_report':hasattr(e,'report'),
                        'report':report.exists(),'treatment':output.exists()})
(HERE/'numeric-results.json').write_text(json.dumps(results,indent=2)+'\n')
for r in results: print(json.dumps(r))
