""" CT and co page objects """
import re
from time import sleep
from urlparse import urljoin, urlparse, parse_qs, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import ftfy
import requests
from selenium.common.exceptions import (
    WebDriverException, NoSuchElementException,
    NoSuchAttributeException)

from common import HOSTS, FV_ATTRS, FILE_ATTRS, IMG_ATTRS

def catch_key_error(func):
    """ Decorator logs key errors """
    def decorated(*args, **kwargs):
        result = ''
        try:
            result = func(*args, **kwargs)
        except KeyError as err:
            pass
        return result
    return decorated

def get_abs_ct_url(url):
    """ Return absolute url for CT page """
    return urljoin('http://www.couchtuner.eu', url)

def get_host(url):
    """ Return netloc aka host from url """
    return urlparse(url).netloc

def _sort_dicts(dicts, key):
    """ Return dicts sorted by key """
    keyed = [(d[key], d) for d in dicts]
    keyed.sort()
    return [x[1] for x in keyed]

@catch_key_error
def parse_ep_text(text):
    """ Return ep info from text """
    m = re.search(r'(?:S|Season )(?P<season>\d+)'
                             r' (?:E|Epis[o0]de )(?P<ep>\d+)(?:-\d+)?'
                             r'(?: ?\W+)? (?P<name>.*)',
                             text)
    season = int(m.group('season'))
    ep = int(m.group('ep'))
    name = m.group('name')
    return dict(season=season, num=ep, name=name)


class Page(object):
    """ Base class for all pages """

    def __init__(self, url):
        self.url = url
        self.soup = BeautifulSoup(self._get())

    def _get(self):
        """ Get response body for Page """
        # best balance between runtime and num of 503 errors
        sleep(0.4)
        res = requests.get(self.url)
        if res.status_code == 503:
            sleep(1)
            body = self._get()
        else:
            body = ftfy.fix_text(res.text)
        return body

class CtPage(Page):
    """ Base class for all CT pages """

    def __init__(self, url):
        super(CtPage, self).__init__(url)
        self.hdr = self.soup.find(class_='post').h2.text
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
            ep = parse_ep_text(li.text)
            if ep:
                if not season or ep['season'] == season:
                    eps.append(ep)
                    ep['url'] = get_abs_ct_url(li.a['href'])
                    ep['desc'] = ''
                    if detail:
                        try:
                            p = WatchHerePage(ep['url'])
                            ep['desc'] = p.desc
                            ep['url'] = p.watch_here_link
                        except PageTypeError:
                            pass
        eps = _sort_dicts(eps, 'num')
        return eps

    def get_seasons(self):
        """ Return sorted list of seasons """
        seasons = list(set([ep['season'] for ep in
            self.get_ep_list()]))
        return sorted(seasons)

    def get_latest_ep(self):
        """ Return dict(season=season, ep=ep) for latest ep """
        eps = self.get_ep_list()
        ssn_max = max(list({ep['season'] for ep in eps}))
        ssn_ep_max = max([ep['num'] for ep in  eps if ep['season'] == ssn_max])
        return dict(season=ssn_max, ep=ssn_ep_max)

    def _print_eps_by_season(self):
        """ Print basic ep info for show """
        latest = self.get_latest_ep()
        print 'Latest ep: S%i E%s' % (latest['season'], latest['ep'])
        seasons = range(1, latest['season'] + 1)
        for ssn in seasons:
            print 'Season %i' % ssn
            for ep in self.get_ep_list(ssn):
                print 'S%i E%i: %r' % (ep['season'], ep['num'], ep['name'])
            print


class WatchHerePage(CtPage):
    """ CT Page with 'Watch here' link to EpPage """

    def __init__(self, url):
        """ Init obj """
        super(WatchHerePage, self).__init__(url)
        if not self.is_watch_here_page():
            raise PageTypeError('Not a Watch Here page')
        self.desc = self.entry.p.text
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
            raise NoSourceError(
                'FlashVars not found in %s' % self.url)
        self.mp4_url = self._get_mp4_url()
        if not self.mp4_url:
            raise NoSourceError(
                'No mp4 url found in %s' % self.url)
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
            # change this part to strip query string first
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

