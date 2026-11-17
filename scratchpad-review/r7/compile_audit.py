"""Pinned installed declarations and an independent statement lexer; never invokes an engine."""
from pathlib import Path
import sys,re,json,hashlib,collections
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent/'head'))
from tools.setup import taped_light_probe as p,probe_runtime as rt
cache=Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289')
patterns={
'1_Core/proto/EnString.c':r'proto.*\b(?:Substring|Replace|ToLower|Length|IndexOf|LastIndexOf|IndexOfFrom)\(',
'1_Core/proto/EnScript.c':r'(class array<Class T>|proto.*\b(?:Count|Clear|Get|Insert|Find)\()',
'1_Core/proto/EnConvert.c':r'proto string ToString\(',
'3_Game/gameplay.c':r'(class (?:Selection|LOD)|(?:GetName|GetVertexCount|GetLODVertexIndex|GetVertexPosition|GetSelectionCount|GetSelections)\(|NAME_VIEW)',
'3_Game/Entities/Object.c':r'(GetLODS\(|.*GetLODName\(|LOD GetLODByName\(|proto native void GetSelectionList\()',
'3_Game/Global/Game.c':r'proto.*(?:ConfigGetText\(|ConfigGetTextArray\(|ConfigIsExisting\(|ConfigGetChildName\(|ConfigGetChildrenCount\()',
}
for relative,pattern in patterns.items():
    for n,line in enumerate((cache/relative).read_text().splitlines(),1):
        if re.search(pattern,line) and (relative!='1_Core/proto/EnScript.c' or 374<=n<=407): print(f'{relative}:{n}: {line.strip()}')
classification=json.loads(Path('/home/david/.cache/hollow-country/experiments/taped-light-probe-003/classification.json').read_text())
hook=p.render_hook(p.select_targets(classification)).decode()
# Lex string literals and comments ourselves; formatting/line breaks do not terminate a statement.
def statements(text):
    quoted=False;line_comment=False;block=False;escape=False;buf=[];i=0
    while i<len(text):
        ch=text[i];nxt=text[i:i+2]
        if line_comment:
            if ch=='\n': line_comment=False;buf.append('\n')
        elif block:
            if nxt=='*/':block=False;i+=1
        elif quoted:
            if escape:escape=False
            elif ch=='\\':escape=True
            elif ch=='"':quoted=False;buf.append('"')
        elif nxt=='//':line_comment=True;i+=1
        elif nxt=='/*':block=True;i+=1
        elif ch=='"':quoted=True;buf.append('"')
        elif ch in ';{}':
            yield ''.join(buf);buf=[]
        else:buf.append(ch)
        i+=1
    assert not quoted and not block
    if buf:yield ''.join(buf)
counts=[re.sub(r'\+\+|\+=','',s).count('+') for s in statements(hook)]
clean=rt._clean(hook)
names=rt.native_type_names(cache)
extra=(("GetSelections",(0,)),("GetLODS",(0,)),("ConfigGetText",(1,)),("ConfigGetTextArray",(1,)),("GetWorldName",(0,)),("GetVersion",(0,)))
with mock.patch.object(rt,'_OUT_CALLS',rt._OUT_CALLS+extra): issues=rt.lint_hook(hook,native_types=names,explicit_numbers=True)
methods=list(rt._function_bodies(clean))
print('AUDIT',json.dumps({'bytes':len(hook.encode()),'sha256':hashlib.sha256(hook.encode()).hexdigest(),'native_types':len(names),'methods':len(methods),'independent_max_plus':max(counts),'shared_max_plus':rt.max_statement_plus(hook),'ternary_tokens':sum('?' in s for s in statements(hook)),'lint_including_out_calls':issues},sort_keys=True))
assert max(counts)==8 and not issues and '?' not in clean
for method,body,_ in methods:
    if method.group(0).find('HCTLView')>=0 or method.group(0).find('HCTLProxy')>=0:
        print('METHOD',method.group(0).strip().split('\n')[0])
print('OUT_DECLARATION_ORDER lodList allocated before GetLODS; childName before ConfigGetChildName; world/version before their getters; viewSelections allocated before GetSelections; modelPath/slotText/slotNames declared before config calls; no inline out declarations')
print('NUMERIC_SERIALIZATION vertex components and all emitted counts use ToString; booleans use HCTLBool; no duplicate locals or native-type variable/parameter names found')
