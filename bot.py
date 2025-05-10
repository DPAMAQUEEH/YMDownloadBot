import os
import logging

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

# Импортируем функции скачивания из yandexMusicDownloader.py
from yandexMusicDownloader import download_track, download_album, extract_track_info

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токены из переменных окружения
YM_TOKEN = os.getenv("YM_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Создаем экземпляр бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ID или username канала для проверки подписки
CHANNEL_USERNAME = "@DPAMAQUEEH1" # Замените на username вашего канала
CHANNEL_LINK = "https://t.me/DPAMAQUEEH1" # Замените на ссылку на ваш канал

# Функция для проверки подписки на канал
async def check_subscription(user_id: int, chat_id: str):
    try:
        member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "user not found" in error_message:
            logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {chat_id}: Пользователь не найден. {e}")
        elif "chat not found" in error_message or "channel not found" in error_message:
            logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {chat_id}: Канал не найден. Проверьте CHANNEL_USERNAME. {e}")
        elif "bot is not a member" in error_message or "bot is not a participant" in error_message:
            logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {chat_id}: Бот не является участником канала. Добавьте бота в канал. {e}")
        elif "not enough rights" in error_message or "user_is_deactivated" in error_message or "USER_ID_INVALID" in error_message:
            logging.error(f"Ошибка при проверке подписки пользователя {user_id} на канал {chat_id}: Недостаточно прав у бота или проблема с пользователем. {e}")
        else:
            logging.error(f"Ошибка Telegram API при проверке подписки пользователя {user_id} на канал {chat_id}: {e}")
        # В любом случае, если произошла ошибка TelegramBadRequest, считаем, что подписка не подтверждена.
        return False
    except Exception as e:
        logging.error(f"Непредвиденная ошибка при проверке подписки: {e}")
        return False

async def send_subscription_message(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="🔄 Проверить подписку", callback_data="check_sub")]
    ])
    await message.answer(
        f"Для использования бота, пожалуйста, подпишитесь на наш канал: {CHANNEL_LINK}\n\n"
        f"После подписки нажмите кнопку 'Проверить подписку'.",
        reply_markup=keyboard
    )

# Обработчик для кнопки "Проверить подписку"
@dp.callback_query(F.data == "check_sub")
async def handle_check_subscription_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    is_subscribed = await check_subscription(user_id, CHANNEL_USERNAME)
    if is_subscribed:
        await callback_query.message.edit_text("🎉 Спасибо за подписку! Теперь вы можете пользоваться ботом.\nОтправьте мне ссылку на трек или используйте команду /start.")
        await callback_query.answer()
    else:
        await callback_query.answer("Вы все еще не подписаны. Пожалуйста, подпишитесь и попробуйте снова.", show_alert=True)


# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return
    await message.answer(
        "👋 Привет! Я бот для скачивания музыки с Яндекс.Музыки.\n\n"
        "Просто отправь мне ссылку на трек, и я пришлю тебе аудиофайл.\n\n"
        "Примеры поддерживаемых ссылок:\n"
        "• https://music.yandex.ru/album/123456/track/7890123\n"
        "• https://music.yandex.ru/track/7890123"
    )

# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return
    await message.answer(
        "🔍 *Как пользоваться ботом:*\n\n"
        "1. Найдите трек на Яндекс.Музыке\n"
        "2. Скопируйте ссылку на трек\n"
        "3. Отправьте ссылку мне\n"
        "4. Дождитесь загрузки аудиофайла\n\n"
        "⚠️ *Примечание:* Некоторые треки могут быть недоступны для скачивания из-за ограничений правообладателей.",
        parse_mode=ParseMode.MARKDOWN
    )

# Функция для проверки, является ли сообщение ссылкой на Яндекс.Музыку
def is_yandex_music_link(text: str) -> bool:
    return "music.yandex" in text and ("track" in text or "album" in text)

# Обработчик ссылок на Яндекс.Музыку
@dp.message(F.text.func(is_yandex_music_link))
async def process_music_link(message: Message):
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return
    url = message.text.strip()
    
    # Определяем тип ссылки (трек или альбом)
    link_info = extract_track_info(url)
    is_album = link_info and link_info[1] == "album"
    
    # Отправляем сообщение о начале обработки
    if is_album:
        processing_msg = await message.answer("🔍 Ищу альбом по ссылке...")
    else:
        processing_msg = await message.answer("🔍 Ищу трек по ссылке...")
    
    try:
        if is_album:
            # Скачиваем альбом
            await processing_msg.edit_text("⏳ Скачиваю альбом... Это может занять некоторое время.")
            success, album_metadata = await download_album(url, token=YM_TOKEN)
            
            if success and album_metadata:
                # Отправляем информацию об альбоме
                album_title = album_metadata.get("title", "Неизвестный альбом")
                album_artist = album_metadata.get("artists", "Неизвестный исполнитель")
                tracks_downloaded = album_metadata.get("tracks_downloaded", 0)
                tracks_total = album_metadata.get("tracks_total", 0)
                
                await processing_msg.edit_text(
                    f"✅ Альбом скачан успешно!\n\n"
                    f"🎵 {album_artist} - {album_title}\n"
                    f"📂 Скачано {tracks_downloaded} из {tracks_total} треков\n\n"
                    f"📤 Отправляю треки... Это может занять некоторое время."
                )
                
                # Отправляем все треки из альбома с задержкой между отправками
                tracks = album_metadata.get("tracks", [])
                sent_count = 0
                total_tracks = len(tracks)
                
                # Информируем пользователя о количестве треков
                await message.answer(
                    f"📂 Будет отправлено {total_tracks} треков.\n"
                    f"⏳ Это может занять некоторое время. Пожалуйста, подождите."
                )
                
                for i, track_info in enumerate(tracks):
                    try:
                        file_path = track_info.get("file_path")
                        title = track_info.get("title", "Неизвестный трек")
                        performer = track_info.get("artists", "Неизвестный исполнитель")
                        
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                            audio = FSInputFile(file_path)
                            await message.answer_audio(
                                audio=audio,
                                caption=f"🎵 {performer} - {title}\n\n🛠Сделано с помощью @YMDownload_bot",
                                title=title,
                                performer=performer
                            )
                            sent_count += 1
                            
                            # Добавляем задержку между отправками, чтобы избежать блокировки за спам
                            # Задержка только если не последний трек
                            if i < total_tracks - 1:
                                await asyncio.sleep(1.5)  # 1.5 секунды между отправками
                    except Exception as e:
                        logging.error(f"Ошибка при отправке трека {i+1}: {e}")
                        await message.answer(f"⚠️ Не удалось отправить трек {i+1}: {title}")
                
                # Сообщаем о завершении отправки
                if sent_count == total_tracks:
                    await message.answer(f"✅ Все {sent_count} треков успешно отправлены!")
                else:
                    await message.answer(
                        f"⚠️ Отправлено {sent_count} из {total_tracks} треков.\n"
                        f"Некоторые треки не удалось отправить из-за ошибок."
                    )
                
                # Удаляем сообщение о загрузке
                await processing_msg.delete()
            else:
                # Если не удалось скачать альбом
                await processing_msg.edit_text(
                    "❌ Не удалось скачать альбом. Возможные причины:\n\n"
                    "• Альбом недоступен для скачивания\n"
                    "• Ссылка некорректна\n"
                    "Попробуйте другой альбом или повторите попытку позже."
                )
        else:
            # Формируем постоянный путь для сохранения трека
            temp_path = os.path.join(os.path.dirname(__file__), 'трек.mp3')
            
            # Отправляем сообщение о скачивании
            await processing_msg.edit_text("⏳ Скачиваю трек...")
            
            # Скачиваем трек
            success, track_metadata = await download_track(url, output_path=temp_path, token=YM_TOKEN)
            
            if success and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                # Отправляем сообщение о подготовке файла
                await processing_msg.edit_text("📤 Отправляю файл...")
                
                # Получаем информацию о файле
                file_size = os.path.getsize(temp_path) / (1024 * 1024)  # размер в МБ
                
                # Отправляем аудиофайл с правильными метаданными
                audio = FSInputFile(temp_path)
                
                # Получаем название и исполнителя из метаданных
                title = track_metadata.get("title", "Неизвестный трек") if track_metadata else "Неизвестный трек"
                performer = track_metadata.get("artists", "Неизвестный исполнитель") if track_metadata else "Неизвестный исполнитель"
                
                await message.answer_audio(
                    audio=audio,
                    caption=f"🎵 {performer} - {title}\n\n🛠Сделано с помощью @YMDownload_bot",
                    title=title,
                    performer=performer
                )
                
                # Удаляем сообщение о загрузке
                await processing_msg.delete()
                
                # Удаляем временный файл после отправки
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception as e:
                        logging.error(f"Ошибка при удалении временного файла: {e}")
            else:
                # Если не удалось скачать трек
                await processing_msg.edit_text(
                    "❌ Не удалось скачать трек. Возможные причины:\n\n"
                    "• Трек недоступен для скачивания\n"
                    "• Ссылка некорректна\n"
                    "Попробуйте другой трек или повторите попытку позже."
                )
    except Exception as e:
        # В случае ошибки
        logging.error(f"Ошибка при обработке ссылки: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка при обработке запроса: {str(e)}\n\n"
            "Пожалуйста, проверьте ссылку и попробуйте снова."
        )

# Обработчик для всех остальных сообщений
@dp.message()
async def echo(message: Message):
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return
    await message.answer(
        "🤔 Я не понимаю это сообщение. Пожалуйста, отправьте мне ссылку на трек Яндекс.Музыки.\n\n"
        "Например: https://music.yandex.ru/album/123456/track/7890123\n\n"
        "Для получения справки используйте команду /help"
    )

# Функция запуска бота
async def main():
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
