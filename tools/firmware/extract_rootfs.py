import sys,os
from PySquashfsImage import SquashFsImage
img=open(sys.argv[1],'rb').read()
for name,off in (('sq1',2608128),('sq2',6695936)):
    p=f'{sys.argv[2]}/{name}.bin'; open(p,'wb').write(img[off:])
    try:
        im=SquashFsImage.from_file(p)
        n=0
        for f in im:
            n+=1
            if n<=400 and f.is_file: pass
        print(name,'files',n)
        out=f'{sys.argv[2]}/{name}'
        for f in im:
            t=os.path.join(out,f.path.lstrip('/'))
            if f.is_dir: os.makedirs(t,exist_ok=True)
            elif f.is_file:
                os.makedirs(os.path.dirname(t),exist_ok=True)
                try: open(t,'wb').write(f.read_bytes())
                except Exception as e: print('err',f.path,e)
    except Exception as e: print(name,'ERR',e)
