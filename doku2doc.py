import argparse
import ConfigParser
import sys, os, shutil, glob
import shellfolders
import codecs, uuid
import urllib
from urllib import urlencode, unquote, splittype, splithost
import re
import base64
import xml.etree.ElementTree as ET
import subprocess
import zipfile

sys.path.append(".\\Lib")

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
        type, r_type = splittype(self.proxyurl)
        phost, XXX = splithost(r_type)

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

def ElemToString( elem ):
    """
    Function to transfor elementree elem to html string
    """
    attr = ''
    for a in elem.attrib:
        attr = attr + ' ' + a + '="' + elem.attrib[a] +'"'
    
    text = ''
    for t in elem.getchildren():
        text = text + ElemToString(t)
        
    #return '<' + elem.tag + attr + '>' + text + '</' + elem.tag + '>'
    return elem.text
    
class NoGenerator():
    def __init__(self, conf):
        self._conf = conf
        
    def Transform(self):
        pass
    
    def Build(self):
        pass

class ChmGenerator():
    def __init__(self, conf):
        self._conf = conf
        
    def Transform(self, topics ):
        self.topics = topics
        wf = self._conf['general']['work'] + os.path.sep + "target"
        wf_src = self._conf['general']['work'] + os.path.sep + "source"
        
        # create folder structure
        os.makedirs( wf )
        os.makedirs( wf + os.path.sep + "html" + os.path.sep + "images" )
        
        # copy stylesheet
        fn_src = os.path.join( self._conf['general']['template'], "Styles", "*.css" )
        for f in glob.glob(fn_src):
            shutil.copy( f, os.path.join(wf, "html") )
            
        # copy images to correct location
        fn_src = wf_src + os.path.sep + "images" + os.path.sep + "*.*"
        for f in glob.glob(fn_src):
            shutil.copy( f, wf + os.path.sep + "html"  + os.path.sep + "images" )
            
        # copy smileys to correct location
        # TODO: system images
        
        # process all topic files
        for topic in topics:
            print "'tranforming' %s" % topic
            
            if ':start' in topic:
                continue
            
            content = ReadFile( wf_src + os.path.sep + "xhtml", topic.replace(':','-') + '.html', 'utf-8' )
            content = content.replace( 'xmlns="http://www.w3.org/1999/xhtml"', '' )
            try:
                #tree = ET.fromstring(content.encode('ascii', 'xmlcharrefreplace') )
                tree = ET.fromstring(content.encode('utf-8') )
                #tree = ET.fromstring( content )
            except:
                print content

            # remove 'Back to start' links (aka links with start in name)
            body = tree.find('.//body')
            l = tree.findall(".//body/p")
            for i in l :
                l2 = i.findall(".//a[@class='wikilink1']")
                for ii in l2:
                    if 'Back to' in ii.text:
                        body.remove(i)
                        
            # replace all media anchors containing a image tag
            l = tree.findall(".//a[@class='media']")
            for i in l :
                if 'href' in i.keys():
                    img = list(i)
                    if img:
                        pic = img[0]
                        #src = pic.attrib['src']
                        #i.clear()
                        for x in i.getchildren():
                            i.remove(x)
                            
                        i.tag = 'img'
                        
                        fn = pic.attrib['src'].split('/')[-1]
                        if '?' in fn:
                            fn = fn[:fn.find('?')]
                        i.text = '' 
                        i.set('src', 'images/' + fn)
                        i.set('class', pic.attrib['class'])
                        if 'alt' in pic.keys():
                            i.set('alt', pic.attrib['alt'])
                        if 'title' in pic.keys():
                            i.set('title', pic.attrib['title'])
                        if 'width' in pic.keys():
                            i.set('width', pic.attrib['width'])
                        if 'href' in i.attrib:
                            del i.attrib['href']
                            
            # replace smiley links
            l = tree.findall(".//img[@class='middle']")
            for i in l:
                if i.attrib['src'].startswith('/lib/images/smileys'):
                    print 'system image %s' % i.attrib['alt']
                    fn = 'images/' + os.path.basename( i.attrib['src'] )
                    if not os.path.exists( os.path.join( wf, 'html', 'images', os.path.basename( i.attrib['src'] ) ) ):
                        # copy image from template dir
                        shutil.copy( os.path.join( self._conf['general']['template'], "Images", "smileys", os.path.basename( i.attrib['src'] ) ), 
                                     os.path.join( wf, "html", "images" ) )
                    
                    i.attrib['src'] = fn 
            
            # replace internal links
            l = tree.findall(".//a[@class='wikilink1']")
            for i in l:
                href = i.attrib['href']
                if '#' in href:
                    (h1, h2) = href.split('#')
                else:
                    (h1, h2) = (href, '')
                    
                href = h1.split('/')[-1] + '.html'
                if h2:
                    href += '#' + h2
                i.attrib['href'] = href
                    
            # writing resulting page to target location
            c = ET.tostring( tree, 'ascii', 'xml' )
            c = c.replace("<?xml version='1.0' encoding='ascii'?>","")
            c = c.replace("xmlns:html=","xmlns=")
            c = c.replace("<html:","<")
            c = c.replace("</html:","</")
            WriteFile( os.path.join( wf, "html" ), topic.replace(':','-') + ".html", c, 'utf-8' )
        
        # generate hhc and hhp files
        self.GenerateHHP()
        self.GenerateHHC()
        
    def GenerateHHP(self):
        wf = self._conf['general']['work'] + os.path.sep + "target"
        t = self._conf['document']['title']
        f = open( wf + os.path.sep + t + ".hhp", 'w')
    
        topics = [topic for topic in self.topics if not '..' in topic]
        
            
        # print project header
        f.write( "[OPTIONS]" + '\n' )
        f.write( "Compatibility = 1.1 Or later" + '\n' )
        f.write( "Compiled file={}.chm".replace('{}', t) + '\n' )
        f.write( "Contents file={}.hhc".replace('{}', t) + '\n' )
        f.write( "default topic = html\{}.html".replace('{}', topics[0] ) + '\n' )
        f.write( "Display compile progress=No" + '\n' )
        f.write( "Language=0x809 Engels (Verenigd Koninkrijk)" + '\n' )
        f.write( "Title={}".replace('{}', t) + '\n' )
        f.write(  "" + '\n' )
        f.write( "[FILES]" + '\n' )

        # list of used html files
        for topic in topics:
            f.write( "html\\" + topic.replace(':','-') + ".html\n" )
            
        # print project footer
        f.write( "\n[INFOTYPES]\n\n" )
        f.close()
    
    def GenerateHHC(self):
        wf = self._conf['general']['work'] + os.path.sep + "target"
        
        content = ReadFile( self._conf['general']['work'] + os.path.sep + "source", 'start.txt', 'utf-8' )
        arr = content.split( '\n' )
        lvl = 1
        t = self._conf['document']['title']
        
        f = open( wf + os.path.sep + t + '.hhc', 'w' )
    
        # print content header
        header = """<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN">
<HTML>
<HEAD>
<meta name="GENERATOR" content="DokuToDoc">
<!-- Sitemap 1.0 -->
</HEAD><BODY>
<OBJECT type="text/site properties">
    <param name="FrameName" value="main">
    <param name="Window Styles" value="0x800025">
    <param name="ImageType" value="Folder">
</OBJECT>
<UL>
    <LI> <OBJECT type="text/sitemap">
        <param name="Name" value="{TITLE}">
        <param name="ImageNumber" value="1">
        </OBJECT>
    <UL>
"""
        header = header.replace('{TITLE}', t )
        f.write( header )
        
        # print table of content
        for l in arr:
            if not l.strip():
                continue
            
            if l.strip()[0] == "-":
                p = l.find('-')

                new_lvl = p // 2

                if new_lvl < lvl:
                    for j in range( lvl, new_lvl, -1 ):
                        f.write( ' ' * ((j + 2) * 4) +  "</UL>\n" )
                elif new_lvl > lvl:
                    f.write( ' ' * ((lvl + 2) * 4) + "<UL>\n" )

                # get title and topic
                is_new = False

                txt = l[p + 1:]

                # remove fixme's and trim
                txt = txt.replace( "FIXME", "" ).strip()

                # check new topic
                if ":!:" in txt:
                    txt = txt.replace( ":!:", "" )
                    is_new = True

                # remove trailing spaces
                txt = txt.strip()

                # determine title and link
                g = re.search( '\[\[([^\]]*)\]\]', txt )
                if g:
                    s = g.groups()[0]
                    t = str(s.encode('latin-1'))
                    if '|' in t:
                        entry_topic, entry_title = t.split('|')
                    else:
                        entry_title, entry_topic = t, t
                else:
                    entry_title = txt
                    entry_topic = ''

                # level indent
                s = ' ' * ((new_lvl + 2) * 4)

                f.write( s + '<LI> <OBJECT type="text/sitemap">\n' )

                f.write( s + '    <param name="Name" value="{}">\n'.replace( "{}", entry_title.strip() ) )
                if entry_topic:
                    f.write( s + '    <param name="Local" value="html\{}.html">\n'.replace( "{}", entry_topic.strip()) )

                if is_new:
                    f.write( s + '    <param name="New" value="1">\n' )


                f.write( s + "    </OBJECT>\n" )
                lvl = new_lvl

        # print footer
        f.write( """    </UL>
</UL>
</BODY></HTML>""" )

        f.close()

    def Build(self):
        wf = self._conf['general']['work'] + os.path.sep + "target"
        if os.path.exists( 'C:\\Program Files (x86)\\HTML Help Workshop\\hhc.exe' ):
            exec_name = 'C:\\Program Files (x86)\\HTML Help Workshop\\hhc.exe'
        elif os.path.exists( 'C:\\Program Files\\HTML Help Workshop\\hhc.exe' ):
            exec_name = 'C:\\Program Files\\HTML Help Workshop\\hhc.exe' 
        elif os.path.exists( 'D:\\htmlhelp\\hhc.exe' ):
            exec_name = 'D:\\htmlhelp\\hhc.exe' 
        else:
            print 'Help compiler not installed!'
            return
        
        subprocess.call( [ exec_name, wf + os.path.sep + self._conf['document']['title'] + '.hhp' ]
                , cwd = wf
                )

        shutil.copy( wf + os.path.sep + self._conf['document']['title'] + '.chm' ,
                     self._conf['document']['folder']
                    )
        
class EpubGenerator():
    def __init__(self, conf):
        self._conf = conf

        self.manifest_list = []
        self.spine_list = []
        self.images_list = []
        
    def Transform(self, topics):
        print 'Transforming to EPub'
        self.topics = topics
        
        wf = os.path.join( self._conf['general']['work'], "target" )
        os.makedirs( wf )
        
        os.makedirs( os.path.join(wf, "OEBPS", "Text" ) )
        os.makedirs( os.path.join(wf, "OEBPS", "Images" ) )
        os.makedirs( os.path.join(wf, "OEBPS", "Styles" ) )
                
        WriteFile( wf, 'mimetype', 'application/epub+zip' )
        
        self.GenerateManifest()

        # copy stylesheet from templates
        fn_src = os.path.join( self._conf['general']['template'], "Styles", "*.css" )
        fn_target = os.path.join( wf, "OEBPS", "Styles" )
        for f in glob.glob(fn_src):
            shutil.copy( f, fn_target )
        
        # copy images to correct location
        fn_src = os.path.join( self._conf['general']['work'], "source", "images", "*.*" )
        fn_target = os.path.join( wf, "OEBPS", "Images" )
        for f in glob.glob(fn_src):
            shutil.copy( f, fn_target )
        for f in glob.glob( os.path.join(fn_target, "*.*") ):
            name = os.path.basename(f)
            ext = os.path.splitext(f)[1][1:]
            self.images_list.append( '<item id="%s" href="Images/%s" media-type="image/%s"/>' % (name,name,ext) )

        
        self.ProcessTopics()
        
        self.GenerateContentOpf()
        
        self.GenerateTOC( 2 )

    def AppendFootnotes(self,  tree,  chapter_notes):
        
        body = tree.find('.//body')
        footnotes = ET.SubElement(body, 'div')
        footnotes.attrib['class'] = 'footnotes'
        
        arr = [ (chapter_notes[x][0],  x) for x in chapter_notes.keys() ]
        arr.sort()
        arr = [ x[1] for x in arr ]
        for c in arr:
        #   footnotes.append( note )
            d = ET.SubElement(footnotes,  'div')
            d.attrib['class'] = 'fn'
            flag = 0
            for id in chapter_notes[ c ]:
                if flag:
                    sub.tail = ', '
                flag = 1
                    
                sub = ET.SubElement( d,  'sup')
                note = ET.SubElement( sub,  'a')
                note.attrib['class']  = 'fn_bot'
                note.attrib['href'] = '#fnt__%d' % id
                note.attrib['id'] = 'fn__%d' % id
                note.attrib['name'] = 'fn__%d' % id
                note.text = '%d) ' % id
            
            sub.tail = c

    def ProcessTopics(self):
        
        # read all topic files to topic_content buffer
        wf = os.path.join( self._conf['general']['work'], "source", "xhtml" )
        topic_content = ''
        self.topic_list = []
        topic_nr = 0
        chapter_nr = 0
        chapter_file = ''
        chapter_tree = []
        
        # template for the chapter file
        chapter_content = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
 "http://www.w3.org/TR/xhtml1/DTD/xhtml1.dtd">
<html xml:lang="nl" lang="nl" dir="ltr">
<head>
  <title></title>
  <meta content="doku2doc.py" name="generator" />
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <link rel="stylesheet" type="text/css" href="../Styles/styles.css" />
</head>
<body></body></html>"""
        
        
        
        chapter_trees = []
        
        # process all topics
        for t in self.topics:
            topic_nr += 1
            print "Processing topic %s" % t
            content = ReadFile(wf, t.replace(':','-') + '.html', 'utf-8')
            content = content.replace( 'xmlns="http://www.w3.org/1999/xhtml"', '' )
            topic_content = ET.fromstring(content.encode('utf-8') )
                
            topic_body = topic_content.find('.//body')
            
            # get all bottom footnotes texts from topic
            fn_notes = {}
            fn_bot = topic_body.find(".//div[@class='footnotes']")
            if fn_bot is not None:
                for d in fn_bot.getchildren():
                    idx = 0
                    nm = ''
                    while 1:
                        idx -= 1
                        last = d.getchildren()[idx]
                        
                        if last.tag == 'sup':   
                            nm = last.tail + nm
                            break
                        else:
                            xx = ElemToString( last )
                            if last.tail:
                                nm = xx + last.tail + nm
                            else:
                                nm = xx + nm
                    
                    #if nm:
                    nm = nm.strip()
                    #else:
                    #   pass
                    
                    for sub in d.getchildren():
                        for aa in d.findall(".//a[@class='fn_bot']"):
                            id = aa.attrib['href'][1:]
                            fn_notes[ id ] = nm
                
                # remove bottom footnotes
                topic_body.remove( fn_bot )     
            
            # process all headings and content from sections
            for elem in topic_body.getchildren():
                if elem.tag in ('h1','h2','h3','h4','h5'):
                    # h1 will create a new chapter file
                    if elem.tag == 'h1':
                        if chapter_nr > 0:
                            # append footnotes to body
                            if len(chapter_notes):
                                self.AppendFootnotes( chapter_tree,  chapter_notes )
                        
                        # start the new chapter
                        chapter_nr += 1
                        chapter_file = "chapter%04d" % chapter_nr
                        chapter_tree = ET.fromstring(chapter_content.encode('utf-8') )
                        chapter_trees.append( chapter_tree )
                        
                        chapter_footnote_nr = 0
                        
                        title = chapter_tree.find('.//head/title')
                        title.text = 'Chapter %d' % chapter_nr
                        # TODO: add chapter name to tite (h1 text)
                        
                        # manifest item
                        self.manifest_list.append( '        <item id="chapter%04d.xhtml" href="Text/chapter%04d.xhtml" media-type="application/xhtml+xml"/>' % (chapter_nr,chapter_nr) )

                        # spine item
                        self.spine_list.append( '        <itemref idref="chapter%04d.xhtml"/>' % chapter_nr )
                    
                        # restart the chapter footnote hash
                        chapter_notes = {}
                    
                    if elem.getchildren():
                        a = elem.getchildren()[0]
                        id = a.attrib['id']
                    else:
                        id = elem.attrib['id']
        
                    self.topic_list.append( { 
                                            'topicnr': topic_nr, 
                                            'topic': t, 
                                            'tag': elem.tag, 
                                            'innertext': "".join(elem.itertext()),
                                            'linkid': id,
                                            'anchor':  t + '#' +  id,
                                            'chapternr': chapter_nr,
                                            'chapterfile': chapter_file
                                            } )
                
                if chapter_nr > 0 :
                    chapter_body = chapter_tree.find('.//body')
                    chapter_body.append( elem )
                
                # check if element has footnote
                fnotes = elem.findall('.//a[@class="fn_top"]')
                if fnotes:
                    for note in fnotes:
                        # topic footnote id and name
                        id = note.attrib['id']
                        nm = fn_notes[ id ]
                        
                        # renumber footnote
                        chapter_footnote_nr += 1
                        note.attrib['href'] = '#fn__%d' % chapter_footnote_nr
                        note.attrib['id'] = 'fnt__%d' % chapter_footnote_nr
                        note.attrib['name'] = 'fnt__%d' % chapter_footnote_nr
                        note.attrib['title'] = nm
                        note.text = '%d)' % chapter_footnote_nr
                        id = 'fnt__%d' % chapter_footnote_nr
                        
                        if not nm in chapter_notes:
                            chapter_notes[ nm ] = []
                            
                        chapter_notes[ nm ].append( chapter_footnote_nr )
            
    
        # append footnotes to body
        if len(chapter_notes):
            self.AppendFootnotes( chapter_tree,  chapter_notes )
                

        # write out all chapters
        wf = os.path.join( self._conf['general']['work'], "target", "OEBPS", "Text" )

        # this is done now because all link information is now complete
        chapter_nr = 0      
        for ctree in chapter_trees:
            # post-progress chapter trees (replace image links etc.)
            self.PostProcessTree( ctree )
            
            # writing resulting page to target location
            chapter_nr += 1
            content = ET.tostring( ctree, 'ascii', 'xml' )
            content = content.replace("<?xml version='1.0' encoding='ascii'?>","")
            content = content.replace("xmlns:html=","xmlns=")
            content = content.replace("<html:","<")
            content = content.replace("</html:","</")
            content = content.replace("<html",'<html xmlns="http://www.w3.org/1999/xhtml"')
            content = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
  "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
""" + content

            WriteFile( wf, ("chapter%04d" % chapter_nr) + ".xhtml", content, 'utf-8' )

    def PostProcessTree(self, tree):
        # remove 'Back to start' links (aka links with start in name)
        body = tree.find('.//body')
        l = tree.findall(".//body/p")
        for i in l :
            l2 = i.findall(".//a[@class='wikilink1']")
            for ii in l2:
                if 'Back to' in ii.text:
                    body.remove(i)
                        
        # replace all media anchors containing a image tag
        l = tree.findall(".//a[@class='media']")
        for i in l :
            if 'href' in i.keys():
                img = list(i)
                if img:
                    pic = img[0]
                    #src = pic.attrib['src']
                    #i.clear()
                    for x in i.getchildren():
                        i.remove(x)
                        
                    i.tag = 'img'
                    
                    fn = pic.attrib['src'].split('/')[-1]
                    if '?' in fn:
                        fn = fn[:fn.find('?')]
                    i.text = '' 
                    i.set('src', '../Images/' + fn)
                    i.set('class', pic.attrib['class'])
                    if 'alt' in pic.keys():
                        i.set('alt', pic.attrib['alt'])
                    if 'title' in pic.keys():
                        i.set('title', pic.attrib['title'])
                    if 'width' in pic.keys():
                        i.set('width', pic.attrib['width'])
                    if 'href' in i.attrib:
                        del i.attrib['href']


        # replace smiley links
        l = tree.findall(".//img[@class='middle']")
        for i in l:
            if i.attrib['src'].startswith('/lib/images/smileys'):
                #print 'system image %s' % i.attrib['alt']
                fn = '../Images/' + os.path.basename( i.attrib['src'] )
                if not os.path.exists( os.path.join( self._conf['general']['work'], "target", "OEBPS", "Images", os.path.basename( i.attrib['src'] ) ) ):
                    # copy image from template dir
                    shutil.copy( os.path.join( self._conf['general']['template'], "Images", "smileys", os.path.basename( i.attrib['src'] ) ), 
                                 os.path.join( self._conf['general']['work'], "target", "OEBPS", "Images" ) )
                    
                    f = i.attrib['src']
                    name = os.path.basename(f)
                    ext = os.path.splitext(f)[1][1:]
                    self.images_list.append( '<item id="%s" href="Images/%s" media-type="image/%s"/>' % (name,name,ext) )
                    
                i.attrib['src'] = fn 
        
        # replace internal links
        l = tree.findall(".//a[@class='wikilink1']")
        for i in l:
            href = i.attrib['href']
            linkid = href.split('/')[-1]
            print "linkid: %s" % (linkid)

            dummy = [x for x in self.topic_list if x['topic'] == linkid or x['anchor'] == linkid or x['linkid'] == linkid]
            if len(dummy):
                print "  found"
                i.attrib['href'] = dummy[0]['chapterfile'] + '.xhtml'
            
        
        
            
    def Build(self):
        print 'Building EPub'

        zip = zipfile.ZipFile( os.path.join( self._conf['general']['work'], "target", self._conf['document']['title'] + ".epub" ) , 'w' )
        
        # mimetype
        zip.write(os.path.join( self._conf['general']['work'], "target", "mimetype"), 'mimetype', zipfile.ZIP_STORED)
        
        # META-INF
        for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "META-INF", "*") ):
            zip.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        # OEBPS
        for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "OEBPS", "*") ):
            if os.path.isfile(name):
                zip.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        # OEBPS/*
        for x in ('Text','Images','Styles'):
            for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "OEBPS", x, "*") ):
                if os.path.isfile(name):
                    zip.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        zip.close()

        shutil.copy( os.path.join( self._conf['general']['work'], "target", self._conf['document']['title'] + ".epub" ),
                     self._conf['document']['folder'] )
        
    def GenerateManifest(self):
        
        wf = os.path.join( self._conf['general']['work'], "target", "META-INF" )
        
        # create MANIFEST
        os.makedirs( wf  )
        WriteFile( wf, "container.xml", 
"""<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>
""" )
        
    def GenerateContentOpf(self):
        # generate UUID
        self.uuid = str(uuid.uuid4())
                
        # write content.opf
        content = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookID" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier id="BookID" opf:scheme="UUID">{UUID}</dc:identifier>
        <dc:title>{TITLE}</dc:title>
        <dc:creator opf:role="aut">{AUTHOR}</dc:creator>
        <dc:language>{LANGUAGE}</dc:language>
        <meta name="doku2doc.py" content="0.1"/>
    </metadata>
    <manifest>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
        <item id="styles.css" href="Styles/styles.css" media-type="text/css"/>
{IMAGES}
{MANIFEST}
    </manifest>
    <spine toc="ncx">
{SPINE}
    </spine>
</package>
"""

        content = content.replace( "{UUID}", self.uuid )
        content = content.replace( "{TITLE}", self._conf['document']['title'] )
        content = content.replace( "{AUTHOR}", self._conf['document']['author'] )
        content = content.replace( "{LANGUAGE}", "nl" )
        content = content.replace( "{IMAGES}", "\n".join(self.images_list) )
        content = content.replace( "{MANIFEST}", "\n".join(self.manifest_list) )
        content = content.replace( "{SPINE}", "\n".join(self.spine_list) )

        WriteFile( os.path.join( self._conf['general']['work'], "target" , "OEBPS"), "content.opf", content, "utf-8" )

    def GenerateTOC(self, max_level=3):
        
        navpoints = []
        
        content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"
   "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">

<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{UUID}"/>
        <meta name="dtb:depth" content="{TOC-DEPTH}"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle>
        <text>{TITLE}</text>
    </docTitle>
    <navMap>
{NAV-POINTS}
    </navMap>
</ncx>
"""
        counter = 0
        curlevel = 1
        
        for entry in self.topic_list:
            level = int(entry['tag'][1:])
            if counter == 0:
                # do nothing
                pass
                
            elif level > max_level:
                continue

            elif level == curlevel:
                # same level
                navpoints.append( ' ' * (4 * (curlevel + 1)) + "</navPoint>" )

            elif level < curlevel:
                # higher level

                navpoints.append( ' ' * (4 * (curlevel + 1)) + "</navPoint>" )
                navpoints.append( ' ' * (4 * (curlevel)) + "</navPoint>" )

            counter += 1
            navpoints.append( ' ' * (4 * (level + 1)) + '<navPoint id="navPoint-%d" playOrder="%d">' % (counter,counter) )

            # title
            navpoints.append( ' ' * (4 * (level + 2)) + "<navLabel>" )
            navpoints.append( ' ' * (4 * (level + 3)) + "<text>" + entry['innertext'] + "</text>" )
            navpoints.append( ' ' * (4 * (level + 2)) + "</navLabel>" )

            # content
            fn = "Text/" + entry['chapterfile'] + ".xhtml"
            if level > 1:
                fn = fn + "#" + entry['linkid']

            navpoints.append( ' ' * (4 * (level + 2)) + '<content src="%s"/>' % fn )

            curlevel = level

        for i in range(curlevel, 0, -1):
            navpoints.append( ' ' * (4 * (i + 1)) + "</navPoint>" )


        # write content.opf
        content = content.replace( "{UUID}", self.uuid )
        content = content.replace( "{TITLE}", self._conf['document']['title'] )
        content = content.replace( "{TOC-DEPTH}", str(max_level) )
        content = content.replace( "{NAV-POINTS}", '\n'.join(navpoints) )

        WriteFile( os.path.join( self._conf['general']['work'], "target" , "OEBPS"), "toc.ncx", content, "utf-8" )

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

        url = self._conf['dokuwiki']['url'] + "/lib/exe/xmlrpc.php?" + urlencode(
                    {'u':self._conf['dokuwiki']['username']
                    ,'p':self._conf['dokuwiki']['password']})
                    
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
            self.server = xmlrpclib.Server(url, transport=p)
        else:
            self.server = xmlrpclib.ServerProxy(url)

        self.topic_nr = 0
        
        self.mode = mode
        self.page = page
        
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
        
if __name__ == '__main__':


    parser = argparse.ArgumentParser(description='Do stuff.')
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
