# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/en/latest/topics/item-pipeline.html

import requests
from datetime import datetime
from PIL import Image
from StringIO import StringIO

class StoreItemPipeline(object):
    def process_item(self, item, spider):
        res = requests.get(item['url'])
        print('requests success')
        if res.status_code == 200:
            print('log here')
            im = Image.open(StringIO(res.content))
            filename = ''.join(['美女/', item['name'].encode('utf-8'), '-', datetime.today().strftime('%Y%m%d%H%M%S'), '.', im.format])
            print(type(filename))
            print(filename)
            #return item
            im.save(filename)
        else:
            print res.status


        return item
