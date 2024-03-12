import logging
from PIL import Image
from PIL import UnidentifiedImageError
from io import BytesIO


def create_logger(name_logger):
    logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s',
                        level=logging.INFO)
    logger = logging.getLogger(name_logger)
    logger.setLevel(logging.INFO)
    return logger


def get_list_channels(start_idx, finish_idx, count_workers, count_process, num_worker):
    """Возвращает список каналов для указанного номера врокера"""
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
