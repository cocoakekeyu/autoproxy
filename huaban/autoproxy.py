#! -*- coding: utf-8 -*-
import urllib2
import logging
import threading
import math
import re

from bs4 import BeautifulSoup
from twisted.internet import defer
from twisted.internet.error import TimeoutError, ConnectionRefusedError, \
    ConnectError, ConnectionLost, TCPTimedOutError, ConnectionDone

logger = logging.getLogger(__name__)


class AutoProxyMiddleware(object):

    EXCEPTIONS_TO_CHANGE = (defer.TimeoutError, TimeoutError, ConnectionRefusedError, ConnectError, ConnectionLost, TCPTimedOutError, ConnectionDone)

    _settings = [
        ('enable', True),
        ('test_urls', [('http://www.w3school.com.cn', '06004630'), ]),
        ('test_proxy_timeout', 5),
        ('download_timeout', 60),
        ('test_threadnums', 20),
        ('ban_code', [503, ]),
        ('ban_re', r''),
        ('proxy_least', 3),
        ('init_valid_proxys', 1),
        ('invalid_limit', 200),
    ]

    def __init__(self, proxy_set=None):
        self.proxy_set = proxy_set or {}
        for k, v in self._settings:
            setattr(self, k, self.proxy_set.get(k, v))

        # 代理列表和当前的代理指针，couter_proxy用作该代理下载的网页数量
        self.proxy = []
        self.proxy_index = 0
        self.proxyes = {}
        self.counter_proxy = {}

        self.fecth_new_proxy()
        self.test_proxyes(self.proxyes, wait=True)
        logger.info('Use proxy : %s', self.proxy)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings.getdict('AUTO_PROXY'))

    def process_request(self, request, spider):
        if not self._is_enabled_for_request(request):
            return

        if self.len_valid_proxy() > 0:
            self.set_proxy(request)
            # if 'download_timeout' not in request.meta:
            request.meta['download_timeout'] = self.download_timeout
        else:
            # 没有可用代理，直连
            if 'proxy' in request.meta:
                del request.meta['proxy']

    def process_respose(self, request, response, spider):
        if not self._is_enabled_for_request(request):
            return response

        if response.status in self.ban_code:
            self.invaild_proxy(request.meta['proxy'])
            logger.debug("Proxy[%s] ban because return httpstatuscode:[%s]. ", request.meta['proxy'], str(response.status))
            new_request = request.copy()
            new_request.dont_filter = True
            return new_request

        if self.re:
            try:
                pattern = re.compile(self.re)
            except TypeError:
                logger.error('Wrong "ban_re", please check settings')
                return response
            match = re.search(pattern, response.body)
            if match:
                self.invaild_proxy(request.meta['proxy'])
                logger.debug("Proxy[%s] ban because pattern match:[%s]. ", request.meta['proxy'], str(match))
                new_request = request.copy()
                new_request.dont_filter = True
                return new_request

        p = request.meta['proxy']
        self.counter_proxy[p] = self.counter_proxy.setdefault(p, 1) + 1
        return response

    def process_exception(self, request, exception, spider):
        if isinstance(exception, self.EXCEPTIONS_TO_CHANGE) \
                and request.meta.get('proxy', False):
            self.invaild_proxy(request.meta['proxy'])
            logger.debug("Proxy[%s] connect exception[%s].", request.meta['proxy'], exception)
            new_request = request.copy()
            new_request.dont_filter = True
            return new_request

    def invaild_proxy(self, proxy):
        """
        将代理设为invaild。如果之前该代理已下载超过200页（默认）的资源，则暂时不设置，仅切换代理，并减少其计数。
        """
        if self.counter_proxy.get(proxy, 0) > self.invalid_limit:
            self.counter_proxy[proxy] = self.counter_proxy.get(proxy, 0) - 50
            if self.counter_proxy[proxy] < 0:
                self.counter_proxy[proxy] = 0
            self.change_proxy()
        else:
            self.proxyes[proxy] = False
            # logger.info('Set proxy[%s] invaild.', proxy)

    def change_proxy(self):
        """
        切换代理。
        """
        while True:
            self.proxy_index = (self.proxy_index + 1) % len(self.proxy)
            proxy_valid = self.proxyes[self.proxy[self.proxy_index]]
            if proxy_valid:
                break
            if self.len_valid_proxy() == 0:
                logger.info('Available proxys is none.Waiting for fecth new proxy.')
                break
        logger.info('Change proxy to %s', self.proxy[self.proxy_index])
        logger.info('Available proxys[%s]: %s', self.len_valid_proxy(), self.valid_proxyes())

        # 可用代理数量小于预设值则扩展代理
        if self.len_valid_proxy() < self.proxy_least:
            self.extend_proxy()

    def set_proxy(self, request):
        """
        设置代理。
        """
        proxy_valid = self.proxyes[self.proxy[self.proxy_index]]
        if not proxy_valid:
            self.change_proxy()

        request.meta['proxy'] = self.proxy[self.proxy_index]
        # logger.info('Set proxy. request.meta: %s', request.meta)

    def len_valid_proxy(self):
        """
        计算可用代理的数量
        """
        count = 0
        for p in self.proxy:
            if self.proxyes[p]:
                count += 1
        return count

    def valid_proxyes(self):
        """
        可用代理列表
        """
        proxyes = []
        for p in self.proxy:
            if self.proxyes[p]:
                proxyes.append(p)
        return proxyes

    def extend_proxy(self):
        """
        扩展代理。测试代理是异步的。
        """
        self.fecth_new_proxy()
        self.test_proxyes(self.proxyes)

    def append_proxy(self, p):
        """
        辅助函数，将测试通过的代理添加到列表
        """
        if p not in self.proxy:
            self.proxy.append(p)

    def fecth_new_proxy(self):
        """
        获取新的代理，目前从三个网站抓取代理，每个网站开一个线程抓取代理。
        """
        logger.info('Starting fecth new proxy.')
        urls = ['xici', 'ip3336', 'kxdaili']
        threads = []
        for url in urls:
            t = ProxyFecth(self.proxyes, url)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def test_proxyes(self, proxyes, wait=False):
        """
        测试代理可通性。测试网址、特征码以及测试线程数均可设置。
        """
        list_proxy = proxyes.items()
        threads = []
        n = int(math.ceil(len(list_proxy) / self.test_threadnums))
        for i in range(self.test_threadnums):
            # 将待测试的代理平均分给测试线程
            list_part = list_proxy[i * n: (i + 1) * n]
            part = {k: v for k, v in list_part}
            t = ProxyValidate(self, part)
            threads.append(t)
            t.start()

        # 初始化该中间件时，等待有可用的代理
        if wait:
            while True:
                for t in threads:
                    t.join(0.2)
                    if self._has_valid_proxy():
                        break
                if self._has_valid_proxy():
                        break

    def _has_valid_proxy(self):
        if self.len_valid_proxy() >= self.init_valid_proxys:
            return True

    def _is_enabled_for_request(self, request):
        return self.enable and 'dont_proxy' not in request.meta


class ProxyValidate(threading.Thread):
    """
    测试代理线程类
    """

    def __init__(self, autoproxy, part):
        super(ProxyValidate, self).__init__()
        self.autoproxy = autoproxy
        self.part = part

    def run(self):
        self.test_proxyes(self.part)

    def test_proxyes(self, proxyes):
        for proxy, valid in proxyes.iteritems():
            if(self.check_proxy(proxy)):
                self.autoproxy.proxyes[proxy] = True
                self.autoproxy.append_proxy(proxy)

    def check_proxy(self, proxy):
        proxy_handler = urllib2.ProxyHandler({'http': proxy})
        opener = urllib2.build_opener(proxy_handler, urllib2.HTTPHandler)
        try:
            for url, code in self.autoproxy.test_urls:
                resbody = opener.open(url, timeout=self.autoproxy.test_proxy_timeout).read()
                if code not in resbody:
                    return False
            return True
        except Exception:
            return False


class ProxyFecth(threading.Thread):

    def __init__(self, proxyes, url):
        super(ProxyFecth, self).__init__()
        self.proxyes = proxyes
        self.url = url

    def run(self):
        self.proxyes.update(getattr(self, 'fecth_proxy_from_' + self.url)())

    def fecth_proxy_from_xici(self):
        proxyes = {}
        url = "http://www.xicidaili.com/nn/"
        try:
            for i in range(1, 4):
                soup = self.get_soup(url + str(i))
                trs = soup.find("table", attrs={"id": "ip_list"}).find_all("tr")
                for i, tr in enumerate(trs):
                    if(0 == i):
                        continue
                    tds = tr.find_all('td')
                    ip = tds[1].text
                    port = tds[2].text
                    proxy = ''.join(['http://', ip, ':', port]).encode('utf-8')
                    proxyes[proxy] = False
        except Exception as e:
            logger.error('Failed to fecth_proxy_from_xici. Exception[%s]', e)

        return proxyes

    def fecth_proxy_from_ip3336(self):
        proxyes = {}
        url = 'http://www.ip3366.net/free/?stype=1&page='
        try:
            for i in range(1, 6):
                soup = self.get_soup(url + str(i))
                trs = soup.find("div", attrs={"id": "list"}).table.find_all("tr")
                for i, tr in enumerate(trs):
                    if 0 == i:
                        continue
                    tds = tr.find_all("td")
                    ip = tds[0].string.strip().encode('utf-8')
                    port = tds[1].string.strip().encode('utf-8')
                    proxy = ''.join(['http://', ip, ':', port])
                    proxyes[proxy] = False
        except Exception as e:
            logger.error('Failed to fecth_proxy_from_ip3336. Exception[%s]', e)

        return proxyes

    def fecth_proxy_from_kxdaili(self):
        proxyes = {}
        url = 'http://www.kxdaili.com/dailiip/1/%d.html'
        try:
            for i in range(1, 11):
                soup = self.get_soup(url % i)
                trs = soup.find("table", attrs={"class": "ui table segment"}).find_all("tr")
                for i, tr in enumerate(trs):
                    if 0 == i:
                        continue
                    tds = tr.find_all("td")
                    ip = tds[0].string.strip().encode('utf-8')
                    port = tds[1].string.strip().encode('utf-8')
                    proxy = ''.join(['http://', ip, ':', port])
                    proxyes[proxy] = False
        except Exception as e:
            logger.error('Failed to fecth_proxy_from_kxdaili. Exception[%s]', e)

        return proxyes

    def get_soup(self, url):
        request = urllib2.Request(url)
        request.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit\/537.36 (KHTML, like Gecko) Chrome/47.0.2526.106 Safari/537.36")
        html_doc = urllib2.urlopen(request).read()

        soup = BeautifulSoup(html_doc)

        return soup


if __name__ == '__main__':

    AutoProxyMiddleware()
