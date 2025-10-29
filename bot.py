import os
import logging
import asyncio

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

# Импортируем функции скачивания из yandexMusicDownloader.py
from yandexMusicDownloader import download_track, download_album, extract_track_info

# Импортируем класс для работы с базой данных
from database import Database

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Получаем токены из переменных окружения
YM_TOKEN = os.getenv("YM_TOKEN")
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Получаем ID администратора из переменных окружения (если есть)
ADMIN_ID = os.getenv("ADMIN_ID", "218957780")  # Используем указанный ID по умолчанию

# Создаем экземпляр бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализируем базу данных
# Создаем директорию data, если она не существует
data_dir = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(data_dir, exist_ok=True)

db = Database(os.path.join(data_dir, 'bot_database.db'))

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

# Функция для регистрации пользователя в базе данных
async def register_user(message: Message):
    user = message.from_user
    db.add_user(
        user_id=user.id,
        username=user.username or "",
        first_name=user.first_name or "",
        last_name=user.last_name or ""
    )
    # Если это первый запуск и указан ADMIN_ID, назначаем администратора
    if ADMIN_ID and str(user.id) == ADMIN_ID and not db.is_admin(user.id):
        db.set_admin(user.id, True)
        logging.info(f"Пользователь {user.id} назначен администратором")

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Регистрируем пользователя
    await register_user(message)
    db.update_user_activity(message.from_user.id)
    
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
    # Обновляем активность пользователя
    db.update_user_activity(message.from_user.id)
    
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return

    # Если пользователь админ, показываем список админских команд
    if db.is_admin(message.from_user.id):
        await message.answer(
            "<b>🔧 Команды администратора:</b>\n\n"
            "/help - Показать это сообщение\n"
            "/admin_stats - Показать общую статистику бота\n"
            "/users - Показать количество пользователей\n"
            "/broadcast [текст] - Отправить сообщение всем пользователям\n"
            "/add_admin [id] - Добавить нового администратора\n\n"
            "<b>📝 Обычные команды:</b>\n"
            "/start - Начать работу с ботом\n"
            "/stats - Показать вашу статистику скачиваний",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            "<b>🔍 Как пользоваться ботом:</b>\n\n"
            "1. Найдите трек на Яндекс.Музыке\n"
            "2. Скопируйте ссылку на трек\n"
            "3. Отправьте ссылку мне\n"
            "4. Дождитесь загрузки аудиофайла\n\n"
            "<b>⚠️ Примечание:</b> Некоторые треки могут быть недоступны для скачивания из-за ограничений правообладателей.",
            parse_mode=ParseMode.HTML
        )

# Добавляем команду /stats для пользователей
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    # Обновляем активность пользователя
    db.update_user_activity(message.from_user.id)
    
    if not await check_subscription(message.from_user.id, CHANNEL_USERNAME):
        await send_subscription_message(message)
        return
    
    user_id = message.from_user.id
    downloads_count = db.get_user_stats(user_id)
    
    await message.answer(
        f"📊 *Ваша статистика*\n\n"
        f"Скачано треков: {downloads_count}",
        parse_mode=ParseMode.MARKDOWN
    )

# Функция для проверки, является ли сообщение ссылкой на Яндекс.Музыку
def is_yandex_music_link(text: str) -> bool:
    return "music.yandex" in text and ("track" in text or "album" in text)

# Обработчик ссылок на Яндекс.Музыку
@dp.message(F.text.func(is_yandex_music_link))
async def process_music_link(message: Message):
    # Обновляем активность пользователя
    db.update_user_activity(message.from_user.id)
    
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
                            
                            # Записываем информацию о скачивании в базу данных
                            db.add_download(message.from_user.id, title, performer)
                            
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
                
                # Записываем информацию о скачивании в базу данных
                db.add_download(message.from_user.id, title, performer)
                
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

# Добавляем команды администратора

# Команда для получения статистики (только для админов)
@dp.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not db.is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем статистику
    stats = db.get_total_stats()
    
    await message.answer(
        f"📊 *Общая статистика бота*\n\n"
        f"👥 Всего пользователей: {stats.get('total_users', 0)}\n"
        f"🎵 Всего скачиваний: {stats.get('total_downloads', 0)}\n"
        f"👤 Активных пользователей за неделю: {stats.get('active_users_week', 0)}",
        parse_mode=ParseMode.MARKDOWN
    )

# Команда для отправки сообщения всем пользователям (только для админов)
@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not db.is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем текст сообщения (после команды /broadcast)
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "⚠️ Пожалуйста, укажите текст сообщения после команды.\n"
            "Пример: /broadcast Привет всем пользователям!"
        )
        return
    
    broadcast_text = command_parts[1]
    
    # Получаем список всех пользователей
    users = db.get_all_users()
    
    if not users:
        await message.answer("⚠️ В базе данных нет пользователей.")
        return
    
    # Отправляем сообщение о начале рассылки
    status_message = await message.answer(f"📤 Начинаю рассылку сообщения {len(users)} пользователям...")
    
    # Счетчики для статистики
    sent_count = 0
    error_count = 0
    
    # Отправляем сообщение каждому пользователю
    for user in users:
        try:
            await bot.send_message(
                chat_id=user['user_id'],
                text=f"📢 *Сообщение от администратора*\n\n{broadcast_text}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent_count += 1
            
            # Обновляем статус каждые 10 отправленных сообщений
            if sent_count % 10 == 0:
                await status_message.edit_text(
                    f"📤 Отправлено {sent_count}/{len(users)} сообщений..."
                )
            
            # Добавляем небольшую задержку, чтобы избежать блокировки за спам
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения пользователю {user['user_id']}: {e}")
            error_count += 1
    
    # Отправляем итоговую статистику
    await status_message.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📊 Статистика:\n"
        f"✓ Успешно отправлено: {sent_count}\n"
        f"❌ Ошибок: {error_count}"
    )

# Команда для добавления администратора (только для существующих админов)
@dp.message(Command("add_admin"))
async def cmd_add_admin(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not db.is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем ID нового администратора (после команды /add_admin)
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) < 2:
        await message.answer(
            "⚠️ Пожалуйста, укажите ID пользователя после команды.\n"
            "Пример: /add_admin 123456789"
        )
        return
    
    try:
        new_admin_id = int(command_parts[1])
    except ValueError:
        await message.answer("⚠️ ID пользователя должен быть числом.")
        return
    
    # Проверяем, существует ли пользователь в базе данных
    user = db.get_user(new_admin_id)
    if not user:
        await message.answer(
            "⚠️ Пользователь с указанным ID не найден в базе данных.\n"
            "Пользователь должен хотя бы раз воспользоваться ботом."
        )
        return
    
    # Назначаем пользователя администратором
    if db.set_admin(new_admin_id, True):
        username = user['username'] or f"ID: {new_admin_id}"
        await message.answer(f"✅ Пользователь {username} успешно назначен администратором.")
    else:
        await message.answer("❌ Произошла ошибка при назначении администратора.")

# Команда для подсчета пользователей (только для админов)
@dp.message(Command("users"))
async def cmd_users(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь администратором
    if not db.is_admin(user_id):
        await message.answer("⛔ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем статистику
    stats = db.get_total_stats()
    
    await message.answer(
        f"👥 *Статистика пользователей*\n\n"
        f"Всего пользователей: {stats.get('total_users', 0)}\n"
        f"Активных за неделю: {stats.get('active_users_week', 0)}",
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик для всех остальных сообщений
@dp.message()
async def echo(message: Message):
    # Регистрируем пользователя, если он новый
    await register_user(message)
    # Обновляем активность пользователя
    db.update_user_activity(message.from_user.id)
    
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
