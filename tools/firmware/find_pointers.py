import struct,sys
p=sys.argv[1]; lo=int(sys.argv[2]); hi=int(sys.argv[3])
d=open(p,'rb').read(); B=0x10000
for i in range(0,len(d)-3,4):
    v=struct.unpack_from('<I',d,i)[0]
    if B+lo<=v<B+hi:
        print(hex(B+i),hex(v),d[v-B:v-B+40].split(b'\0')[0])
