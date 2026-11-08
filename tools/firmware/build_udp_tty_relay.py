"""Собирает крошечную программу для дрона (ARM, Linux, без библиотек): принимает UDP-пакеты и пишет их в /dev/ttyS0.

На дроне нет ни nc, ни python, ни компилятора, а нужно донести кадры зуммера с компьютера по Wi-Fi до линии к модулю.
Программа короткая (около 250 байт), собрана вручную по одной машинной команде и проверяется дизассемблером capstone.

Использование:
    python -I build_udp_tty_relay.py <выходной файл> [порт UDP, по умолчанию 5555]
Дальше (на дроне по ADB):
    adb push <файл> /tmp/relay && adb shell chmod 755 /tmp/relay && adb shell "/tmp/relay &"
Что делает программа: слушает UDP-порт, пакеты короче 4 байт и не начинающиеся с AD FA выбрасывает, остальные пишет в /dev/ttyS0 как есть.
Останавливается командой kill (живёт только в оперативной памяти дрона, флеш не трогает). Запрещённые в сети без доверия: любой в Wi-Fi может слать кадры.
"""
import struct
import sys

BASE = 0x10000


def mov(rd, imm):          # mov rd, #imm8
    assert 0 <= imm < 256
    return 0xE3A00000 | (rd << 12) | imm


def movw(rd, imm):
    return 0xE3000000 | ((imm >> 12) << 16) | (rd << 12) | (imm & 0xFFF)


def movt(rd, imm):
    return 0xE3400000 | ((imm >> 12) << 16) | (rd << 12) | (imm & 0xFFF)


def movr(rd, rm):
    return 0xE1A00000 | (rd << 12) | rm


def svc():
    return 0xEF000000


def str_sp(rt, off):
    return 0xE58D0000 | (rt << 12) | off


def ldrb_sp(rt, off):
    return 0xE5DD0000 | (rt << 12) | off


def add_sp(rd, imm):
    assert imm < 256
    return 0xE28D0000 | (rd << 12) | imm


def cmp_imm(rn, imm):
    return 0xE3500000 | (rn << 16) | imm


SUB_SP_0x100 = 0xE24DDC01                      # sub sp, sp, #0x100
ORR_R1_0x100 = 0xE3811C01                       # orr r1, r1, #0x100  (O_NOCTTY)


def branch(cond, cur, target):
    off = (target - (cur + 2)) & 0xFFFFFF
    return (cond << 28) | 0x0A000000 | off


AL, NE, LT = 0xE, 0x1, 0xB


def build(port=5555):
    hi, lo = (port >> 8) & 0xFF, port & 0xFF
    code = []
    code += [movw(7, 281), mov(0, 2), mov(1, 2), mov(2, 0), svc(), movr(8, 0)]       # r8 = socket(AF_INET, SOCK_DGRAM, 0)
    code += [SUB_SP_0x100, mov(0, 0), str_sp(0, 0), str_sp(0, 4), str_sp(0, 8), str_sp(0, 12)]
    code += [movw(1, 0x0002), movt(1, (lo << 8) | hi), str_sp(1, 0)]                  # sockaddr_in: family 2, порт, адрес 0.0.0.0
    code += [movw(7, 282), movr(0, 8), movr(1, 13), mov(2, 16), svc()]                 # bind(r8, sp, 16)
    path_at = len(code)
    code += [mov(7, 5), 0, mov(1, 1), ORR_R1_0x100, mov(2, 0), svc(), movr(9, 0)]      # r9 = open("/dev/ttyS0", O_WRONLY|O_NOCTTY); [1] заполним ниже
    loop = len(code)
    code += [movw(7, 292), movr(0, 8), add_sp(1, 0x20), mov(2, 0x40), mov(3, 0), mov(4, 0), mov(5, 0), svc()]   # recvfrom(r8, sp+0x20, 64, 0, 0, 0)
    code += [cmp_imm(0, 4)]
    code += [branch(LT, len(code), loop)]
    code += [ldrb_sp(1, 0x20), cmp_imm(1, 0xAD)]
    code += [branch(NE, len(code), loop)]
    code += [ldrb_sp(1, 0x21), cmp_imm(1, 0xFA)]
    code += [branch(NE, len(code), loop)]
    code += [movr(2, 0), movr(0, 9), add_sp(1, 0x20), mov(7, 4), svc()]                 # write(r9, sp+0x20, n)
    code += [branch(AL, len(code), loop)]
    path = b"/dev/ttyS0\x00"
    # add r0, pc, #off: адрес строки сразу после кода
    cur = path_at + 1
    str_off = (len(code) - cur) * 4 - 8
    assert 0 <= str_off < 256
    code[path_at + 1] = 0xE28F0000 | (0 << 12) | str_off
    body = b"".join(struct.pack("<I", w) for w in code) + path
    body += b"\x00" * (-len(body) % 4)
    header_size = 52 + 32
    total = header_size + len(body)
    ehdr = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\x00" * 8
    ehdr += struct.pack("<HHIIIIIHHHHHH", 2, 40, 1, BASE + header_size, 52, 0, 0x05000000, 52, 32, 1, 0, 0, 0)
    phdr = struct.pack("<IIIIIIII", 1, 0, BASE, BASE, total, total, 7, 0x1000)
    return ehdr + phdr + body, header_size


if __name__ == "__main__":
    out = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5555
    image, hdr = build(port)
    open(out, "wb").write(image)
    print(f"{out}: {len(image)} байт, UDP-порт {port}")
