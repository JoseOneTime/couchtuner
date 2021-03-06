""" CT and co page objects """
from errno import EEXIST
import os.path
import re
from time import sleep
from urlparse import urljoin, urlparse, parse_qs, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import ftfy
from lxml.builder import E
import requests
from selenium.common.exceptions import (
    WebDriverException, NoSuchElementException,
    NoSuchAttributeException, TimeoutException)

from common import (HOSTS, FV_ATTRS, FILE_ATTRS, IMG_ATTRS, S3_URL,
    SHOWS, mkdir)

def catch_key_error(func):
    """ Decorator logs key errors """
    def decorated(*args, **kwargs):
        result = ''
        try:
            result = func(*args, **kwargs)
        except KeyError:
            pass
        return result
    return decorated

def get_abs_ct_url(url):
    """ Return absolute url for CT page """
    return urljoin('http://www.couchtuner.eu', url)

def get_host(url):
    """ Return netloc aka host from url """
    return urlparse(url).netloc

def get_bitrate(url):
    """ Return url's host's bitrate """
    return HOSTS[get_host(url)]

class Page(object):
    """ Base class for all pages """

    def __init__(self, url):
        self.url = url
        self.soup = BeautifulSoup(self._get())

    def _get(self):
        """ Get response body for Page """
        # best balance between runtime and num of 503 errors
        sleep(0.4)
        res = requests.get(self.url, timeout=3.0)
        if res.status_code == 503:
            sleep(1)
            body = self._get()
        else:
            body = res.text
        return body


class Episode(object):
    """ CT episode """
    url = desc = img_src = ''
    duration = 0

    def __init__(self, show_pg, season, num, name):
        self.show_pg = show_pg
        self.season = season
        self.num = num
        self.name = name
        self.content_id = self.get_content_id()

    def __str__(self):
        return 'S%i E%i: %r' % (self.season, self.num, self.name)

    def __repr__(self):
        return str(self)

    def get_content_id(self):
        """ Return content id """
        return '%i%i%i' % (
            SHOWS[self.show_pg.name.lower()]['id_'],
            self.season,
            self.num)

    def to_xml(self):
        """ Return XML representation """
        return E('episode', num=str(self.num), name=self.name, desc=self.desc,
            url=self.url, content_id=self.content_id, duration=self.duration,
            img_src=self.img_src)


class CtPage(Page):
    """ Base class for all CT pages """

    def __init__(self, url):
        super(CtPage, self).__init__(url)
        self.hdr = ftfy.fix_text(self.soup.find(class_='post').h2.text)
        self.entry = self.soup.find(class_='entry')

    def is_watch_here_page(self):
        """ Return True if this is a 'Watch it here' page """
        return 'Watch it here' in self.entry.get_text()

class ShowPage(CtPage):
    """ CT show ep list page """

    def __init__(self, url):
        super(ShowPage, self).__init__(url)
        self.name = self._get_name()
        self.img_src = self._get_img_src()

    def write_season_file(self, season, chrome):
        """ Update single season """
        print 'Getting episodes...',
        eps = self.get_ep_list(season, detail=True)
        root = E('root')
        print 'Parsing episodes...',
        for ep in eps:
            print ep.num,
            srcs = []
            try:
                for src in EpPage(ep.url).iframe_srcs:
                    try:
                        p = SourcePage(src, chrome)
                        if not ep.duration:
                            ep.duration = str(p.duration)
                        if not ep.img_src:
                            ep.img_src = p.img_src
                        srcs.append(dict(url=p.mp4_url, bitrate=get_bitrate(p.url)))
                    except (requests.exceptions.Timeout, TimeoutException):
                        pass
            except (requests.exceptions.Timeout, TimeoutException):
                pass
            except NoSourceError:
                pass
            if len(srcs) > 0:
                ep_xml = ep.to_xml()
                for src in srcs:
                    ep_xml.append(E('source', url=src['url'], bitrate=str(src['bitrate'])))
                root.append(ep_xml)
            else:
                print '(no source found)',
        print 'OK'
        mkdir(self.get_local_xml_dir())
        root.getroottree().write(self.get_local_xml_file(season))

    def get_local_xml_dir(self):
        """ Return local filepath for show xml files """
        return os.path.join('shows', self.get_formatted_name())

    def get_local_xml_file(self, season):
        """ Return local filepath for season xml file """
        return os.path.join(self.get_local_xml_dir(), '%i.xml' % season)

    def get_feed_url(self, season):
        """ Return feed url """
        return urljoin(S3_URL, self.get_s3_key_name(season))

    def get_s3_key_name(self, season):
        """ Return Amazon S3 key name """
        return 'shows/%s/%i.xml' % (self.get_formatted_name(), season)

    def get_formatted_name(self):
        """ Return formatted showname """
        return '_'.join(self.name.lower().split())

    @catch_key_error
    def parse_ep_text(self, text):
        """ Return ep info from text """
        m = re.search(r'(?:S|Season )(?P<season>\d+)'
                                 r' (?:E|Epis[o0]de )(?P<ep>\d+)(?:-\d+)?'
                                 r'(?: ?\W+)? (?P<name>.*)',
                                 text)
        ep = Episode(self, int(m.group('season')), int(m.group('ep')), m.group('name'))
        return ep

    @catch_key_error
    def _get_name(self):
        """ Return show name """
        return re.match('Watch (.*) [Oo]nline', self.hdr).group(1)

    def _get_img_src(self):
        """ Return show img src """
        return get_abs_ct_url(self.entry.img['src'])

    def get_ep_list(self, season=None, detail=False):
        """ Return episode list for single or all seasons """
        eps = []
        for li in self.entry.find_all('li'):
            ep = self.parse_ep_text(li.text)
            if ep:
                if not season or (ep.season == season):
                    eps.append(ep)
                    ep.url = get_abs_ct_url(li.a['href'])
                    if detail:
                        try:
                            p = WatchHerePage(ep.url)
                            ep.desc = p.desc
                            ep.url = p.watch_here_link
                        except requests.exceptions.Timeout:
                            pass
                        except PageTypeError:
                            pass
        eps = sorted(eps, key=lambda ep: ep.num)
        return eps

    def get_seasons(self):
        """ Return sorted list of seasons """
        return sorted(list(set([ep.season for ep in self.get_ep_list()])))

    def get_latest_ep(self):
        """ Return dict(season=season, ep=ep) for latest ep """
        eps = self.get_ep_list()
        ssn_max = max(list({ep.season for ep in eps}))
        ssn_ep_max = max([ep.num for ep in  eps if ep.season == ssn_max])
        return dict(season=ssn_max, ep=ssn_ep_max)

    def to_xml(self):
        """ Return XML representation """
        print 'Parsing %s...' % self.name
        show = E('show', name=self.name, img_src=self.img_src, url=self.url)
        latest = self.get_latest_ep()
        show.append(E('latest', season=str(latest['season']), ep=str(latest['ep'])))

        print 'Parsing seasons...',
        for season in self.get_seasons():
            print season,
            show.append(E('season', num=str(season), feed=self.get_feed_url(season)))
        print 'OK'
        return show

class WatchHerePage(CtPage):
    """ CT Page with 'Watch here' link to EpPage """

    def __init__(self, url):
        """ Init obj """
        super(WatchHerePage, self).__init__(url)
        if not self.is_watch_here_page():
            raise PageTypeError('Not a Watch Here page')
        self.desc = ftfy.fix_text(self.entry.p.text)
        self.watch_here_link = get_abs_ct_url(self.entry.a['href'])

class EpPage(CtPage):
    """ CT episode player page """

    def __init__(self, url):
        super(EpPage, self).__init__(url)
        self.iframe_srcs = self._get_iframe_srcs()
        if len(self.iframe_srcs) == 0:
            raise NoSourceError('There are no valid iframe srcs on this page.')

    def _get_iframe_srcs(self):
        """ Return scrapeable iframe srcs for vids on Page """
        return [iframe['src'] for iframe in self.soup.select(
            '.postTabs_divs iframe') if get_host(iframe['src']) in HOSTS]


class SourcePage(Page):
    """ Source video embedded player page """

    def __init__(self, url, chrome):
        super(SourcePage, self).__init__(url)
        self.chrome = chrome
        self.host = get_host(url)
        self._flashvars = self._get_flashvars()
        if not self._flashvars:
            raise NoSourceError('FlashVars not found in %s' % self.url)
        self.mp4_url = self._get_mp4_url()
        if not self.mp4_url:
            raise NoSourceError('No mp4 url found in %s' % self.url)
        self.img_src = self._get_img_src()
        self.duration = self._get_fv_val('duration')

    def _get_flashvars(self):
        """ Return dict of flashvars """
        fv_vals = None
        try:
            self.chrome.get(self.url)
            fv_vals = parse_qs(self.chrome
                .find_element_by_name('flashvars')
                .get_attribute('value'))
            fv_vals = {k:v for k, v in fv_vals.items() if k in FV_ATTRS}
        except (NoSuchElementException, NoSuchAttributeException):
            pass
        except TimeoutException as err:
            print err,
        except WebDriverException as err:
            print err
        return fv_vals

    def _get_mp4_url(self):
        """ Return url of highest quality mp4 source """
        url = ''
        for attr in FILE_ATTRS:
            val = self._get_fv_val(attr)
            val_parts = urlsplit(val)
            val = urlunsplit((
                val_parts.scheme,
                val_parts.netloc,
                val_parts.path,
                '', ''))
            if val and val.endswith('.mp4'):
                url = val
                break
        return url

    def _get_img_src(self):
        """ Return img src """
        src = ''
        for attr in IMG_ATTRS:
            val = self._get_fv_val(attr)
            if val:
                src = val
                break
        return src

    @catch_key_error
    def _get_fv_val(self, key):
        """ Return value of key in _flashvars """
        return self._flashvars[key][0]

class PageTypeError(Exception):
    """ Errors thrown to indicate improper page initialization """
    pass

class NoSourceError(Exception):
    """ Errors thrown when page doesn't include appropriate source info """
    pass
