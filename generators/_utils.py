'''
Created on 17 dec. 2013

@author: Maurice
'''

import codecs
import os.path

def WriteFile(workfolder, filename, content, encoding='ansi'):
    fn = workfolder 
    if fn[-1:] != os.path.sep:
        fn += os.path.sep
    fn = fn + filename
    
    if encoding == 'ansi':
        f = open(fn, 'w')
        f.write( content )
    else:
        f = codecs.open(fn, 'w', encoding )
#       if encoding == 'utf-8':
#           f.write( codecs.BOM_UTF8 )
            
        f.write( content )

    f.close()

def ReadFile(workfolder, filename, encoding='ansi'):
    fn = workfolder 
    if fn[-1:] != os.path.sep:
        fn += os.path.sep
    fn = fn + filename
    
    if encoding == 'ansi':
        f = open(fn, 'r')
    else:
        f = codecs.open(fn, 'r', encoding )
        
    content = f.read()
    f.close()
    
    if content[0] == unicode( codecs.BOM_UTF8, "utf8" ):
        content = content[1:]
        
    return content