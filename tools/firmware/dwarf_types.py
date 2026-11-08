import sys
from elftools.elf.elffile import ELFFile
f=ELFFile(open(__import__('os').environ.get('ELF','melis30_1.5.elf'),'rb')); dw=f.get_dwarf_info()
want=sys.argv[1:]
LIBC=('_','__','tm','sbuf','reent')
def nm(d):
    a=d.attributes.get('DW_AT_name'); return a.value.decode() if a else None
def tyname(cu,d):
    t=d.attributes.get('DW_AT_type')
    if not t: return 'void'
    td=cu.get_DIE_from_refaddr(t.value+cu.cu_offset) if t.form!='DW_FORM_ref_addr' else cu.get_DIE_from_refaddr(t.value)
    if td.tag=='DW_TAG_pointer_type': return tyname(cu,td)+'*'
    if td.tag=='DW_TAG_array_type':
        n=tyname(cu,td)
        for c in td.iter_children():
            if c.tag=='DW_TAG_subrange_type':
                ub=c.attributes.get('DW_AT_upper_bound'); n+='[%s]'%((ub.value+1) if ub else '')
        return n
    if td.tag in('DW_TAG_const_type','DW_TAG_volatile_type'): return tyname(cu,td)
    return nm(td) or td.tag.replace('DW_TAG_','')
seen=set()
for cu in dw.iter_CUs():
    top=cu.get_top_DIE(); n=nm(top) or ''
    if not any(w in n for w in want): continue
    print('=== CU',n.split('/src/')[-1])
    for d in cu.iter_DIEs():
        if d.tag in('DW_TAG_structure_type','DW_TAG_union_type') and nm(d) and not nm(d).startswith('_') and d.attributes.get('DW_AT_byte_size'):
            key=(nm(d),n)
            print(d.tag[7:-5],nm(d),'size',d.attributes['DW_AT_byte_size'].value)
            for c in d.iter_children():
                if c.tag=='DW_TAG_member':
                    off=c.attributes.get('DW_AT_data_member_location'); off=('' if off is None else (off.value[-1] if isinstance(off.value,list) and off.value else off.value))
                    bs=c.attributes.get('DW_AT_bit_size')
                    print('   +%s %s %s%s'%(off,tyname(cu,c),nm(c),(':%d'%bs.value) if bs else ''))
        elif d.tag=='DW_TAG_enumeration_type':
            es=[(nm(c),c.attributes['DW_AT_const_value'].value) for c in d.iter_children() if c.tag=='DW_TAG_enumerator']
            if es and not any(e[0].startswith(('_','E')) for e in es[:1]): print('enum',nm(d) or '',' '.join('%s=%s'%e for e in es))
        elif d.tag=='DW_TAG_subprogram' and nm(d) and 'DW_AT_low_pc' in d.attributes:
            params=[tyname(cu,c)+' '+(nm(c) or '') for c in d.iter_children() if c.tag=='DW_TAG_formal_parameter']
            print('func %s %s(%s) @%x'%(tyname(cu,d),nm(d),', '.join(params),d.attributes['DW_AT_low_pc'].value))
