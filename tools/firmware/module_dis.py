"""Дизассемблер ARM (32 бит) для .so модуля V831: подписи вызовов по символам и PLT. Использование: python -I module_dis.py LIB.so ИМЯ_ИЛИ_АДРЕС ..."""
import sys,struct
from elftools.elf.elffile import ELFFile
from capstone import *
from capstone.arm import ARM_OP_IMM
f=sys.argv[1]; d=open(f,'rb').read(); e=ELFFile(open(f,'rb'))
segs=[(s['p_vaddr'],s['p_offset'],s['p_filesz']) for s in e.iter_segments() if s['p_type']=='PT_LOAD']
def rd(a,n):
    for va,off,sz in segs:
        if va<=a<va+sz: return d[off+a-va:off+a-va+n]
syms={};dyn=e.get_section_by_name('.dynsym')
for s in dyn.iter_symbols():
    if s['st_shndx']!='SHN_UNDEF' and s.name: syms[s['st_value']&~1]=(s.name,s['st_size'])
byname={v[0]:k for k,v in syms.items()}
# plt imports
got={}
for sn in('.rel.plt','.rel.dyn'):
    r=e.get_section_by_name(sn)
    if r:
        for x in r.iter_relocations():
            if x['r_info_sym']: got[x['r_offset']]=dyn.get_symbol(x['r_info_sym']).name
md=Cs(CS_ARCH_ARM,CS_MODE_ARM); md.detail=True
plt={}
ps=e.get_section_by_name('.plt'); base=ps['sh_addr']; code=rd(base,ps['sh_size'])
# ARM PLT: entries 'add ip,pc,#0,12; add ip,ip,#x,20; ldr pc,[ip,#y]!' 12 bytes after 20-byte header
for a in range(base+20,base+ps['sh_size'],12):
    w=struct.unpack('<3I',rd(a,12))
    # compute target GOT slot
    def imm(w):
        v=w&0xff;r=((w>>8)&0xf)*2; return ((v>>r)|(v<<(32-r)))&0xffffffff if r else v
    g=a+8+imm(w[0])+imm(w[1])+(w[2]&0xfff)
    if g in got: plt[a]=got[g]
def sym(a):
    for k,(n,sz) in syms.items():
        if k<=a<k+max(sz,1): return n+('+%d'%(a-k) if a!=k else '')
def cstr(a):
    b=rd(a,100)
    if b:
        s=b.split(b'\0')[0]
        if len(s)>=2 and all(32<=c<127 for c in s): return s.decode()
for arg in sys.argv[2:]:
    a=byname.get(arg) or int(arg,16); n=syms.get(a,(arg,0x100))[1] or 0x100
    print('=====',arg,hex(a),n)
    code=rd(a,n); lit={}
    for i in md.disasm(code,a):
        ann=''
        if i.mnemonic in('bl','b') and i.operands and i.operands[0].type==ARM_OP_IMM:
            t=i.operands[0].imm; ann=' ; '+(plt.get(t) or sym(t) or hex(t))
        elif i.mnemonic=='ldr' and 'pc' in i.op_str and '#' in i.op_str:
            try:
                disp=int(i.op_str.split('#')[-1].rstrip(']!'),0)
                la=i.address+8+disp; v=struct.unpack('<I',rd(la,4))[0]
                s=cstr(v); sy=sym(v)
                ann=' ; =%#x %s'%(v,('"%s"'%s) if s else (sy or ''))
            except Exception: pass
        print('%x: %s %s%s'%(i.address,i.mnemonic,i.op_str,ann))
