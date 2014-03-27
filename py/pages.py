""" CT and co page objects """
import re
from time import sleep
from urlparse import urljoin

from bs4 import BeautifulSoup
import ftfy
import requests

def catch_key_error(func):
    """ Decorator logs key errors """
    def decorated(*args, **kwargs):
        result = None
        try:
            result = func(*args, **kwargs)
        except KeyError as err:
            print 'KeyError in %s: %s' % (func.__name__, err)
        return result
    return decorated

def get_abs_ct_url(url):
    """ Return absolute url for CT page """
    return urljoin('http://www.couchtuner.eu', url)

def _sort_dicts(dicts, key):
    """ Return dicts sorted by key """
    keyed = [(d[key], d) for d in dicts]
    keyed.sort()
    return [x[1] for x in keyed]

@catch_key_error
def parse_ep_text(text):
    """ Return ep info from text """
    m = re.search('(?:S|Season )(?P<season>\d+)'
                             ' (?:E|Epis[o0]de )(?P<ep>\d+)(?:-\d+)?'
                             '(?: ?\W+)? (?P<name>.*)',
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
            body = self.get()
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

    @catch_key_error
    def get_name(self):
        """ Return show name """
        return re.match('Watch (.*) [Oo]nline', self.hdr).group(1)

    def get_img_src(self):
        """ Return show img src """
        return get_abs_ct_url(self.entry.img['src'])

    def get_ep_list(self, season=None):
        """ Return episode list for single or all seasons """
        eps = []
        for li in self.entry.find_all('li'):
            ep = parse_ep_text(li.text)
            if ep:
                if not season or ep['season'] == season:
                    eps.append(ep)
        eps = _sort_dicts(eps, 'num')
        return eps

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
