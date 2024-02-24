import random
from telethon import TelegramClient
import dotenv, os, multiprocessing, re

from exceptions import ErrorCheckNotTrue
from service import create_logger
from checkers import main_checker
from telegram_parsing import main
from pymongo import MongoClient
import boto3
from botocore.client import Config


def start_worker_parser(num_process, count_workers, work_accounts, work_proxys):
    # Запускаем главную корутину (клиент)
    for num_worker in range(num_process*count_workers, num_process*count_workers+count_workers):
        proxy_data = re.split(r'[:@]', work_proxys[num_worker*num_process])
        # proxy_data = re.split(r'[:@]', random.choice(work_proxys))
        proxy = {
            'proxy_type': 'http',
            'addr': proxy_data[2],
            'port': proxy_data[3],
            'username': proxy_data[0],
            'password': proxy_data[1],
            'rdns': True
        }

        api_id = int(os.getenv('API_ID'))
        api_hash = os.getenv('API_HASH')

        with TelegramClient(work_accounts[num_worker*num_process], api_id, api_hash, proxy=proxy) as client:
            client.loop.run_until_complete(main(num_worker+1, client, db, s3))


def start_process_parser(count_process, count_workers, work_proxys, work_accounts):
    """Запускает процессы парсера"""

    processes = []

    # запуск процессов
    for num_process in range(0, count_process):
        print(f"Запуск процесса № {num_process + 1}...")
        process = multiprocessing.Process(target=start_worker_parser,
                                          args=(num_process, count_workers, work_accounts, work_proxys))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

    print("Все процессы закончили работу.")


def run():
    """Запуск парсинга"""

    # активируем переменные окружения
    dotenv.load_dotenv()

    # добавляем настройки логгера и выводим первый лог
    logger = create_logger('parse_telegram')
    logger.info("Starting telegram parsing")

    # добавляем настройки подключения (id, hash, session, proxy)
    api_id = int(os.getenv('API_ID'))
    api_hash = os.getenv('API_HASH')

    # проверяем прокси и аккаунтов
    if os.getenv("CHECK"):
        work_accounts, work_proxy = main_checker(api_id, api_hash)
    else:
        print("Прокси и аккаунты не проверены, так как настройка выключена")
        raise ErrorCheckNotTrue

    count_proxys = len(work_proxy)
    count_accounts = len(work_accounts)
    count_process = int(os.getenv('COUNT_PROCESS'))
    count_workers = int(os.getenv('COUNT_WORKERS'))
    count_channels = int(os.getenv('FINISH_NUM_CHANNEL')) - int(os.getenv('START_NUM_CHANNEL'))

    if count_accounts < count_process*count_workers:
        raise Exception("Недостаточно аккаунтов для данного кол-ва процессов")

    if count_proxys < count_process*count_workers:
        raise Exception(f'Недостаточно прокси для всех аккаунтов. Минимум 1 прокси на 1 аккаунт')

    if not count_accounts or not count_proxys:
        raise Exception(f'Недостаточно рабочих аккаунтов или прокси. Нужно минимум 1 аккаунт и 1 прокси')

    if count_workers*count_process > count_channels:
        raise Exception(f'Слишком много воркеров для данного кол-ва каналов. Максимум 1 воркер на 1 канал'
                        f'Каналы - {count_channels}'
                        f'Воркеры - {count_workers}')

    start_process_parser(count_process, count_workers, work_proxy, work_accounts)


if __name__ == '__main__':
    # создаем клиент для работы с монго
    client_mongo = MongoClient('127.0.0.1', 27017)
    db = client_mongo.telegram_db

    # создаем клиент для передачи картинок в хранилище s3
    s3 = boto3.client(
        's3',
        endpoint_url='https://s3.timeweb.cloud',
        region_name='ru-1',
        aws_access_key_id='SI3PXEYPDWJK5AXJ1JQK',
        aws_secret_access_key='1HUe80GXLnQ2uxXEg6ijz5D6JAAJ8RCwThr3gKsr',
        config=Config(s3={'addressing_style': 'path'})
    )
    run()
