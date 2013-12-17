'''
Created on 17 dec. 2013

@author: Maurice
'''
from urllib import urlencode, splittype, splithost, unquote
import sys
import base64

try:
    #import xmlrpclib_new as xmlrpclib
    import xmlrpclib
except ImportError:
    print "This script needs the xmlrpclib module!"
    sys.exit(1)

class UrllibTransport(xmlrpclib.Transport):
    def set_proxy(self, proxy):
        self.proxyurl = proxy
 
    def request(self, host, handler, request_body, verbose=0):
        _, r_type = splittype(self.proxyurl)
        phost, _ = splithost(r_type)

        puser_pass = None
        if '@' in phost:
            user_pass, phost = phost.split('@', 1)
            if ':' in user_pass:
                user, password = user_pass.split(':', 1)
                puser_pass = base64.encodestring('%s:%s' % (unquote(user),
                                                unquote(password))).strip()

        urlopener = urllib.FancyURLopener({'http':'http://%s'%phost})
        if not puser_pass:
            urlopener.addheaders = [('User-agent', self.user_agent)]
        else:
            urlopener.addheaders = [('User-agent', self.user_agent),
                                    ('Proxy-authorization', 'Basic ' + puser_pass) ]

        host = unquote(host)
        f = urlopener.open("http://%s%s"%(host,handler), request_body)

        self.verbose = verbose 
        return self.parse_response(f)



def getDokuWikiClient(dokuwiki_url, dokuwiki_user, dokuwiki_password, proxy_host=None, proxy_user=None, proxy_password=None):
    '''
    get the xml-rpc server
    '''
    url = dokuwiki_url + "/lib/exe/xmlrpc.php?" + urlencode( { 'u':dokuwiki_user, 'p':dokuwiki_password } )
        
    if proxy_host:
        p = UrllibTransport()
        
        if proxy_user:
            proxy = proxy_user
            if proxy_password:
                proxy = proxy +':' + proxy_password 
            proxy = proxy + '@' + proxy_host
        else:
            proxy = proxy_host
        print 'Proxy: %s\n' % proxy
        p.set_proxy(proxy)
        return xmlrpclib.Server(url, transport=p)
    
    return xmlrpclib.ServerProxy(url)


        
        