import sys,struct,bisect
from capstone import *
from capstone.riscv import *
from elftools.elf.elffile import ELFFile
f=ELFFile(open(sys.argv[1],'rb')); data=open(sys.argv[1],'rb').read()
segs=[(s['p_vaddr'],s['p_offset'],s['p_filesz']) for s in f.iter_segments() if s['p_type']=='PT_LOAD' and s['p_filesz']]
def rd(a,n):
    for v,o,sz in segs:
        if v<=a<v+sz: return data[o+a-v:o+a-v+n]
    return None
syms={}
for s in f.get_section_by_name('.symtab').iter_symbols():
    if s.name and s['st_value'] and s['st_info']['type'] in('STT_FUNC','STT_OBJECT'): syms[s['st_value']]=(s.name,s['st_size'])
keys=sorted(syms)
def sym(a):
    i=bisect.bisect_right(keys,a)-1
    if i>=0:
        k=keys[i]; n,sz=syms[k]
        if a<k+max(sz,1): return n+('+%d'%(a-k) if a!=k else '')
    return None
lo,hi=int(sys.argv[2],16),int(sys.argv[3],16)
md=Cs(CS_ARCH_RISCV,CS_MODE_RISCV32|CS_MODE_RISCVC); md.detail=False; md.skipdata=True
code=rd(lo,hi-lo)
au={}
for i in md.disasm(code,lo):
    ann=''
    ops=i.op_str
    if i.mnemonic=='auipc':
        r,imm=ops.split(', '); au[r]=i.address+(int(imm,0)<<12)
    elif i.mnemonic in('addi','lw','flw','fsw','sw','lh','lhu','lb','lbu','sh','sb') and '(' in ops or i.mnemonic=='addi':
        try:
            if i.mnemonic=='addi':
                rd_,rs,imm=ops.split(', '); base=rs; off=int(imm,0)
            else:
                rd_,m=ops.split(', '); off=int(m.split('(')[0],0); base=m.split('(')[1].rstrip(')')
            if base in au:
                a=au[base]+off; s=sym(a)
                ann=' ; %x%s'%(a,(' '+s) if s else '')
                if i.mnemonic=='flw':
                    b=rd(a,4); 
                    if b: ann+=' =%g'%struct.unpack('<f',b)[0]
        except Exception as e: pass
    elif i.mnemonic in('jal','j') or i.mnemonic=='c.jal' or i.mnemonic=='c.j':
        try:
            t=int(ops.split(',')[-1].strip(),0); s=sym(t); ann=' ; '+(s or hex(t))
        except: pass
    print('%x: %s %s%s'%(i.address,i.mnemonic,ops,ann))
