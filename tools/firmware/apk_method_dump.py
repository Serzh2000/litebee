from loguru import logger; logger.disable("androguard")
import sys
from androguard.core.dex import DEX
d=DEX(open(__import__('os').environ.get('DEX','classes.dex'),'rb').read())
want=sys.argv[1:]
for c in d.get_classes():
    for m in c.get_methods():
        key=c.get_name()+'->'+m.get_name()
        if not any(w==key or (w.endswith('*') and key.startswith(w[:-1])) for w in want): continue
        code=m.get_code()
        if not code: continue
        print('###',key)
        for i in code.get_bc().get_instructions():
            print('   ',i.get_name(),i.get_output()[:140])
