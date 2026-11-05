from loguru import logger; logger.disable("androguard")
import re,sys
from androguard.core.dex import DEX
d=DEX(open(__import__('os').environ.get('DEX','classes.dex'),'rb').read())
cls=sys.argv[1]
for c in d.get_classes():
    if c.get_name()!=cls: continue
    for m in c.get_methods():
        code=m.get_code()
        if not code or m.get_name() in ('crc16','<clinit>','<init>'): continue
        nreg=code.get_registers_size(); nin=code.get_ins_size()
        params={nreg-nin+i:'P%d'%i for i in range(nin)}
        reg=dict(); arrs={}  # reg -> expr
        out={}
        for ins in code.get_bc().get_instructions():
            n=ins.get_name(); o=ins.get_output()
            R=re.findall(r'v(\d+)',o)
            def val(r): 
                r=int(r); return reg.get(r, params.get(r,'v%d'%r))
            if n.startswith('const'):
                m2=re.match(r'v(\d+), (-?\d+)',o)
                if m2: reg[int(m2.group(1))]=int(m2.group(2))
            elif n=='new-array':
                reg[int(R[0])]='ARR'
            elif n.startswith('move-result') or n.startswith('invoke'):
                if 'ID_SRC' in o or 'byteValue' in o: pass
            elif n.startswith('sget-object') and 'ID_SRC' in o:
                reg[int(R[0])]='SRC'
            elif n=='move-result':
                pass
            elif n in ('int-to-byte','int-to-short','move','move-object') and len(R)>=2:
                reg[int(R[0])]=val(R[1])
            elif n.startswith('and-int') and len(R)>=2:
                lit=re.search(r', (\d+)$',o)
                reg[int(R[0])]='(%s&%s)'%(val(R[1]),lit.group(1) if lit else val(R[2]) if len(R)>2 else '?')
            elif n.startswith('shr-int') and len(R)>=2:
                lit=re.search(r', (\d+)$',o)
                reg[int(R[0])]='(%s>>%s)'%(val(R[0]) if n.endswith('2addr') else val(R[1]),lit.group(1) if lit else val(R[2]) if len(R)>2 else '?')
            elif n=='aput-byte':
                v,a,i=R[0],R[1],R[2]
                out[val(i) if isinstance(val(i),int) else int(i)]=val(v)
            elif n.startswith('add-int/lit') and len(R)>=2:
                lit=re.search(r', (-?\d+)$',o); 
                x=val(R[1]); reg[int(R[0])]=x+int(lit.group(1)) if isinstance(x,int) else '(%s+%s)'%(x,lit.group(1))
            elif n.startswith('mul-int') and len(R)>=2:
                lit=re.search(r', (-?\d+)$',o); x=val(R[1])
                reg[int(R[0])]=x*int(lit.group(1)) if isinstance(x,int) and lit else '(%s*%s)'%(x,lit.group(1) if lit else '?')
        keys=sorted(k for k in out if isinstance(k,int))
        if keys:
            body=' '.join('[%d]=%s'%(k,out[k]) for k in keys)
            print('%-18s %s'%(m.get_name()+m.get_descriptor().split(')')[0]+')',body[:420]))
