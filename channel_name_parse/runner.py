from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import dotenv, os, re
from checkers import main_checker
from exceptions import ErrorCheckNotTrue
from bs4 import BeautifulSoup
from service import create_logger
import multiprocessing
from telethon import TelegramClient
from pymongo import MongoClient
import boto3
from botocore.client import Config
from spiders.tgstat import TgstatSpider
import requests, math


def start_worker_parser(
        num_process, count_workers, work_accounts, work_proxys, api_id, api_hash, categories_for_everyone,
        groups_tgstat_links
):
    # Запускаем главную корутину (клиент)
    process = CrawlerProcess(settings=get_project_settings())
    for num_worker in range(num_process*count_workers, num_process*count_workers+count_workers):

        # берем прокси для данного паука и приводим его к нужному формату
        proxy_data = re.split(r'[:@]', work_proxys[num_worker])
        proxy = {
            'proxy_type': 'http',
            'addr': proxy_data[2],
            'port': proxy_data[3],
            'username': proxy_data[0],
            'password': proxy_data[1],
            'rdns': True
        }

        # доб. кастомную настройку для паука
        custom_settings_group = {
            'ROTATING_PROXY_LIST': [work_proxys[num_worker]],
        }
        spider = TgstatSpider
        spider.custom_settings = custom_settings_group
        spider.settings = get_project_settings().copy()
        spider.settings.update(custom_settings_group)

        # индекс начала и конца категорий, с которыми должен работать паук
        start_ind_category = num_worker*categories_for_everyone
        end_ind_category = num_worker*categories_for_everyone+categories_for_everyone

        # запуск паука
        process.crawl(
            spider, work_accounts[num_worker], api_id, api_hash, proxy,
            groups_tgstat_links[start_ind_category:end_ind_category], s3, db
        )

    process.start()


def start_process_parser(
        count_process, count_workers, work_proxys, work_accounts, api_id, api_hash, groups_tgstat_links, count_groups_tgstat
):
    """Запускает процессы парсера"""

    # список всех процессов
    processes = []

    # запуск процессов
    for num_process in range(0, count_process):
        print(f"Запуск процесса № {num_process + 1}...")

        # добавляем общее кол-во запущенных пауков в переменную
        workers_count = count_workers*count_process

        # добавляем кол-во групп для каждого паука
        categories_for_everyone = math.ceil(count_groups_tgstat/workers_count)

        # создаем обьект процесса
        process = multiprocessing.Process(target=start_worker_parser,
                                          args=(
                                              num_process,
                                              count_workers,
                                              work_accounts,
                                              work_proxys,
                                              api_id,
                                              api_hash,
                                              categories_for_everyone,
                                              groups_tgstat_links
                                          ))

        # добавляем обьект в список процессов
        processes.append(process)

        # запускаем процесс
        process.start()

    # ожидаем завершения каждого процесса
    for process in processes:
        process.join()

    print("Все процессы закончили работу.")


def run():
    # загружаем переменные окружения из .env
    dotenv.load_dotenv()

    # добавляем настройки логгера и выводим первый лог
    logger = create_logger('parse_telegram')
    logger.info("Starting telegram parsing")

    # добавляем настройки подключения telegram (api_id, api_hash)
    api_id = int(os.getenv('API_ID'))
    api_hash = os.getenv('API_HASH')

    # добавляем кол-во процессов и воркеров в переменные
    count_process = int(os.getenv('COUNT_PROCESS'))
    count_workers = int(os.getenv('COUNT_WORKERS'))

    # проверяем прокси и аккаунтов
    if os.getenv("CHECK"):
        work_accounts, work_proxy = main_checker(api_id, api_hash)
    else:
        print("Прокси и аккаунты не проверены, так как настройка выключена")
        raise ErrorCheckNotTrue

    # добавляем кол-во рабочих прокси и аккаунтов в переменные
    count_proxys = len(work_proxy)
    count_accounts = len(work_accounts)

    # получаем обьекты категорий в tgstat + кол-во этих категорий
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/50.0.2661.102 Safari/537.36'
    }
    response = requests.get('https://tgstat.ru/en', timeout=10, headers=headers)
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    groups_tgstat = soup.find_all('a', href=re.compile(r'^/en/[a-zA-Z0-9]+$'), class_="text-dark")
    groups_tgstat_links = {path.get("href") for path in groups_tgstat}
    count_groups_tgstat = len(groups_tgstat_links)

    # проверки выставленных настроек перед запуском
    if count_accounts < count_process * count_workers:
        raise Exception("Недостаточно аккаунтов для данного кол-ва процессов")
    if count_proxys < count_process * count_workers:
        raise Exception(f'Недостаточно прокси для всех аккаунтов. Минимум 1 прокси на 1 аккаунт')
    if not count_accounts or not count_proxys:
        raise Exception(f'Недостаточно рабочих аккаунтов или прокси. Нужно минимум 1 аккаунт и 1 прокси')
    if count_workers*count_process > count_groups_tgstat:
        raise Exception(f'Слишком много воркеров для данного кол-ва категорий. Максимум 1 воркер на 1 категорию'
                        f'Категории - {count_groups_tgstat}'
                        f'Воркеры - {count_workers}')

    start_process_parser(
        count_process,
        count_workers,
        work_proxy,
        work_accounts,
        api_id,
        api_hash,
        list(groups_tgstat_links),
        count_groups_tgstat
    )


if __name__ == '__main__':
    # создаем клиент для работы с монго и создаем бд
    client_mongo = MongoClient('127.0.0.1', 27017)
    db = client_mongo.channel_tg

    # создаем клиент для передачи картинок в хранилище s3
    s3 = boto3.client(
        's3',
        endpoint_url='https://s3.timeweb.cloud',
        region_name='ru-1',
        aws_access_key_id='SI3PXEYPDWJK5AXJ1JQK',
        aws_secret_access_key='1HUe80GXLnQ2uxXEg6ijz5D6JAAJ8RCwThr3gKsr',
        config=Config(s3={'addressing_style': 'path'})
    )

    # запускаем парсер
    run()
