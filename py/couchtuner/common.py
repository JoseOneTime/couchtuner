""" Common constants, classes and functions """
import os

from selenium import webdriver

SHOWS = {
    'game of thrones': dict(url='http://www.couchtuner.eu/watch-game-of-thrones-online-free/', id_=0),
    'lost girl': dict(url='http://www.couchtuner.eu/watch-lost-girl/', id_=1),
    'new girl': dict(url='http://www.couchtuner.eu/watch-new-girl-online/', id_=2),
    'once upon a time': dict(url='http://www.couchtuner.eu/watch-once-upon-a-time-online/', id_=3),
    'psych': dict(url='http://www.couchtuner.eu/psych/', id_=4),
    'sherlock': dict(url='http://www.couchtuner.eu/sherlock/', id_=5),
    'sons of anarchy': dict(url='http://www.couchtuner.eu/watch-sons-of-anarchy-online-1/', id_=6)
}

HOSTS = {
    'vidbull.com': 3000,
    'vk.com': 1400,
    'played.to': 1200,
    'vshare.eu': 1100,
    'youwatch.org': 1000
}

# quality high -> low
FILE_ATTRS = [
    'file', 'url1080', 'url720', 'url480', 'url360', 'url240'
]

# arbitrary order
IMG_ATTRS = {'image', 'jpg', 'jpeg'}

FV_ATTRS = IMG_ATTRS.union(FILE_ATTRS)

S3_URL = 'http://xtcouchtuner.s3-website-us-east-1.amazonaws.com/shows/'

# selenium code
def _get_adblock_crx():
    """ Returns path to Chrome AdBlock crx file """
    path = None
    try:
        path = os.environ['ADBLOCK_CRX']
    except KeyError:
        print 'ADBLOCK_CRX environment variable not found.'
        print 'ChromeDriver will be started without AdBlock.'
    return path

def _get_chromedriver_with_options(options=None):
    """ Return instance of Chrome with given options enabled """
    chrome = webdriver.Chrome(chrome_options=options)
    chrome.implicitly_wait(5)
    return chrome

def start_chromedriver():
    """ Return ChromeDriver instance """
    chrome = None
    crx_path = _get_adblock_crx()
    if crx_path:
        options = webdriver.chrome.options.Options()
        options.add_extension(crx_path)
        chrome = _get_chromedriver_with_options(options)
        print 'Initializing ChromeDriver with AdBlock...'
        chrome.find_element_by_id('paypal-xclick-form')
        print 'AdBlock is installed.'
    else:
        chrome = _get_chromedriver_with_options()
    return chrome
