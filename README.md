# Plibber parser telegram

Парсер телеграм каналов. Позволяет парсить все сообщения всех телеграм каналов, которые находятся в tgstat.
Сначала берутся имена телеграм каналов из сервиса tgstat и заносяться в бд. После происходит парсинг сообщений этих
каналов тг по именам, которые мы взяли из tgstat

## Установка и запуск (Linux)

1. Клонирование репозитория

```git clone https://github.com/biter-bit/plibber_parse_telegram.git```

2. Переход в директорию plibber_parse_telegram

```cd plibber_parse_telegram```

3. Создание виртуального окружения

```python3 -m venv venv```

4. Активация виртуального окружения

```source venv/bin/activate```

5. Установка зависимостей

```pip3 install -r requirements.txt```

6. Установка нового пути для переменной окружения PYTHONPATH

```echo 'export PYTHONPATH=$PYTHONPATH:<ПУТЬ ДО ПРОЕКТА>/plibber_parse_telegram/' >> ~/.bashrc```

7. Запуск скрипта для запуска парсера

```python channel_name_parse/runner.py```

## Зависимости

Эта программа зависит от интепретатора Python версии 3.7 или выше, PIP 23.2.1 или выше. Если вы заметили, 
что он данное ПО можно запустить на версии ниже, или он не работает на какой-либо версии, 
то напишите в [поддержку](https://github.com/OkulusDev/Oxygen#поддержка)

## Файловая система проекта

Файл channel_name_parse/runner.py. Запускает работу парсера. В нем происходят создание указанного кол-ва процессов, 
в которых будут запущено указанное кол-во пауков

Файл channel_name_parse/spiders/tgstat.py. Паук, в котором происходит основная работа парсера

Файл channel_name_parse/telegram_parsing.py. Получаем сообщения из указанного телеграм канала, сохраняем полученные 
данные в бд и в хранилище s3

Файл channel_name_parse/service.py. Доп. функции (создание логера, создание списка каналов для определенного воркера, 
сжатие картинок)

Файл channel_name_parse/exceptions.py. Тут находятся кастомные обработчики исключений

Файл channel_name_parse/extensions.py. Хранятся расширения для пауков

Файл channel_name_parse/items.py. Создает обьект данных, которые будем сохранять в бд и передает дальше в pipelines.py

Файл channel_name_parse/checkers.py. Проверяет работоспособность прокси и аккаунтов

Файл channel_name_parse/middlewares.py. Находятся классы, методы которых срабатывают до или после запроса паука. 
Создали проверку запрос селениум или обычный запрос паука

Файл channel_name_parse/pipelines.py. Происходит сохранения данных канала в бд

Файл channel_name_parse/settings.py. Находятся все настройки проекта

Папка channel_name_parse/data. В ней находятся данные прокси (все, рабочие и не рабочие)

Папка channel_name_parse/session. В ней находятся файлы аккаунтов телеграм

chromedriver и LICENSE.chromedriver. Драйвер для работы selenium

Файл .env. Тут хранятся переменные окружения, нужно создать если нет и внести все переменные, указанные в environ.txt.

Файл .gitignore. Файл git

Файл environ.txt. Заносим переменные, которые нужно вынести в файл .env

Файл requirements.txt. Хранятся зависимости проекта

Файл scrapy.cfg. Файл scrapy
