from loguru import logger; logger.disable("androguard")
import sys
from androguard.core.dex import DEX
d=DEX(open(__import__('os').environ.get('DEX','classes.dex'),'rb').read())
for c in d.get_classes():
    if c.get_name()==sys.argv[1]:
        for m in c.get_methods():
            code=m.get_code()
            print('###',m.get_name(),m.get_descriptor())
            if not code: continue
            for i in code.get_bc().get_instructions(): print('   ',i.get_name(),i.get_output()[:150])
