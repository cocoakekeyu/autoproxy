# AutoProxyMiddleware

## 简介
一个用于scrapy爬虫的自动代理中间件。可自动抓取和切换代理，自定义抓取和切换规则。

## 用法
将中间件模块放置到项目中，并在项目设置文件中添加该中间件。如
```python
DOWNLOADER_MIDDLEWARES = {
    'projectname.autoproxy.AutoProxyMiddleware': 543,
}
```

## 配置
可在项目配置文件中使用`AUTO_PROXY`配置项配置代理中间件。如
```python
AUTO_PROXY = {
	'test_urls':[('http://upaiyun.com','online'),('http://huaban.com', '33010602001878')],
	'ban_code':[500,502,503,504],
}
```
**所有可用配置**
- `'enable'`: 一个布尔值，是否启用该中间件。默认为`True`
- `'test_urls'`: 一个二元组的列表，网址+特征码(返回的网页内容中能找到的特定值)，用作代理连接的测试。默认为`[('http://www.w3school.com.cn', '06004630'), ]`
- `'test_proxy_timeout'`: 大于0的整数，用于测试代理时连接超时设置。默认为`5`
- `'download_timeout'`: 大于0的整数，与scrapy的`download_timeout`一样，启用该中间件则设置。默认为`60`
- `'test_threadnums'`: 大于0的整数，启动测试代理的线程数。默认为`20`
- `'ban_code'`: 一个列表，代理被禁用的http状态码。确认返回状态码在此范围可自动切换代理。默认为`[503,]`
- `'ban_re'`: 正则表达式字符串，代理被禁用返回的页面内容包含匹配正则式的内容，则切换代理，若为空则不启用。默认为`r''`
- `'proxy_least'`: 大于0的整数， 若代理池可用数量小于它则自动抓取新的代理。默认为`3`
- `'init_valid_proxys'`: 大于0的整数， 初始化爬虫时等待的可用代理数量。数值大会导致初始化比较慢，在爬虫进行中也可以同时测试保存的代理。默认为`1`
- `'invalid_limit'`: 大于0的整数，每个代理成功下载到页面时都会对其计数，若突然无法连接或者被网站拒绝将对这个代理进行invaild操作，若代理爬取的页面数大于该设置数值，则暂时不invaild，切换至另一个代理，并减少其页面计数。默认为`200`
