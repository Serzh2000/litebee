"""Дизассемблер ARM64 для .so из APK: подписывает вызовы по символам и импортам PLT, строки и данные по adrp/add/ldr.

Использование: python -I arm64_disasm.py <файл.so> <имя функции или адрес> [<имя или адрес> ...]
Нужны capstone и pyelftools.
"""
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from capstone.arm64 import ARM64_OP_IMM, ARM64_OP_REG, ARM64_OP_MEM
from elftools.elf.elffile import ELFFile

path = sys.argv[1]
data = open(path, "rb").read()
elf = ELFFile(open(path, "rb"))

segs = [(s["p_vaddr"], s["p_offset"], s["p_filesz"]) for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]


def rd(addr, n):
    for va, off, sz in segs:
        if va <= addr < va + sz:
            return data[off + addr - va: off + addr - va + n]
    return None


syms = {}
for sec in (".dynsym", ".symtab"):
    t = elf.get_section_by_name(sec)
    if t:
        for s in t.iter_symbols():
            if s["st_shndx"] != "SHN_UNDEF" and s.name and s["st_info"]["type"] in ("STT_FUNC", "STT_OBJECT"):
                syms[s["st_value"]] = (s.name, s["st_size"])
by_name = {v[0]: k for k, v in syms.items()}

# PLT: адрес заглушки -> имя импорта
got = {}
dynsym = elf.get_section_by_name(".dynsym")
for secname in (".rela.plt", ".rela.dyn"):
    rel = elf.get_section_by_name(secname)
    if rel:
        for r in rel.iter_relocations():
            if r["r_info_sym"]:
                got[r["r_offset"]] = dynsym.get_symbol(r["r_info_sym"]).name
md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True
plt = {}
plt_sec = elf.get_section_by_name(".plt")
if plt_sec:
    base, size = plt_sec["sh_addr"], plt_sec["sh_size"]
    code = rd(base, size)
    regs = {}
    for i in md.disasm(code, base):
        if i.mnemonic == "adrp":
            regs[i.operands[0].reg] = i.operands[1].imm
        elif i.mnemonic == "ldr" and i.operands[1].type == ARM64_OP_MEM and i.operands[1].mem.base in regs:
            g = regs[i.operands[1].mem.base] + i.operands[1].mem.disp
            if g in got:
                # заглушка начинается на 2 команды раньше (adrp, ldr, add, br)
                plt[i.address - 4] = got[g]


def sym(a):
    best = None
    for k, (n, sz) in syms.items():
        if k <= a < k + max(sz, 1):
            best = n + ("+%d" % (a - k) if a != k else "")
    return best


def cstr(a):
    b = rd(a, 80)
    if not b:
        return None
    s = b.split(b"\0")[0]
    if len(s) >= 3 and all(32 <= c < 127 for c in s):
        return s.decode()
    return None


def disasm(lo, hi, name=""):
    print("=== %s %x..%x" % (name, lo, hi))
    code = rd(lo, hi - lo)
    adrp = {}
    for i in md.disasm(code, lo):
        ann = ""
        ops = i.op_str
        if i.mnemonic == "adrp":
            adrp[i.operands[0].reg] = i.operands[1].imm
        elif i.mnemonic in ("add",) and len(i.operands) == 3 and i.operands[1].type == ARM64_OP_REG and i.operands[1].reg in adrp and i.operands[2].type == ARM64_OP_IMM:
            a = adrp[i.operands[1].reg] + i.operands[2].imm
            adrp[i.operands[0].reg] = a
            s = cstr(a)
            ann = " ; %x%s" % (a, (' "%s"' % s) if s else (" " + sym(a) if sym(a) else ""))
        elif i.mnemonic.startswith("ldr") and i.operands and i.operands[-1].type == ARM64_OP_MEM and i.operands[-1].mem.base in adrp:
            a = adrp[i.operands[-1].mem.base] + i.operands[-1].mem.disp
            b = rd(a, 8)
            extra = ""
            if b and i.mnemonic in ("ldr",) and len(b) >= 4:
                extra = " =%#x" % struct.unpack("<I", b[:4])[0]
            ann = " ; [%x] %s%s" % (a, sym(a) or "", extra)
        elif i.mnemonic in ("bl", "b") and i.operands and i.operands[0].type == ARM64_OP_IMM:
            t = i.operands[0].imm
            ann = " ; " + (plt.get(t) or sym(t) or hex(t))
        print("%x: %s %s%s" % (i.address, i.mnemonic, ops, ann))


for arg in sys.argv[2:]:
    if arg in by_name:
        a = by_name[arg]
        disasm(a, a + syms[a][1], arg)
    else:
        a = int(arg, 16)
        disasm(a, a + 0x80, arg)
