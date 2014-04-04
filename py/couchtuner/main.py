""" Main entry point for CT-scraping """
from argparse import ArgumentParser
from errno import EEXIST
import os
from time import time
from traceback import print_exc
from urllib2 import URLError
import boto
from lxml import etree
from lxml.builder import E
from requests.exceptions import Timeout
from common import SHOWS, start_chromedriver, mkdir
from pages import ShowPage

def init_shows_xml():
    """ Initialize shows.xml """
    shows_root = E('root')
    for key in sorted(SHOWS.keys()):
        try:
            show_pg = ShowPage(SHOWS[key]['url'])
            show = show_pg.to_xml()
            shows_root.append(show)
        except Timeout:
            pass
    shows_root.getroottree().write('shows.xml')
    s3 = boto.connect_s3()
    s3_bucket = s3.get_bucket('xtcouchtuner')
    s3_key = s3_bucket.get_key('shows.xml')
    s3_key.set_contents_from_filename('shows.xml')
    s3.close()

def go(showname=None, season=None):
    if showname:
        shows = [showname]
    else:
        shows = sorted(SHOWS.keys())
    chrome = start_chromedriver()
    s3 = boto.connect_s3()
    s3_bucket = s3.get_bucket('xtcouchtuner')
    try:
        for showname in shows:
            try:
                print 'Parsing %s...' % showname.title()
                p = ShowPage(SHOWS[showname.lower()]['url'])
                if season:
                    seasons = [season]
                else:
                    seasons = p.get_seasons()
                for s in seasons:
                    print 'Writing season %i...' % s,
                    p.write_season_file(s, chrome)
                    print 'Season %i local done...' % s,
                    s3_key = s3_bucket.get_key(p.get_s3_key_name(s))
                    if not s3_key:
                        s3_key = s3_bucket.new_key(p.get_s3_key_name(s))
                    s3_key.set_contents_from_filename(p.get_local_xml_file(s))
                    print 'S3 done'
                print
            except Timeout:
                pass
    except KeyboardInterrupt:
        print 'Well, I guess you\'ve got better things to do...'
    except:
        print_exc()
    finally:
        try:
            chrome.quit()
        except URLError:
            pass
        s3.close()


if __name__ == '__main__':
    START = time()
    parser = ArgumentParser(description='Update CT xml files')
    parser.add_argument('--show', help='show name (default = all)')
    parser.add_argument('-s', '--season', type=int, help='season (default = all)')
    parser.add_argument('-i', '--init', help='initialize shows.xml', action='store_true')
    args = parser.parse_args()
    if args.init:
        init_shows_xml()
    else:
        go(args.show, args.season)
    DURATION = time() - START
    print 'Duration in minutes:', DURATION / 60
