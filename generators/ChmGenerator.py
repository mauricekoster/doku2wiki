'''
Created on 17 dec. 2013

@author: Maurice
'''
import os
import subprocess
import shutil
import glob
import xml.etree.ElementTree as ET

from _utils import ReadFile, WriteFile
import re

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
