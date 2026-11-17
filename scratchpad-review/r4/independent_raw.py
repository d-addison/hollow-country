"""Independent stdlib reading of native files. Does not import the report or its fixtures."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

for variant in ('stock', 'candidate'):
    root = Path('/mnt/d/HollowCountryLocal/weather-probe-001-' + variant)
    path = root / 'profiles/HCWeatherProbe/observations.json'
    raw = path.read_bytes()
    cached = Path.home() / '.cache/hollow-country/experiments' / root.name / 'observations.json'
    rows = [json.loads(line) for line in raw.decode().splitlines()]
    samples = [r for r in rows if r['type'] == 'sample']
    tree = ET.fromstring((root / 'mpmissions/dayzOffline.chernarusplus/cfgweather.xml').read_bytes())
    print(variant, json.dumps(dict(header=rows[0], end=rows[-1], samples=len(samples),
          seq_contiguous=[s['seq'] for s in samples] == list(range(241)),
          game_ms_step_range=[min(b['game_ms']-a['game_ms'] for a,b in zip(samples,samples[1:])),
                              max(b['game_ms']-a['game_ms'] for a,b in zip(samples,samples[1:]))],
          mission_weather=sorted({s['mission_weather'] for s in samples}),
          update_frozen=sorted({s['update_frozen'] for s in samples}), xml_flags=tree.attrib,
          cache_matches=raw == cached.read_bytes() if cached.exists() else 'cache path absent',
          sha256=hashlib.sha256(raw).hexdigest())))
    exponent_values=[v for s in samples for p in s['phenomena'].values() for v in p.values()
                     if isinstance(v,str) and 'e' in v.lower()]
    print('  exponent_strings:', len(exponent_values), 'examples:', exponent_values[:5])
    for name in ('fog','overcast'):
        node=tree.find(name)
        current={k:float(v) for k,v in node.find('current').attrib.items()}
        first=samples[0]['phenomena'][name]
        limits=tuple(float(node.find('limits').get(k)) for k in ('min','max'))
        def outside(value):
            return value < limits[0]-.001 or value > limits[1]+.001
        values=[float(s['phenomena'][name]['actual']) for s in samples]
        target=current['actual']
        reached=next((s for s in samples if abs(float(s['phenomena'][name]['actual'])-target)<=.001),None)
        forecast_changes=[s['seq'] for a,s in zip(samples,samples[1:])
                          if abs(float(s['phenomena'][name]['forecast'])-float(a['phenomena'][name]['forecast']))>.001]
        initial_end=forecast_changes[0] if forecast_changes else len(samples)
        initial_countdown_residuals=[float(s['phenomena'][name]['next_change']) -
                                   (current['time']+current['duration']-float(s['weather_time']))
                                   for s in samples[:initial_end]]
        print(' ', name, json.dumps(dict(current=current, xml_limits=limits, seq0=first,
              actual_range=[min(values),max(values)], raw_actual_outside=sum(map(outside,values)),
              first_forecast_equals_current=float(first['forecast'])==target,
              first_countdown_residual=initial_countdown_residuals[0],
              initial_countdown_residual_range=[min(initial_countdown_residuals),max(initial_countdown_residuals)],
              reached=None if reached is None else [reached['seq'],reached['weather_time'],reached['phenomena'][name]['actual']],
              first_forecast_change=None if not forecast_changes else [forecast_changes[0],samples[forecast_changes[0]]['weather_time']],
              forecast_change_count=len(forecast_changes),
              forecasts_outside_count=sum(outside(float(s['phenomena'][name]['forecast'])) for s in samples),
              actual_outside_after_target=None if reached is None else
              [s['seq'] for s in samples[reached['seq']:] if outside(float(s['phenomena'][name]['actual']))],
              all_live_limits=sorted({tuple(float(s['phenomena'][name][k]) for k in ('limit_min','limit_max','time_min','time_max')) for s in samples}),
              last_pre_target=None if reached is None or reached['seq']==0 else
              [samples[reached['seq']-1]['weather_time'], samples[reached['seq']-1]['phenomena'][name]['actual']])))
