import sys,collections
from elftools.elf.elffile import ELFFile
f=ELFFile(open(__import__('os').environ.get('ELF','melis30_1.5.elf'),'rb')); dw=f.get_dwarf_info()
rows=[]
for cu in dw.iter_CUs():
    top=cu.get_top_DIE(); a=top.attributes.get('DW_AT_name'); n=a.value.decode() if a else '?'
    nf=sum(1 for d in cu.iter_DIEs() if d.tag=='DW_TAG_subprogram' and 'DW_AT_low_pc' in d.attributes)
    rows.append((n,nf))
print(len(rows))
grp=collections.defaultdict(list)
for n,nf in rows:
    k=n.split('/src/')[1].rsplit('/',1)[0] if '/src/' in n else n.rsplit('/',1)[0] if '/' in n else '.'
    grp[k].append((n.rsplit('/',1)[-1],nf))
for k in sorted(grp): print(k, sum(x for _,x in grp[k]), ' '.join('%s(%d)'%t for t in grp[k]))
