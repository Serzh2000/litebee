import sys
from elftools.elf.elffile import ELFFile
f=ELFFile(open(__import__('os').environ.get('ELF','melis30_1.5.elf'),'rb')); dw=f.get_dwarf_info()
want=set(sys.argv[1:])
def nm(d):
    a=d.attributes.get('DW_AT_name'); return a.value.decode() if a else None
def ref(cu,d):
    t=d.attributes.get('DW_AT_type')
    if not t: return None
    return cu.get_DIE_from_refaddr(t.value+cu.cu_offset)
def tname(cu,d):
    if d is None: return 'void'
    if d.tag=='DW_TAG_pointer_type': return tname(cu,ref(cu,d))+'*'
    if d.tag in('DW_TAG_const_type','DW_TAG_volatile_type'): return tname(cu,ref(cu,d))
    if d.tag=='DW_TAG_array_type':
        n=tname(cu,ref(cu,d))
        for c in d.iter_children():
            if c.tag=='DW_TAG_subrange_type':
                ub=c.attributes.get('DW_AT_upper_bound'); n+='[%s]'%((ub.value+1) if ub else '')
        return n
    return nm(d) or d.tag[7:]
done=set()
def dump(cu,s,ind=''):
    for c in s.iter_children():
        if c.tag=='DW_TAG_member':
            off=c.attributes.get('DW_AT_data_member_location'); off=off.value if off else ''
            bs=c.attributes.get('DW_AT_bit_size')
            t=ref(cu,c); 
            print('%s+%s %s %s%s'%(ind,off,tname(cu,t),nm(c),(':%d'%bs.value) if bs else ''))
            tt=t
            while tt is not None and tt.tag in('DW_TAG_typedef','DW_TAG_const_type'): tt=ref(cu,tt)
            if tt is not None and tt.tag in('DW_TAG_structure_type','DW_TAG_union_type') and not nm(tt) and ind=='':
                dump(cu,tt,'      ')
for cu in dw.iter_CUs():
    for d in cu.iter_DIEs():
        if d.tag=='DW_TAG_typedef' and nm(d) in want and nm(d) not in done:
            done.add(nm(d)); t=ref(cu,d)
            while t is not None and t.tag=='DW_TAG_typedef': t=ref(cu,t)
            if t is None: continue
            if t.tag in('DW_TAG_structure_type','DW_TAG_union_type'):
                print('typedef struct',nm(d),'size',t.attributes.get('DW_AT_byte_size').value); dump(cu,t)
            elif t.tag=='DW_TAG_enumeration_type':
                print('typedef enum',nm(d),' '.join('%s=%s'%(nm(c),c.attributes['DW_AT_const_value'].value) for c in t.iter_children()))
