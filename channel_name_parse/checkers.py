import requests
from requests import RequestException

from exceptions import ErrorNotApiHashId, ErrorCheckNotTrue
# from service import proxy_file_read, account_file_read, save_in_files, check_proxy, check_account, go
import threading, os, random, re, asyncio
from telethon.sync import TelegramClient
from typing import Union, List


class Checker:

    def __init__(self, name_file_work: str, name_file_not_work: str):
        self.works_list = []
        self.not_works_list = []
        self.name_file_work = name_file_work
        self.name_file_not_work = name_file_not_work

    def save_in_files(self) -> str:
        """Сохраняет рабочие и не рабочие данные в файлы

        Returns:
            str: статус выполнения
        """

        for file_ in (self.name_file_work, self.name_file_not_work):
            try:
                os.remove(file_)
            except FileNotFoundError:
                pass
            with open(file_, "w") as file:
                if file_ == self.name_file_work:
                    for i in self.works_list:
                        file.write(f'{i}\n')
                elif file_ == self.name_file_not_work:
                    for i in self.not_works_list:
                        file.write(f'{i}\n')
        return 'Ok'

    def convert_to_str(self, list_convert: list) -> str:
        str_convert = ','.join(list_convert)
        return str_convert


class AccountChecker(Checker):

    def __init__(self, path_to_account_sessions, name_file_work_accounts, name_file_not_work_accounts):
        super().__init__(name_file_work_accounts, name_file_not_work_accounts)
        self.list_name_sessions = []
        self.path_to_account_sessions = path_to_account_sessions

    def account_file_read(self) -> list:
        """Возвращает список имен файлов сессий телеграм.

        Возвращает:
            list: список аккаунтов
        """

        files = os.listdir(self.path_to_account_sessions)
        for account in files:
            _, file_extension = os.path.splitext(account)
            if file_extension == '.session':
                self.list_name_sessions.append(_)
        return self.list_name_sessions

    def check_account(self, proxy_full: str, account: str) -> str:
        """Проверяет работоспособость одного аккаунта.

        Формат прокси должен быть - login:password@ip:port.

        Param:
            proxy_full (str): прокси
            data_account (list): данные аккаунта
        Returns:
            str: статус выполнения
        """

        try:
            # формирование прокси
            proxy_data = re.split(r'[:@]', proxy_full)
            proxy_dict = {
                'ip': proxy_data[2],
                'port': proxy_data[3],
                'username': proxy_data[0],
                'password': proxy_data[1]
            }
            proxy = {
                'proxy_type': 'http',
                'addr': proxy_dict['ip'],
                'port': proxy_dict['port'],
                'username': proxy_dict['username'],
                'password': proxy_dict['password'],
                'rdns': True
            }

            # получение api_id и api_hash приложения
            api_id = int(os.getenv('API_ID'))
            api_hash = os.getenv('API_HASH')

            client = TelegramClient(account, api_id, api_hash, proxy=proxy)
            client.connect()
            if not client.is_user_authorized():
                self.not_works_list.append(account)
                print(f"Ошибка авторазации аккаунта {account}")
            else:
                self.works_list.append(account)
                print(f"Авторизирован аккаунт {account}")
            client.disconnect()

        except Exception as e:
            self.not_works_list.append(account)
            print(f"Error processing token {account}: {e}")
            return 'Error'

    # def go_check_account(self, proxy_full: str, account: str):
    #     asyncio.run(self.check_account(proxy_full, account))

    def main_checker_accounts(self, proxies: str) -> list:
        """Проверяет работоспособность аккаунтов телеграм

        Параметры:
            proxies (str): прокси

        Возвращает:
            list: список рабочих аккаунтов

        """
        # threads = []
        # for account in self.account_file_read():
        #     proxies_list = proxies.split(',')
        #     proxy_full = random.choice(proxies_list)
        #     thread = threading.Thread(target=self.go_check_account, args=(proxy_full, f'session/{account}'))
        #     thread.start()
        #     threads.append(thread)
        #
        # for thread in threads:
        #     thread.join()

        for account in self.account_file_read():
            proxies_list = proxies.split(',')
            proxy_full = random.choice(proxies_list)
            self.check_account(proxy_full, f'session/{account}')

        return self.works_list


class ProxyChecker(Checker):

    def __init__(self, file_name_proxy, file_name_work_proxy, file_name_not_work_proxy):
        super().__init__(file_name_work_proxy, file_name_not_work_proxy)
        self.list_proxys = []
        self.file_name_proxy = file_name_proxy

    def proxy_file_read(self) -> list:
        """Возвращает список всех прокси или строку прокси из файла.

        Возвращает:
            list: строка проксей
        """
        with open(self.file_name_proxy, 'r') as file:
            for proxy_line in file:
                self.list_proxys.append(proxy_line.strip())
        return self.list_proxys

    def check_proxy(self, proxy_full: str) -> str:
        """Проверяет работоспособость указанного прокси и доб. в категорию рабочих или нет.

        Формат прокси должен быть - login:password@ip:port.

        Param:
            proxy_full (str): прокси
            work_proxy (list): рабочие прокси
            not_work_proxy (list): нерабочие прокси
        Returns:
            str: статус выполнения
        """

        try:
            proxy_format = {
                'http': proxy_full,
                'https': proxy_full
            }
            response = requests.get(url='https://api.ipify.org/', proxies=proxy_format, timeout=5)
            response.raise_for_status()
            self.works_list.append(proxy_full[7:])
            return 'Ok'
        except RequestException:
            self.not_works_list.append(proxy_full[7:])
            return 'Error'

    def main_checker_proxy(self) -> list:
        """Проверяет работоспособность прокси

        Возвращает:
            list: список рабочих прокси

        """

        threads = []
        for proxy_line in self.proxy_file_read():
            proxy_full = f'http://{proxy_line}'
            thread = threading.Thread(target=self.check_proxy, args=(proxy_full,))
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

        return self.works_list


def main_checker(api_id, api_hash):
    if not api_id or not api_hash:
        raise ErrorNotApiHashId

    print("Проверка прокси...")
    checker_proxy = ProxyChecker(
        'data/proxies.txt',
        'data/work_proxy.txt',
        'data/not_work_proxy.txt'
    )
    work_proxy = checker_proxy.main_checker_proxy()
    os.environ['PROXIES'] = checker_proxy.convert_to_str(work_proxy)
    checker_proxy.save_in_files()

    print(f'Проверка прокси завершена. Рабочих прокси {len(work_proxy)} шт.\n')

    print('Проверка аккаунтов...')
    checker_account = AccountChecker(
        'session',
        'data/work_account.txt',
        'data/not_work_account.txt'
    )
    work_accounts = checker_account.main_checker_accounts(checker_proxy.convert_to_str(work_proxy))
    print(f'Проверка аккаунтов завершена. Рабочих аккаунтов {len(work_accounts)} шт.\n')
    return work_accounts, work_proxy
