""" Main entry point for CT-scraping """
from errno import EEXIST
from os import mkdir
from urlparse import urljoin, urlparse
from lxml import etree
from lxml.builder import E
from common import SHOWS, S3_URL, HOSTS, start_chromedriver
from pages import ShowPage, EpPage, SourcePage, NoSourceError

def _get_feed_url(showname, season):
    """ Return feed url """
    return urljoin(S3_URL,
        '%s/%i.xml' % (
            _format_showname(showname),
            season))

def _format_showname(showname):
    """ Return formatted showname """
    return '_'.join(showname.lower().split())

def _get_content_id(showname, season, ep):
    """ Return content id """
    return '%i%i%i' % (
        SHOWS[showname.lower()]['id_'],
        season,
        ep)

def _get_bitrate(url):
    """ Return bitrate """
    return HOSTS[urlparse(url).netloc]

def _try_to_mkdir(dir_):
    """ Make dir if it doesn't already exist """
    try:
        mkdir(dir_)
    except OSError as err:
        if err.errno != EEXIST:
            raise

def init_shows_xml():
    """ Initialize shows.xml """
    shows_root = E('root')
    for v in SHOWS.values():
        show_pg = ShowPage(v['url'])
        print 'Parsing', show_pg.name
        show = E('show',
            name=show_pg.name,
            img_src=show_pg.img_src,
            url=show_pg.url)
        shows_root.append(show)
        latest = show_pg.get_latest_ep()
        show.append(E('latest',
            season=str(latest['season']),
            ep=str(latest['ep'])))
        for season in show_pg.get_seasons():
            print 'Parsing', season
            show.append(E('season',
                num=str(season),
                feed=_get_feed_url(show_pg.name, season)))
        print
    shows_root.getroottree().write('shows.xml')

def do_it_all():
    """ Do it! """
    shows = etree.parse('shows.xml')
    chrome = start_chromedriver()
    try:
        _try_to_mkdir('shows')
        for s in shows.findall('show'):
            show_pg = ShowPage(s.get('url'))
            print 'Parsing %s...' % show_pg.name
            for ssn in s.findall('season'):
                update_season(show_pg, int(ssn.get('num')), chrome)
    except Exception as err:
        print 'WHOOPS!!!!', err
    finally:
        chrome.quit()

def update_season(show_pg, season, chrome):
    """ Update single season """
    print 'Getting episode info for season %i' % season
    root = E('root')
    eps = show_pg.get_ep_list(season, True)
    for e in eps:
        ep = E('episode',
            num=str(e['num']),
            name=e['name'],
            desc=e['desc'],
            url=e['url'],
            content_id=_get_content_id(
                show_pg.name,
                season,
                e['num']),
            duration='')
        try:
            ep_pg = EpPage(e['url'])
            for src in ep_pg.iframe_srcs:
                src_pg = SourcePage(src, chrome)
                if not ep.get('duration'):
                    ep.set('duration', str(src_pg.duration))
                if not ep.get('img_src'):
                    ep.set('img_src', src_pg.img_src)
                ep.append(E('source',
                    url=src_pg.mp4_url,
                    bitrate=str(_get_bitrate(src_pg.url))))
        except NoSourceError as err:
            print err
        if len(ep.findall('source')) > 0:
            root.append(ep)
        else:
            print 'No source found for E%i' % e['num']
    _try_to_mkdir('shows\\%s' % _format_showname(
        show_pg.name))
    print 'Writing xml...',
    root.getroottree().write('shows\\%s\\%i.xml' % (
        _format_showname(show_pg.name),
        season))
    print 'DONE!\n'

def update_psych_ssn_8():
    """ Psych S8 """
    p = ShowPage('http://www.couchtuner.eu/psych/')
    chrome = start_chromedriver()
    try:
        update_season(p, 8, chrome)
    except Exception as err:
        print 'WHOOPS!', err
    chrome.quit()

if __name__ == '__main__':
    do_it_all()
