"""Independent lexical statement counter plus local cache API audit; no engine execution."""
from collections import Counter
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / 'baseline'))
from tools.setup import weather_probe as p, probe_runtime as rt
CACHE = Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
HERE = Path(__file__).resolve().parent
hook=p.render_hook().decode('ascii')
(HERE/'generated-hook.c').write_text(hook)
# Lexer blanks comments and string contents, preserving newlines. Braces are statement boundaries.
i=0; clean=[]
while i < len(hook):
    if hook.startswith('//',i):
        j=hook.find('\n',i); j=len(hook) if j<0 else j
        clean.extend(' '*(j-i)); i=j
    elif hook.startswith('/*',i):
        j=hook.index('*/',i+2)+2
        clean.extend('\n' if c=='\n' else ' ' for c in hook[i:j]); i=j
    elif hook[i]=='"':
        clean.append('"'); i+=1
        while i<len(hook):
            if hook[i]=='\\': clean.extend('  '); i+=2
            elif hook[i]=='"': clean.append('"'); i+=1; break
            else: clean.append('\n' if hook[i]=='\n' else ' '); i+=1
    else: clean.append(hook[i]); i+=1
clean=''.join(clean)
statements=[]; start=0
for m in re.finditer(r'[;{}]',clean):
    body=clean[start:m.start()]
    if body.strip():
        begin=start+len(body)-len(body.lstrip())
        statements.append((clean[:begin].count('\n')+1, body.strip(), body.count('+')))
    start=m.end()
plus=[(n,count) for n,body,count in statements if count]
print('independent statement plus counts (hook line, count):',plus)
print('independent maximum + operators:', max(x[2] for x in statements))
print('leading boolean operators:',re.findall(r'^\s*(?:\|\||&&).*',clean,re.M))
print('ternaries:',clean.count('?'))
print('Set* / weather mutator calls:',re.findall(r'\b(?:Set\w*|MissionWeather|SuppressLightningSimulation)\s*\(',clean))
native=rt.native_type_names(CACHE)
print('native type names:',len(native))
identifiers = re.findall(r'\b(?:int|float|bool|string|Weather|WeatherPhenomenon|FileHandle)\s+(\w+)',clean)
print('declared identifiers colliding with native types:',sorted(set(identifiers)&set(native)))
print('shared lint:',rt.lint_hook(hook,native_types=native))
print('local explicit-number/statement lint:',p.statement_problems(hook))
# All declarations, parameters and locals checked per method, including shadowing.
for m in re.finditer(r'(?:override\s+)?(?:void|string)\s+(\w+)\(([^)]*)\)\s*\{',clean):
    opening=clean.index('{',m.start()); depth=1; j=opening+1
    while depth:
        depth+=(clean[j]=='{')-(clean[j]=='}'); j+=1
    params=m.group(2); body=clean[opening+1:j-1]
    names=re.findall(r'\b(?:int|float|bool|string|Weather|WeatherPhenomenon|FileHandle)\s+(\w+)',params+';'+body)
    dup=[n for n,c in Counter(names).items() if c>1]
    print('method',m.group(1),'duplicate locals/params:',dup)
    assert not dup
print('API declarations from installed cache (not runtime evidence):')
citations=re.findall(r'^\s+(\S+?)\s+->\s+(\S+?):(\d+)',p.__doc__,re.M)
citations += [(a,'1_Core/proto/EnString.c',str(n)) for a,n in [('Substring',113),('Replace',156),('Length',199),('IndexOf',240)]]
citations += [('Print','1_Core/proto/EnDebug.c','96')]
for api,name,n in citations:
    line=(CACHE/name).read_text(errors='replace').splitlines()[int(n)-1].strip()
    assert api.split('.')[-1] in line,(api,name,n,line)
    print(f'{api} -> {name}:{n} {line}')
for api in ['GetLimits','GetForecastChangeLimits','GetForecastTimeLimits','GetDate','GetWorldName','GetVersion']:
    for m in re.finditer(r'\b'+api+r'\(([^)]*)\)',clean):
        args=[x.strip() for x in m.group(1).split(',')]
        assert all(re.search(r'\b(?:int|float|string)\s+'+re.escape(a)+r'\b',clean[:m.start()]) for a in args)
        print('declared-before-call out params:',api,args)
print('default span s:',(p.DEFAULT_SAMPLES-1)*p.DEFAULT_INTERVAL_S)
print('best effort: start=5s interval=5s samples=277 span s:',276*5,'cap ms:',p.cap_ms(5,277),'watchdog ms:',p.watchdog_ms(5,5,277),'launcher wait min:',p.worst_case_minutes(5,5,277))
inline='void F() { string s = "a"'+' + "b"'*27+'; }'
print('inline-brace 27-plus shared lint:',rt.lint_hook(inline))
print('inline-brace 27-plus weather local lint:',p.statement_problems(inline))
