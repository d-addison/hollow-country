"""Token-based independent audit of the actual generated hook, independent of shared lint."""
import re,sys,collections
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.setup import interior_sampler as s,ce_probe
from tests.unit import test_interior_sampler as f
text=Path(sys.argv[1]).read_text() if len(sys.argv)>1 else s.render_hook(f.sampler_targets()).decode('ascii')
if len(sys.argv)==1:Path(__file__).with_name('generated-hook.c').write_text(text)
# Preserve line offsets and remove lexical strings/comments before tokenizing. Formatting is irrelevant.
lex=re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\+\+|\+=|&&|\|\||[A-Za-z_]\w*|[^\s]')
tokens=[]
for m in lex.finditer(text):
 v=m.group()
 if v.startswith(('//','/*')):continue
 tokens.append(('STRING' if v.startswith('"') else v,text.count('\n',0,m.start())+1))
statements=[];cur=[]
for token in tokens:
 if token[0] in '{};':
  if cur: statements.append(cur)
  cur=[]
 else:cur.append(token)
counts=[(sum(v=='+' for v,l in x),x[0][1]) for x in statements]
print('Targets:',len(f.sampler_targets()),'statements:',len(statements),'maximum binary plus:',max(x[0] for x in counts))
print('Statements with 8 plus (generated lines):',[line for count,line in counts if count==8])
print('Statements over 8:',[(n,l) for n,l in counts if n>8])
print('Leading boolean operators:',[(i,l) for i,l in enumerate(text.splitlines(),1) if l.lstrip().startswith(('||','&&'))])
print('Ternary tokens:',[(v,l) for v,l in tokens if v=='?'])
# Class-depth method scanner; indentation and same-line braces do not affect it.
functions=[];depth=0;i=0
while i<len(tokens):
 v,line=tokens[i]
 if v=='{' and depth==1 and i and tokens[i-1][0]==')':
  j=i-2;pd=1
  while pd:
   if tokens[j][0]==')':pd+=1
   if tokens[j][0]=='(':pd-=1
   j-=1
  name=tokens[j][0];params=tokens[j+2:i-1]
  k=i+1;bd=1
  while bd:
   if tokens[k][0]=='{':bd+=1
   if tokens[k][0]=='}':bd-=1
   k+=1
  functions.append((name,params,tokens[i+1:k-1]))
 if v=='{':depth+=1
 if v=='}':depth-=1
 i+=1
native=ce_probe.native_type_names(Path('/home/david/.cache/hollow-country/native-scripts/scripts-1.30.164289'))
types=native|{'int','float','vector','string','bool','FileHandle','TVectorArray','array','set'}
def declarations(ts):
 out=[]
 for i,(v,line) in enumerate(ts):
  if v not in types:continue
  if i and ts[i-1][0] in ('.','new'):continue
  j=i+1
  if j<len(ts) and ts[j][0]=='<':
   while j<len(ts) and ts[j][0]!='>':j+=1
   j+=1
  if j+1<len(ts) and re.fullmatch(r'[A-Za-z_]\w*',ts[j][0]) and ts[j+1][0] in ('=',',',';',')','['):
   out.append((ts[j][0],line,i))
 return out
duplicates=[];collisions=[]
for name,params,body in functions:
 ds=declarations(params+[(';',0)]+body)
 for n,c in collections.Counter(x[0] for x in ds).items():
  if c>1:duplicates.append((name,n,c))
 collisions.extend((name,n,line) for n,line,i in ds if n in native)
print('Methods checked:',len(functions),'duplicate local/parameter names:',duplicates,'native type name collisions:',collisions)
# Explicitly inspect every out-call argument and declaration ordering.
out_calls={'RaycastRV':[2,3,4],'SampleNavmeshPosition':[3],'FindPath':[3],'ClippingInfo':[0],
 'GetObjectsAtPosition3D':[2,3],'GetWorldName':[0],'GetVersion':[0]}
for name,params,body in functions:
 ds=declarations(body)
 for i,(v,line) in enumerate(body):
  if v not in out_calls or i+1>=len(body) or body[i+1][0]!='(':continue
  args=[];arg=[];d=0
  for tok in body[i+2:]:
   if tok[0]==')' and d==0:
    args.append(arg);break
   if tok[0]==',' and d==0:args.append(arg);arg=[];continue
   if tok[0] in ('(','['):d+=1
   if tok[0] in (')',']'):d-=1
   arg.append(tok[0])
  checks=[]
  for ix in out_calls[v]:
   a=''.join(args[ix]);ok=any(n==a and pos<i for n,l,pos in ds)
   checks.append((a,ok))
  print('Out call:',name,v,'line',line,checks)
print('Numeric JSON: HCProbeInt/HCProbeNum each return value.ToString(); strict-string behavioral suite is also run.')
print('External calls:',sorted(set(v for i,(v,l) in enumerate(tokens[:-1]) if tokens[i+1][0]=='(' and v not in {'if','for','while','switch'} and re.fullmatch(r'[A-Za-z_]\w*',v) and not v.startswith('HCProbe'))))
