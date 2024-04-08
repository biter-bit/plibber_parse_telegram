import scrapy
from scrapy import FormRequest
from scrapy.http import HtmlResponse
from selenium.webdriver.support.wait import WebDriverWait
from telethon import TelegramClient
import re
import json
from scrapy.selector import Selector
from channel_name_parse.items import ChannelNameParseItem
from hashlib import sha256
from twocaptcha import TwoCaptcha
from scrapy_selenium import SeleniumRequest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
from channel_name_parse.telegram_parsing import main, download_image
import asyncio
import hashlib, os
from channel_name_parse.service import solve_with_2captcha


class TgstatSpider(scrapy.Spider):
    name = "tgstat"
    url_start = 'https://tgstat.ru/en'
    bucket_name = '24825ad4-e2369fbe-f825-4ba9-9c6e-f9de1573149f'

    def __init__(self, work_account, api_id, api_hash, proxy, category_list, s3, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # относительный путь до session
        self.work_account = work_account

        # api_id и api_hash приложения тг
        self.api_id = api_id
        self.api_hash = api_hash

        self.proxy = proxy

        # текущий номер категории и сами категории tgstat, с которыми работает данных аккаунт
        self.count_category = 0
        self.category_list = category_list

        # данные хранилища s3 и текущей базы данных
        self.s3 = s3
        self.db = db

    def start_requests(self):
        """Делает первые запросы на страницу авторизации и ответ передает методу parse"""
        url = "https://tgstat.ru/en/login"
        yield scrapy.Request(url=url, callback=self.parse)

    async def parse(self, response: HtmlResponse):
        """Подтверждает авторизацию в боте телеграм (отправляем ключ боту и подтверждаем по url)"""

        # проверка капчи, если сработала 429
        if 'Suspicion of a robot - 429' in response.text:
            # specify reCAPTCHA sitekey, replace with the target site key
            sitekey_match = re.search(r"'sitekey': '([^']+)'", response.text)

            # call the CAPTCHA solving function
            captcha_solved = solve_with_2captcha(sitekey_match.group(1), driver)

        # получаем ключ для отправки его боту и ссылку на бота
        auth_key = re.search(r'data-telegram-auth-button="(.*)"\n', response.text)
        bot_username = 'https://t.me/tg_analytics_bot'

        # отправляем ключ боту и проверяем
        async with TelegramClient(self.work_account, self.api_id, self.api_hash, proxy=self.proxy) as client:
            await client.send_message(bot_username, f'/start {auth_key.group(1)}')
            message = await client.get_messages(bot_username, limit=1)
            bot_check_id = 433791261
            while True:
                # Проверяем, что сообщение отправлено ботом
                if message[0] and message[0].sender_id == bot_check_id:
                    await message[0].click(0)
                    break
                else:
                    message = await client.get_messages(bot_username, limit=1)
        yield scrapy.FormRequest(
            "https://tgstat.ru/en/auth",
            method='POST',
            callback=self.login,
            formdata={'auth_key': auth_key.group(1)}
        )

    def login(self, response: HtmlResponse):
        """Получает все данные авторизированного пользователя и переходим на стартовую страницу с Selenium"""
        received_cookie = response.headers.getlist('Set-Cookie')
        dict_cookie = {}
        for i in received_cookie:
            dict_cookie[i.decode().split(';')[0].split('=')[0]] = i.decode().split(';')[0].split('=')[1]

        yield SeleniumRequest(
            url=self.url_start,
            callback=self.category_parse,
            cookies=dict_cookie,
            cb_kwargs={"cookie": dict_cookie}
        )

    def category_parse(self, response: HtmlResponse, cookie: dict):
        """Делает переход на определенную категорию каналов тг"""

        # проверка капчи, если сработала 429
        if 'Suspicion of a robot - 429' in response.text:
            # specify reCAPTCHA sitekey, replace with the target site key
            sitekey_match = re.search(r"'sitekey': '([^']+)'", response.text)

            # call the CAPTCHA solving function
            captcha_solved = solve_with_2captcha(sitekey_match.group(1), driver)

        for link in self.category_list:
            if link.split('/')[-1] != "courses":
                self.count_category = self.count_category + 1
                continue

            yield SeleniumRequest(
                url=f'{self.url_start}/{self.category_list[self.count_category].split("/")[-1]}',
                callback=self.parse_channels,
                cookies=cookie,
                cb_kwargs={"cookie": cookie},
                wait_time=10,
                wait_until=EC.element_to_be_clickable(
                    (By.XPATH, "//button[@class='btn btn-light border lm-button py-1 min-width-220px']"))
                )

    async def parse_channels(self, response: HtmlResponse, cookie: dict):
        """Раскрывает страницу группы, парсит инфу каждого канала группы (доб. в бд и скачивание картинок на s3)"""
        driver = response.request.meta['driver']

        # проверка капчи, если сработала 429
        if 'Suspicion of a robot - 429' in response.text:
            # specify reCAPTCHA sitekey, replace with the target site key
            sitekey_match = re.search(r"'sitekey': '([^']+)'", response.text)

            # call the CAPTCHA solving function
            captcha_solved = solve_with_2captcha(sitekey_match.group(1), driver)

        # раскрываем страницу полностью (все каналы)
        while True:
            try:
                button = driver.find_element(By.XPATH, "//*[@class='btn btn-light border lm-button py-1 min-width-220px']")
                button.click()
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "//button[@class='btn btn-light border lm-button py-1 min-width-220px']"))
                )
            except NoSuchElementException:
                break
            except TimeoutException:
                break

        # Создаем объект Selector из HTML-кода
        selector = Selector(text=driver.page_source)
        names_channel = selector.xpath(
            '//div[@class="card card-body peer-item-box py-2 mb-2 mb-sm-3 border border-info-hover position-relative"]/a[@class="text-body"]'
        )

        self.count_category = self.count_category + 1

        # проверяем нужно ли еще просмотреть какую-либо категорию для данного пользователя
        if len(self.category_list) > self.count_category:
            yield SeleniumRequest(
                url=f'{self.url_start}/{self.category_list[self.count_category].split("/")[-1]}',
                callback=self.parse_channels,
                cookies=cookie,
                cb_kwargs={"cookie": cookie}
            )

        # парсим информацию по каждому каналу тг данной категории
        for channel in names_channel:
            parse_channel_name = channel.attrib.get("href").split('/')[-1]
            if '@' in parse_channel_name:
                async with TelegramClient(self.work_account, self.api_id, self.api_hash, proxy=self.proxy) as client:

                    # парсинг постов канала
                    channel, messages = await main(parse_channel_name, client, self.db, self.s3)

                    # проверка на наличие аватарки канала, после скачивание в s3
                    if channel['avatar']:
                        checksum_name_file_profile = hashlib.sha256(channel['avatar'].file_reference).hexdigest()
                        file_name = ''

                        # проверка на наличие файла в s3
                        if not self.check_file_exists(self.bucket_name, f'photo/{checksum_name_file_profile}.jpg'):
                            file_name = await download_image(channel['avatar'], checksum_name_file_profile, client, self.s3)
                        channel['avatar'] = channel['avatar'].to_dict()
                        channel['file_name'] = file_name

                    messages_result = []

                    # каждое сообщение канала скачивается и доб. в mesages_result
                    for message in messages:
                        if message['photo']:
                            access_hash_bytes = message['photo'].file_reference
                            checksum_name_file = hashlib.sha256(access_hash_bytes).hexdigest()
                            file_name = ''
                            if not self.check_file_exists(self.bucket_name, f'photo/{checksum_name_file}.jpg'):
                                file_name = await download_image(message['photo'], checksum_name_file, client, self.s3)
                            message['photo'] = message['photo'].to_dict()
                            message['photo']['file_name'] = file_name
                            messages_result.append(message)

                item = ChannelNameParseItem(
                    _id=sha256(parse_channel_name.encode('utf-8')).hexdigest(),
                    name_channel=parse_channel_name,
                    channel_info=channel,
                    messages=messages_result,
                )
                yield item
            else:
                print("Имя без '@'")

    def check_file_exists(self, bucket_name, file_path):
        try:
            self.s3.head_object(Bucket=bucket_name, Key=file_path)
            return True  # Файл существует
        except self.s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False  # Файл не существует
            else:
                raise  # Обработка других ошибок
