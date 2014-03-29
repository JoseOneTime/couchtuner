""" Main entry point for CT-scraping """
from errno import EEXIST
import os
from urlparse import urljoin, urlparse
from lxml import etree
from lxml.builder import E
from common import SHOWS, S3_URL, HOSTS, start_chromedriver
from pages import ShowPage, EpPage, SourcePage, NoSourceError

def mkdir(dir_):
    """ Make dir if it doesn't already exist """
    try:
        os.mkdir(dir_)
    except OSError as err:
        if err.errno != EEXIST:
            raise

def init_shows_xml():
    """ Initialize shows.xml """
    shows_root = E('root')
    for v in SHOWS.values():
        show_pg = ShowPage(v['url'])
        show = show_pg.to_xml()
        shows_root.append(show)
    shows_root.getroottree().write('shows.xml')

def do_it_all():
    """ Do it! """
    shows = etree.parse('shows.xml')
    chrome = start_chromedriver()
    try:
        mkdir('shows')
        for s in shows.findall('show'):
            show_pg = ShowPage(s.get('url'))
            print 'Parsing %s...' % show_pg.name
            for ssn in s.findall('season'):
                show_pg.write_season_file(int(ssn.get('num')), chrome)
    except Exception as err:
        print 'WHOOPS!!!!', err
    finally:
        chrome.quit()

if __name__ == '__main__':
    do_it_all()
