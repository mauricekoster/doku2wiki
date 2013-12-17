import ConfigParser
import sys, os, shutil
import shellfolders
import urllib
from urllib import urlencode, unquote, splittype, splithost
import re
import base64
from generators._utils import WriteFile
from generators.EpubGenerator import EpubGenerator
from generators.ChmGenerator import ChmGenerator
from generators.NoGenerator import NoGenerator
from DokuWiki import getDokuWikiClient

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

class DokuToDoc():
    def __init__(self, inifile, page='start', target='document', mode='toc', proxy_host='', proxy_user='', proxy_password=''):

        cfg = ConfigParser.ConfigParser()
        cfg.readfp( open( inifile ) )
        self._conf = {}
        
        # Dokuwiki settings
        self._conf['dokuwiki'] = {}
        if cfg.has_option('dokuwiki', 'url'):
            self._conf['dokuwiki']['url'] = cfg.get('dokuwiki', 'url')
        else:
            print 'option dokuwiki.url not found.'
            sys.exit(1)
        
        if cfg.has_option('dokuwiki', 'username'):
            self._conf['dokuwiki']['username'] = cfg.get('dokuwiki', 'username')
        else:
            print 'option dokuwiki.username not found.'
            sys.exit(1)
        
        if cfg.has_option('dokuwiki', 'password'):
            self._conf['dokuwiki']['password'] = cfg.get('dokuwiki', 'password')
        else:
            print 'option dokuwiki.password not found.'
            sys.exit(1)
            
        if cfg.has_option('dokuwiki', 'namespace'):
            self._conf['dokuwiki']['namespace'] = cfg.get('dokuwiki', 'namespace')
        else:
            self._conf['dokuwiki']['namespace'] = 'start'
            
        # general options
        self._conf['general'] = {}
        if cfg.has_option('general', 'template'):
            self._conf['general']['template'] = cfg.get('general', 'template')
        else:
            self._conf['general']['template'] = ''
        if not self._conf['general']['template']:
            self._conf['general']['template'] = os.path.dirname(__file__)  + os.path.sep + 'Template' # folder of this script
            
        if cfg.has_option('general', 'work'):
            self._conf['general']['work'] = cfg.get('general', 'work')
        else:
            self._conf['general']['work'] = ''
        if not self._conf['general']['work']:
            self._conf['general']['work'] = shellfolders.MyTemp() + os.path.sep + 'DokuToDoc'  # folder of this script
        
        # epub options
        self._conf['document'] = {}
        
        if cfg.has_option('document', 'title'):
            self._conf['document']['title'] = cfg.get('document', 'title')
        else:
            self._conf['document']['title'] = 'No Title'
    
        if cfg.has_option('document', 'author'):
            self._conf['document']['author'] = cfg.get('document', 'author')
        else:
            self._conf['document']['author'] = 'No Author'
    
        if cfg.has_option('document', 'lang'):
            self._conf['document']['lang'] = cfg.get('document', 'lang')
        else:
            self._conf['document']['lang'] = 'nl'
            
        if cfg.has_option('document', 'folder'):
            self._conf['document']['folder'] = cfg.get('document', 'folder')
        else:
            self._conf['document']['folder'] = ''

        if self._conf['document']['folder'] == 'desktop':
            self._conf['document']['folder'] = shellfolders.MyDesktop()
        if not self._conf['document']['folder']:
            self._conf['document']['folder'] = os.path.dirname( os.path.realpath( inifile ) )
    
        if cfg.has_option('document', 'filename'):
            self._conf['document']['filename'] = cfg.get('document', 'filename')
        else:
            self._conf['document']['filename'] = self._conf['document']['title']

        url, usr, pwd = (self._conf['dokuwiki']['url'], self._conf['dokuwiki']['username'], self._conf['dokuwiki']['password'])
                    
        self.server = getDokuWikiClient(url, usr, pwd, proxy_host, proxy_user, proxy_password)

        self.topic_nr = 0
        
        self.mode = mode
        self.page = page
        
        # TODO: make this pluggable
        if target == 'epub':
            self.target = EpubGenerator(self._conf)
        elif target == 'chm':
            self.target = ChmGenerator(self._conf)
        else:
            self.target = NoGenerator(self._conf)
        
    def GetAttachments(self):
        wf = os.path.join( self._conf['general']['work'], "source", "images" ) 
        g = re.findall('{{([^}]*)}}', self.topic)
        for e in g:
            try:
                l = e.split('|', 1)[0]
            except:
                l = e
            
            if '?' in l:
                l = l[:l.find('?')]
            
            att = self.server.wiki.getAttachment(l)
            bindata = att.data  # base64.decodestring(att)
            
            fn = os.path.join( wf, l.split(':')[-1] )
            f = open(fn, 'wb')
            f.write( bindata )
            f.close()
            
        
    def GetTopic(self, topic):
        """
        Get the topic. 
        
        This includes the raw text and the rendered xhtml page.
        All attachments used in the page will be downloaded as well.
        """
        
        if topic in self.topics:
            print "Topic already downloaded: %s" % topic
            return
        
        print "Topic %s" % topic
        wf = self._conf['general']['work'] + os.path.sep + "source"
        self.topic_nr += 1
        
        html_file = topic.replace( "?", "" )
        html_file = html_file.replace( "/", "-" )
        html_file = html_file.replace( "  ", " " )
        
        
        if ":" in topic:
            topic_content = self.server.wiki.getPage( topic )   
            html_content = self.server.wiki.getPageHTML( topic )    
            html_file = html_file.replace( ":", "-" )       
        else:
            topic_content = self.server.wiki.getPage( self._conf['dokuwiki']['namespace'] + ":" + topic )
            html_content = self.server.wiki.getPageHTML( self._conf['dokuwiki']['namespace'] + ":" + topic )

        self.topic = topic_content
        self.content = html_content
        self.GetAttachments( )
        
        self.topics.append(topic)
        
        html_content = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="nl" lang="nl" dir="ltr">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <link rel="stylesheet" type="text/css" href="styles.css" />
</head>
<body>""" + html_content
        html_content += '</body></html>'
        
        WriteFile( wf + os.path.sep + "text", html_file + ".txt", topic_content, "utf-8" )
        WriteFile( wf + os.path.sep + "xhtml", html_file + ".html", html_content, "utf-8" )
    
    
    def GetHTMLFilesStartPage(self):
        links = self.server.wiki.listLinks( self._conf['dokuwiki']['namespace'] + ':start' )
        for link in links:
            self.GetTopic( link['page'] )
    
    def GetHTMLFileSinglePage(self):
        link = {}
        link['page'] = self.page
        links = [ link ]
        for link in links:
            self.GetTopic( link['page'] )
            
    def Download(self):
        wf = self._conf['general']['work']
        # clear work folder
        try:
            shutil.rmtree( wf )
        
        except:
            pass
    
        os.makedirs( wf )
        os.makedirs( wf + os.path.sep + "source" )
        os.makedirs( wf + os.path.sep + "source" + os.path.sep + "xhtml" )
        os.makedirs( wf + os.path.sep + "source" + os.path.sep + "text" )
        os.makedirs( wf + os.path.sep + "source" + os.path.sep + "images" )
        
        self.topics = []
        if self.mode == 'toc':
            # get start page and store it as text for later processing
            content = self.server.wiki.getPage( self._conf['dokuwiki']['namespace'] + ':start' )
            WriteFile( wf + os.path.sep + "source", "start.txt", content, "utf-8" )
            self.GetHTMLFilesStartPage()
        elif self.mode == 'single':
            content = '  - ' + self.page
            WriteFile( wf + os.path.sep + "source", "start.txt", content, "utf-8" )
            self.GetHTMLFileSinglePage()
        
    def Transform(self):
        self.target.Transform( self.topics )
        
    def Build(self):
        self.target.Build()
        
    def Generate(self):
        self.Download()
        self.Transform()
        self.Build()
        
