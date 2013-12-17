'''
Created on 17 dec. 2013

@author: Maurice
'''
from DokuToDoc import DokuToDoc
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser( description='Do stuff.' )
    parser.add_argument('ini',  type=str, 
        help='a configuration file')
    parser.add_argument('--output',  choices=['epub', 'chm'], default='epub', type=str, 
                   help='target type (chm,epub)')
    parser.add_argument('--mode',  choices=['single', 'toc'], default='toc', type=str, 
                   help='mode: single page of table of content (single,toc)')
                   
    parser.add_argument('--proxy_host',  default='', type=str, 
                   help='proxy host')
    parser.add_argument('--page', default='start', type=str, nargs='?',
                   help='a topic pagename')               
    args = parser.parse_args()
    print args
    
    c = DokuToDoc(args.ini, args.page, args.output, args.mode, args.proxy_host)
    c.Generate()
    print 'Done'
