import struct,sys
from elftools.elf.elffile import ELFFile
from capstone import *
p=sys.argv[1]; lo=int(sys.argv[2],16); hi=int(sys.argv[3],16)
f=ELFFile(open(p,'rb')); d=open(p,'rb').read(); B=0x10000
ds=f.get_section_by_name('.dynsym'); rp=f.get_section_by_name('.rel.plt')
names={}
plt=f.get_section_by_name('.plt')['sh_addr']
for k,r in enumerate(rp.iter_relocations()):
    names[plt+20+12*k]=ds.get_symbol(r['r_info_sym']).name
md=Cs(CS_ARCH_ARM,CS_MODE_ARM); md.skipdata=True
def lit(a):
    try: return struct.unpack_from('<I',d,a-B)[0]
    except: return None
for i in md.disasm(d[lo-B:hi-B],lo):
    op=i.op_str
    if i.mnemonic in('bl','blx') or i.mnemonic.startswith('bl'):
        try:
            t=int(op.lstrip('#'),16); op+='  <'+names.get(t,'sub_%x'%t)+'>'
        except: pass
    if i.mnemonic.startswith('ldr') and 'pc' in op and '[' in op:
        try:
            disp=int(op.split('#')[1].rstrip(']!'),0); a=i.address+8+disp; v=lit(a)
            s=''
            if v and 0x40000<=v<0x45000 or 0x115000<=v<0x136000: s=d[v-B:v-B+50].split(b'\0')[0]
            op+='   ; [%x]=%s %s'%(a,hex(v) if v is not None else '?',s)
        except: pass
    print('%x: %s %s'%(i.address,i.mnemonic,op))
