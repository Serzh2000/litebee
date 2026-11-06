"""Запускается НА модуле (python3 через adb shell): читает из памяти процесса app_ckh831 последний отправленный кадр (22 байта, global_packet_openmv, смещение 0x17e658 в libmaix_ckh831.so). Только чтение."""
import os,time,binascii
def findpid():
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                if "app_ckh831" in open("/proc/"+p+"/cmdline").read(): return int(p)
            except Exception: pass
pid=findpid(); print("pid",pid)
base=[int(l.split("-")[0],16) for l in open("/proc/%d/maps"%pid) if "libmaix_ckh831.so" in l][0]
f=open("/proc/%d/mem"%pid,"rb",0)
seen=set();t=time.time()
while time.time()-t<12:
    f.seek(base+0x17e658); b=f.read(22)
    key=bytes(b[:18])
    if key not in seen and len(seen)<25:
        seen.add(key); print(binascii.hexlify(b).decode())
    time.sleep(0.05)
