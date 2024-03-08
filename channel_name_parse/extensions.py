from telethon import TelegramClient
from scrapy import signals
import os


class TelegramExtension:
    def __init__(self, api_id, api_hash, proxy, path_account):
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy = proxy
        self.path_account = path_account
        self.client = None

    @classmethod
    def from_crawler(cls, crawler):
        api_id = crawler.spider.custom_settings['API_ID_TELEGRAM']
        api_hash = crawler.spider.custom_settings['API_HASH_TELEGRAM']
        proxy = crawler.spider.custom_settings['PROXY_TELEGRAM']
        path_account = crawler.spider.custom_settings['PATH_ACCOUNT_TELEGRAM']
        ext = cls(api_id, api_hash, proxy, path_account)
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_opened(self, spider):
        self.client = TelegramClient(self.path_account, self.api_id, self.api_hash, proxy=self.proxy)
        spider.telegram_client = self.client

    def spider_closed(self, spider):
        if self.client.is_connected():
            self.client.disconnect()
