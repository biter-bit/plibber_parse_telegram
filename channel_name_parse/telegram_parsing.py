import asyncio
import os, hashlib

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import PeerChannel

from service import get_list_channels
from service import compress_image
import glob


async def download_image(message: dict, checksum_name_file: str, client, s3) -> str:
    """Скачиваем фото из сообщения и загружаем в s3 хранилище

    Parameters
    ----------
    message : dict, optional
        данные сообщения
    checksum_name_file: str, optional
        имя файла
    """

    file_name = f'{checksum_name_file}'
    photo_byte = await client.download_media(message, file_name)
    await asyncio.sleep(0.1)

    # сжимаем изображение
    img_io = compress_image(photo_byte)

    # создаем настройку для подключения s3 и загружаем фото
    bucket_name = '24825ad4-e2369fbe-f825-4ba9-9c6e-f9de1573149f'
    s3.upload_fileobj(img_io, Bucket=bucket_name, Key=photo_byte)
    for name in glob.glob(f'{file_name}.*'):
        os.remove(name)

    return file_name


async def get_channel(channel, client, db, s3) -> dict:
    """Получаем информацию об указанном канале

    Parameters
    ----------
    channel : int, optional
        идентификатор канала
    """

    try:
        # Получение информации о канале
        channel_full_info = await client(GetFullChannelRequest(channel=channel))
        await asyncio.sleep(0.1)
        post = {
            "id": channel_full_info.full_chat.id,
            "name_channel": channel_full_info.chats[0].title,
            "description_channel": channel_full_info.full_chat.about,
            "subscribers_count": channel_full_info.full_chat.participants_count,
            "avatar": channel_full_info.full_chat.chat_photo if channel_full_info.full_chat.chat_photo else None,
            "average_coverage": '',
            "messages_channel": ''
        }

        # # загружаем данные в бд
        # collection_post_channel = db['info_channels']
        # check_message = collection_post_channel.find_one({
        #     'id': post['id']
        # })
        # if not check_message:
        #     if post['avatar'] is not None:
        #         # скачиваем фото профиля
        #         try:
        #             checksum_name_file = hashlib.sha256(post['avatar'].file_reference).hexdigest()
        #             await download_image(post['avatar'], checksum_name_file, client, s3)
        #             await asyncio.sleep(0.1)
        #             post['avatar'] = post['avatar'].to_dict()
        #             post['avatar']['checksum'] = checksum_name_file
        #         except AttributeError as e:
        #             post['avatar'] = None
        #             print(f'Нет этого свойства в обьекте: {e}')
        #     collection_post_channel.insert_one(post)

        return post
    except ValueError as e:
        print("Канал не найден:", e)


async def get_messages(channel: str, client: object) -> list:
    """Получаем сообщения из указанного канала, возвращаем список

    Parameters
    ----------
    channel : int, optional
        идентификатор канала
    client: object, optional
        обьект клиента для API Telegram
    """

    try:
        result_messages = []
        last_message_id = None
        while True:
            if not last_message_id:
                messages = await client.get_messages(channel, limit=100)  # Получить последние 10 сообщений 1005684212
            else:
                messages = await client.get_messages(channel, limit=100, offset_id=last_message_id)
            await asyncio.sleep(0.1)

            if not messages:
                break

            last_message_id = messages[-1].id

            for message in messages:
                post_message = {}

                post_message['id'] = message.id
                post_message['id_channel'] = message.chat.id
                post_message['text'] = message.message
                post_message['average_coverage'] = message.views
                post_message['reactions'] = [
                        (reaction.reaction.emoticon, reaction.count) for reaction in message.reactions.results if reaction
                ] if message.reactions else None
                post_message['count_comments'] = message.replies.replies if message.replies else None
                post_message['date'] = message.date.strftime('%Y-%m-%d %H:%M:%S')

                post_message['photo'] = message.photo if message.photo else None
                post_message['video'] = message.document.to_dict() \
                    if message.document and 'video' in message.document.mime_type else None
                post_message['voice'] = message.voice.to_dict() \
                    if message.voice and 'audio' in message.voice.mime_type else None
                post_message['file'] = message.document.to_dict() \
                    if message.document and 'application' in message.document.mime_type else None
                result_messages.append(post_message)
            print(f'{len(result_messages)}')
            break
        return result_messages
    except ValueError as e:
        print("Канал не найден:", e)


async def add_data_messages(channel: str, client, db, s3):
    """Добавляем данные сообщения в базу данных MongoDB

    Parameters
    ----------
    channel : int, optional
        идентификатор канала
    """

    messages = await get_messages(channel, client)
    if messages is not None:
        for message in messages:
            # проверяем наличие сообщения в бд
            collection_messages_channel = db['messages_channels']
            check_message = collection_messages_channel.find_one({
                'id': message['id'],
                'id_channel': message['id_channel']
            })
            if not check_message:
                # скачиваем фото профиля
                if message['photo'] is not None:
                    access_hash_bytes = str(message['photo'].access_hash).encode('utf-8')
                    checksum_name_file = hashlib.sha256(access_hash_bytes).hexdigest()
                    await download_image(message['photo'], checksum_name_file, client, s3)
                    message['photo'] = message['photo'].to_dict()
                    message['photo']['checksum'] = checksum_name_file

                # добавляем сообщение в бд
                collection_messages_channel.insert_one(message)


async def main(channel_name: str, client, db, s3):
    """Создаем ивент-луп парсинга"""
    channel = await get_channel(channel_name, client, db, s3)
    messages = await get_messages(channel_name, client)

    return channel, messages
