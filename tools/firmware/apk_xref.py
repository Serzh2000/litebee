from loguru import logger; logger.disable("androguard")
import sys,logging
logging.disable(logging.CRITICAL)
from androguard.core.dex import DEX
import re
want_strings=sys.argv[1].split('|')
want_methods=sys.argv[2:]
for dn in (__import__('os').environ.get('DEX','classes.dex'),'libs/classes2.dex'):
    d=DEX(open(dn,'rb').read())
    for c in d.get_classes():
        for m in c.get_methods():
            code=m.get_code()
            if not code: continue
            try: ins=list(code.get_bc().get_instructions())
            except Exception: continue
            for i in ins:
                o=i.get_output()
                if any(w in o for w in want_strings) or any(w in o for w in want_methods):
                    print(dn[-11:],c.get_name(),m.get_name(),'|',i.get_name(),o[:150])
