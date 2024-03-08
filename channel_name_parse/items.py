# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ChannelNameParseItem(scrapy.Item):
    _id = scrapy.Field()
    name_channel = scrapy.Field()
    channel_info = scrapy.Field()
    messages = scrapy.Field()
    photo_byte = scrapy.Field()
    file_path = scrapy.Field()
