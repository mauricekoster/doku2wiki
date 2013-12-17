'''
Created on 17 dec. 2013

@author: Maurice
'''
from _utils import WriteFile, ReadFile
import os.path
import glob
import shutil
import xml.etree.ElementTree as ET
import zipfile
import uuid



class EpubGenerator():
    def __init__(self, conf):
        self._conf = conf

        self.manifest_list = []
        self.spine_list = []
        self.images_list = []

    def ElemToString( self, elem ):
        """
        Function to transfor elementree elem to html string
        """
        attr = ''
        for a in elem.attrib:
            attr = attr + ' ' + a + '="' + elem.attrib[a] +'"'
        
        text = ''
        for t in elem.getchildren():
            text = text + self.ElemToString(t)
            
        #return '<' + elem.tag + attr + '>' + text + '</' + elem.tag + '>'
        return elem.text
     
        
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
            for elem_id in chapter_notes[ c ]:
                    
                sub = ET.SubElement( d,  'sup')
                if flag:
                    sub.tail = ', '
                flag = 1
                
                note = ET.SubElement( sub,  'a')
                note.attrib['class']  = 'fn_bot'
                note.attrib['href'] = '#fnt__%d' % elem_id
                note.attrib['id'] = 'fn__%d' % elem_id
                note.attrib['name'] = 'fn__%d' % elem_id
                note.text = '%d) ' % elem_id
            
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
        chapter_notes = []
        
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
                            xx = self.ElemToString( last )
                            if last.tail:
                                nm = xx + last.tail + nm
                            else:
                                nm = xx + nm
                    
                    #if nm:
                    nm = nm.strip()
                    #else:
                    #   pass
                    
                    #TODO: what happens here?
                    for sub in d.getchildren():
                        for aa in sub.findall(".//a[@class='fn_bot']"):   # 'sub' was 'd'
                            elem_id = aa.attrib['href'][1:]
                            fn_notes[ elem_id ] = nm
                
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
                        elem_id = a.attrib['id']
                    else:
                        elem_id = elem.attrib['id']
        
                    self.topic_list.append( { 
                                            'topicnr': topic_nr, 
                                            'topic': t, 
                                            'tag': elem.tag, 
                                            'innertext': "".join(elem.itertext()),
                                            'linkid': elem_id,
                                            'anchor':  t + '#' +  elem_id,
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
                        elem_id = note.attrib['id']
                        nm = fn_notes[ elem_id ]
                        
                        # renumber footnote
                        chapter_footnote_nr += 1
                        note.attrib['href'] = '#fn__%d' % chapter_footnote_nr
                        note.attrib['id'] = 'fnt__%d' % chapter_footnote_nr
                        note.attrib['name'] = 'fnt__%d' % chapter_footnote_nr
                        note.attrib['title'] = nm
                        note.text = '%d)' % chapter_footnote_nr
                        
                        #TODO: used by?
                        elem_id = 'fnt__%d' % chapter_footnote_nr
                        
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

        zipper = zipfile.ZipFile( os.path.join( self._conf['general']['work'], "target", self._conf['document']['title'] + ".epub" ) , 'w' )
        
        # mimetype
        zipper.write(os.path.join( self._conf['general']['work'], "target", "mimetype"), 'mimetype', zipfile.ZIP_STORED)
        
        # META-INF
        for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "META-INF", "*") ):
            zipper.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        # OEBPS
        for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "OEBPS", "*") ):
            if os.path.isfile(name):
                zipper.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        # OEBPS/*
        for x in ('Text','Images','Styles'):
            for name in glob.glob(os.path.join( self._conf['general']['work'], "target", "OEBPS", x, "*") ):
                if os.path.isfile(name):
                    zipper.write(name, os.path.relpath(name, os.path.join( self._conf['general']['work'], "target")), zipfile.ZIP_DEFLATED)

        zipper.close()

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
