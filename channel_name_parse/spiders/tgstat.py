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


def solve_with_2captcha(sitekey, driver):
    # start the 2CAPTCHA instance
    captcha2_api_key = os.getenv("API_KEY_CAPTCHA")
    solver = TwoCaptcha(captcha2_api_key)

    try:
        # Solve the Captcha
        result = solver.recaptcha(sitekey=sitekey, url=driver.current_url)
        code = result['code']

        # Set the solved Captcha
        elem_hidden = driver.find_element(By.CSS_SELECTOR, '#g-recaptcha-response')
        driver.execute_script("arguments[0].style.display = 'block';", elem_hidden)
        elem_hidden.send_keys(code)

        # Submit the form
        driver.execute_script('onloadCallback()')
        # submit_btn = driver.find_element(By.CSS_SELECTOR, 'span[role="checkbox"]')
        # submit_btn.click()
        return 'Ok'

    except Exception as e:
        print(e)
        return None


class TgstatSpider(scrapy.Spider):
    name = "tgstat"
    # allowed_domains = ["tgstat.ru"]
    # start_urls = ["https://tgstat.ru/en/login"]
    auth_url = "https://tgstat.ru/en/auth"
    url_start = 'https://tgstat.ru/en'
    bucket_name = '24825ad4-e2369fbe-f825-4ba9-9c6e-f9de1573149f'

    def __init__(self, work_account, api_id, api_hash, proxy, category_list, s3, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.work_account = work_account
        self.api_id = api_id
        self.api_hash = api_hash
        self.proxy = proxy
        self.category_list = category_list
        self.s3 = s3
        self.db = db
        self.count_category = 0

    def start_requests(self):
        url = "https://tgstat.ru/en/login"
        yield scrapy.Request(url=url, callback=self.parse)

    async def parse(self, response: HtmlResponse):
        auth_key = re.search(r'data-telegram-auth-button="(.*)"\n', response.text)
        bot_username = 'https://t.me/tg_analytics_bot'
        # получить auth_key из data-telegram-auth-button
        async with TelegramClient(self.work_account, self.api_id, self.api_hash, proxy=self.proxy) as client:
            await client.send_message(bot_username, f'/start {auth_key.group(1)}')
            message = await client.get_messages(bot_username, limit=1)
            while True:
                if message[0] and message[0].sender_id == 433791261:  # Проверяем, что сообщение отправлено ботом
                    await message[0].click(0)
                    break
                else:
                    message = await client.get_messages(bot_username, limit=1)
        yield scrapy.FormRequest(
            self.auth_url,
            method='POST',
            callback=self.login,
            formdata={'auth_key': auth_key.group(1)}
        )

    def login(self, response: HtmlResponse):
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
        # links_category = response.xpath('//a[starts-with(@href, "/en/") and @class="text-dark"]')
        # for link in self.category_list:
        #     if link.split('/')[-1] != "courses":
        #         self.count_category = self.count_category + 1
        #         continue

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
        driver = response.request.meta['driver']
        if 'Suspicion of a robot - 429' in response.text:
            # specify reCAPTCHA sitekey, replace with the target site key
            sitekey_match = re.search(r"'sitekey': '([^']+)'", response.text)

            # call the CAPTCHA solving function
            captcha_solved = solve_with_2captcha(sitekey_match.group(1), driver)
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
        if len(self.category_list) > self.count_category:
            yield SeleniumRequest(
                url=f'{self.url_start}/{self.category_list[self.count_category].split("/")[-1]}',
                callback=self.parse_channels,
                cookies=cookie,
                cb_kwargs={"cookie": cookie}
            )

        for channel in names_channel:
            parse_channel_name = channel.attrib.get("href").split('/')[-1]
            if '@' in parse_channel_name:
                async with TelegramClient(self.work_account, self.api_id, self.api_hash, proxy=self.proxy) as client:
                    channel, messages = await main(parse_channel_name, client, self.db, self.s3)
                    if channel['avatar']:
                        checksum_name_file_profile = hashlib.sha256(channel['avatar'].file_reference).hexdigest()
                        file_name = ''
                        if not self.check_file_exists(self.bucket_name, f'photo/{checksum_name_file_profile}.jpg'):
                            file_name = await download_image(channel['avatar'], checksum_name_file_profile, client, self.s3)
                        channel['avatar'] = channel['avatar'].to_dict()
                        channel['file_name'] = file_name
                    messages_result = []
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
