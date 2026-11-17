"""Local bounded packed-config inspection; no installed content copied to repo."""
from pathlib import Path
import struct, hashlib, json

def entry(pbo, wanted):
    b=pbo.read_bytes();i=0;entries=[]
    while True:
        e=b.index(0,i); name=b[i:e].decode();i=e+1
        meta=struct.unpack_from('<5I',b,i);i+=20
        if not name and meta[0]:
            while b[i]: i=b.index(0,b.index(0,i)+1)+1
            i+=1
        elif not name:break
        else:entries.append((name,meta))
    for name,meta in entries:
        if name.lower()==wanted.lower():
            assert meta[0]==0
            return b[i:i+meta[4]]
        i+=meta[4]
    raise ValueError(wanted)

class RAP:
    def __init__(self,b):self.b=b;self.i=16;assert b[:4]==b'\0raP'
    def s(self):
        e=self.b.index(0,self.i);v=self.b[self.i:e].decode();self.i=e+1;return v
    def byte(self):v=self.b[self.i];self.i+=1;return v
    def num(self,fmt='<I'):v=struct.unpack_from(fmt,self.b,self.i)[0];self.i+=4;return v
    def count(self):
        v=0
        for shift in range(0,35,7):
            n=self.byte();v|=(n&127)<<shift
            if n<128:return v
        raise ValueError('count')
    def val(self,t):
        if t==0:return self.s()
        if t==1:return self.num('<f')
        if t==2:return self.num('<i')
        if t==3:return self.array()
        raise ValueError(('value',t,self.i))
    def array(self):
        n=self.count();assert n<8192
        return [self.val(self.byte()) for _ in range(n)]
    def body(self,at):
        self.i=at;parent=self.s();n=self.count();fields={};children={};assert n<8192
        for _ in range(n):
            t=self.byte()
            if t==0:
                name=self.s();offset=self.num();children[name]=offset
            elif t==1:
                subtype=self.byte();name=self.s();fields[name]=self.val(subtype)
            elif t==2:
                name=self.s();fields[name]=self.array()
            elif t in (3,4):self.s()
            else:raise ValueError(('entry',t,self.i))
        return parent,fields,children

if __name__=='__main__':
    output=[]
    for pbo,prefix in [('characters_gloves.pbo','LeatherGloves_'),('characters_headgear.pbo','LeatherHat_')]:
        b=entry(Path.home()/'.cache/hollow-country/wine-server-20261116/addons'/pbo,'config.bin')
        r=RAP(b);root=r.body(16);vehicles=r.body(root[2]['CfgVehicles'])
        for name,at in vehicles[2].items():
            if not name.startswith(prefix):continue
            parent,fields,children=r.body(at)
            output.append(dict(pbo=pbo,sha256=hashlib.sha256(b).hexdigest(),name=name,offset=at,parent=parent,fields=fields))
    Path('scratchpad-review/v1-crafting-r2/config-evidence.json').write_text(json.dumps(output,indent=2))
    for x in output:print(x['name'],x['offset'],x['fields'])
