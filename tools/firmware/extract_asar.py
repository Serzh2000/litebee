import sys,json,struct,os
p,out=sys.argv[1],sys.argv[2]
f=open(p,'rb')
hdr=f.read(16)
_,_,_,jlen=struct.unpack('<IIII',hdr)
j=json.loads(f.read(jlen))
base=16+jlen
base=(base+3)//4*4 if False else base
# header size field: second uint = header size incl; data starts at 8 + header_size
hs=struct.unpack('<I',hdr[4:8])[0]
base=8+hs
n=0
def walk(node,path):
    global n
    for k,v in node.get('files',{}).items():
        q=os.path.join(path,k)
        if 'files' in v: walk(v,q)
        elif 'offset' in v:
            f.seek(base+int(v['offset'])); d=f.read(v['size'])
            fn=os.path.join(out,q); os.makedirs(os.path.dirname(fn),exist_ok=True)
            open(fn,'wb').write(d); n+=1
walk(j,'')
print('files',n)
