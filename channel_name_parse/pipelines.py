# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter
from pymongo import MongoClient
from scrapy.pipelines.images import ImagesPipeline, FilesPipeline
import scrapy
from PIL import Image
from io import BytesIO
from telethon.sync import TelegramClient
import hashlib
from channel_name_parse.telegram_parsing import download_image


class ChannelNameParsePipeline:
    def __init__(self):
        super().__init__()
        client = MongoClient('127.0.0.1', 27017)
        self.mongo_base = client.channels_tg

    def process_item(self, item, spider):
        collections_item = self.mongo_base['tg_parse_channel']
        if not collections_item.find_one({'_id': item['_id']}):
            collections_item.insert_one(item)
        return item


# class ChannelNameParseImagesPipeline:
#
#     def process_item(self, item, spider):
#         pass
#
#     def get_media_requests(self, item, info):
#         pass
#
#     def item_completed(self, results, item, info):
#         return item
