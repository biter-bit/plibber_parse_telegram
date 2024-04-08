import logging
from PIL import Image
from PIL import UnidentifiedImageError
from io import BytesIO
import os
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By


def create_logger(name_logger):
    logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                        level=logging.INFO)
    logger = logging.getLogger(name_logger)
    logger.setLevel(logging.INFO)
    return logger


def get_list_channels(start_idx, finish_idx, count_workers, count_process, num_worker):
    """Возвращает список каналов для указанного номера воркера"""
    # кол-во обрабатываемых каналов всего
    all_count_groups = finish_idx - start_idx

    # кол-во каналов для каждого воркера в запущенной сессии
    channels_count_for_one = all_count_groups//(count_workers*count_process)

    # итоговый номер последней канала в списке
    result_finish_idx = channels_count_for_one * (num_worker * 1)

    # итоговый номер начального канала в списке
    result_start_idx = result_finish_idx - channels_count_for_one

    # список каналов для данного воркера
    result_list = list(range(start_idx+result_start_idx, start_idx+result_finish_idx))

    return result_list


def compress_image(path):
    try:
        img = Image.open(path)
    except UnidentifiedImageError:
        print('Bad format file')
    else:
        img = img.convert('RGB')

        # Сжимаем изображение
        img_io = BytesIO()
        img.save(img_io, format='JPEG', quality=100)
        img_io.seek(0)
        return img_io


def solve_with_2captcha(sitekey, driver):
    # start the 2CAPTCHA instance
    captcha2_api_key = os.getenv("API_KEY_CAPTCHA")
    solver = TwoCaptcha(captcha2_api_key)

    try:
        # Solve the Captcha
        result = solver.recaptcha(sitekey=sitekey, url=driver.current_url)
        code = result['code']

        # Set the solved Captcha
        elem_hidden = driver.find_element(By.ID, 'g-recaptcha-response')
        driver.execute_script("arguments[0].style.display = 'block';", elem_hidden)
        elem_hidden.send_keys(code)

        # Submit the form
        # Код JavaScript для вызова callback функции с передачей решения капчи в качестве аргумента
        js_code = f"""
        var token = '{code}';  // Получаем решение капчи
        var onloadCallback = function (token) {{
            $.ajax({{
                type: 'POST',
                url: '/en/site/captcha',
                data: {{token: token}},
                success: function (r) {{
                    location.reload();
                }}
            }});
        }};  // Получаем callback функцию

        // Вызываем callback функцию с передачей решения капчи в качестве аргумента
        onloadCallback(token);
        """

        # Выполнение JavaScript кода в Selenium
        driver.execute_script(js_code)
        return 'Ok'

    except Exception as e:
        print(e)
        return None
