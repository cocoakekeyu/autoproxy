#! -*- coding: utf-8 -*-

from scrapy.spiders import Spider
import scrapy
import os
import json
from StringIO import StringIO
from datetime import datetime
from PIL import Image


class HuabanSpider(Spider):
    name = "huaban"
    start_urls = ["http://huaban.com/favorite/beauty/"]

    def __init__(self):
        super(HuabanSpider, self).__init__()
        self.depth = 0
        self.next_urlid = None

    def parse(self, response):

        # print('response_status[%s],response: %s' % (response.status, response.body))

        sel = response.xpath('//body/script[1]/text()')

        jsonstr = sel.re(r'\["pins"\]\s*=\s*(.*}\]);')[0]
        objects = json.loads(jsonstr)

        for obj in objects:
            image_name = obj['board']['title'].encode('utf-8')
            image_url = 'http://hbimg.b0.upaiyun.com/' + obj['file']['key'].encode('utf-8')
            self.next_urlid = str(obj['pin_id'])
            yield scrapy.Request(url=image_url, callback=lambda res, b=image_name: self.pasre_image_url(res, b))

        self.depth += 1

        if(self.depth < 40):
            next_url = ''.join([self.start_urls[0], '?isvvu30d&max=', self.next_urlid, '&limit=20&wfl=1'])
            yield scrapy.Request(url=next_url, callback=self.parse)

    def pasre_image_url(self, response, image_name):

            if response.status == 200:
                image_name = image_name.replace('/', '.')
                im = Image.open(StringIO(response.body))
                des_dir = '美女' + os.sep
                if(not os.path.exists(des_dir)):
                    os.mkdir(des_dir)

                filename = ''.join([des_dir, image_name, '-', datetime.today().strftime('%Y%m%d%H%M%S'), '.', im.format])
                im.save(filename)
                print('写入文件:%s' % filename)
            else:
                print response.status
