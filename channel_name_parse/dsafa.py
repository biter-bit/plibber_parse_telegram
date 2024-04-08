from telethon.sync import TelegramClient

api_id = '23507710'
api_hash = '268e7a7b8720d54b71c9f6734ec99244'

with TelegramClient('session_name', api_id, api_hash) as client:
    session = client.session.save()
    json = client.get_me().to_json()

print('Session:', session)
print('JSON:', json)
