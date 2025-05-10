import os
import re
from urllib.parse import urlparse
import asyncio
from yandex_music import Client

def extract_track_info(url: str) -> tuple[str, str] | None:
    """Извлечение ID трека и альбома из URL"""
    try:
        parsed = urlparse(url)
        path = parsed.path
        print(f"Анализ URL: {url}, путь: {path}")
        
        # Проверяем различные форматы URL
        # Формат 1: /album/123456/track/7890123
        if '/album/' in path and '/track/' in path:
            album_id = re.search(r'/album/(\d+)', path)
            track_id = re.search(r'/track/(\d+)', path)
            
            if album_id and track_id:
                album_id = album_id.group(1)
                track_id = track_id.group(1)
                print(f"Найден трек в альбоме: track_id={track_id}, album_id={album_id}")
                return f"{track_id}:{album_id}", "with_album"
        
        # Формат 2: /track/7890123
        elif '/track/' in path:
            track_id = re.search(r'/track/(\d+)', path)
            if track_id:
                track_id = track_id.group(1)
                print(f"Найден отдельный трек: track_id={track_id}")
                return track_id, "single_track"
        
        # Формат 3: /album/123456 - только альбом
        elif '/album/' in path and '/track/' not in path:
            album_id = re.search(r'/album/(\d+)', path)
            if album_id:
                album_id = album_id.group(1)
                print(f"Найден альбом: album_id={album_id}")
                return album_id, "album"
        
        # Если URL содержит ID трека в любом месте, пытаемся его извлечь
        track_id_match = re.search(r'track[=/](\d+)', url)
        if track_id_match:
            track_id = track_id_match.group(1)
            print(f"Найден ID трека в URL: track_id={track_id}")
            return track_id, "single_track"
            
        print(f"Неподдерживаемый формат URL: {url}")
        return None
    except Exception as e:
        print(f"Ошибка при анализе URL: {e}, URL: {url}")
        return None

async def download_track(url: str, output_path: str = None, token: str = None) -> tuple[bool, dict | None]:
    """Скачивание трека по URL"""
    try:
        # Инициализация клиента с токеном или без авторизации
        if token:
            client = Client(token)
            print("Клиент Яндекс.Музыки инициализирован с авторизацией")
        else:
            client = Client()
            print("Клиент Яндекс.Музыки инициализирован без авторизации (доступны только превью треков)")
        
        client.init()
        
        # Извлечение информации о треке из URL
        track_info = extract_track_info(url)
        if not track_info:
            print("Не удалось извлечь информацию о треке из URL")
            return False, None
        
        track_id, id_type = track_info
        print(f"Получен ID трека: {track_id}, тип: {id_type}")
        
        # Проверяем, если это альбом, вызываем функцию скачивания альбома
        if id_type == "album":
            print(f"Обнаружена ссылка на альбом. Перенаправление на скачивание альбома...")
            return await download_album(url, token=token)
        
        # Получение информации о треке
        try:
            if id_type == "with_album":
                print(f"Запрос трека с альбомом: {track_id}")
                tracks = client.tracks([track_id])
                if not tracks or len(tracks) == 0:
                    print(f"Трек не найден: {track_id}")
                    return False, None
                track = tracks[0]
            else:
                print(f"Запрос отдельного трека: {track_id}")
                track = client.tracks(track_id)
        except Exception as e:
            error_message = str(e)
            if "Unavailable For Legal Reasons" in error_message:
                print(f"Ошибка: Трек недоступен по юридическим причинам. Возможно, он недоступен в вашем регионе.")
            elif "Not found" in error_message or "404" in error_message:
                print(f"Ошибка: Трек не найден. Проверьте правильность ссылки.")
            elif "Unauthorized" in error_message or "401" in error_message:
                print(f"Ошибка авторизации. Проверьте правильность токена.")
            else:
                print(f"Ошибка при запросе трека: {e}, track_id: {track_id}")
            return False, None
        
        if not track:
            print(f"Трек не найден: {track_id}")
            return False, None
        
        print(f"Трек найден: {track.title} - {', '.join(a.name for a in track.artists)}")
        
        if not track.available:
            print(f"Трек недоступен для прослушивания: {track_id}")
            return False, None
        
        # Определение имени файла для сохранения
        if not output_path:
            artists = ", ".join(a.name for a in track.artists)
            filename = f"{artists} - {track.title}.mp3"
            # Удаление недопустимых символов из имени файла
            filename = re.sub(r'[\\/*?:"<>|]', "", filename)
            # Сохраняем файл в директории программы
            script_dir = os.path.dirname(__file__)
            output_path = os.path.join(script_dir, filename)
        
        # Скачивание трека
        print(f"Скачивание трека в файл: {output_path}...")
        try:
            track.download(output_path)
            
            # Проверка, что файл был успешно создан
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Трек успешно скачан в файл: {os.path.abspath(output_path)}")
                # Возвращаем метаданные трека вместе со статусом успеха
                track_metadata = {
                    "title": track.title,
                    "artists": ", ".join(a.name for a in track.artists),
                    "file_path": os.path.abspath(output_path)
                }
                return True, track_metadata
            else:
                print(f"Не удалось скачать трек (файл не создан или пуст)")
                if not token:
                    print("Возможно, для скачивания полной версии трека требуется авторизация.")
                return False, None
        except Exception as e:
            error_message = str(e)
            if "Unauthorized" in error_message:
                print(f"Ошибка авторизации при скачивании. Проверьте правильность токена.")
            elif "Not found" in error_message:
                print(f"Файл трека не найден на сервере.")
            elif "Access denied" in error_message:
                print(f"Доступ к треку запрещен. Возможно, трек недоступен в вашем регионе или требуется подписка.")
            else:
                print(f"Ошибка при скачивании трека: {e}")
            return False, None
    except Exception as e:
        print(f"Общая ошибка при обработке трека: {e}")
        return False, None

async def download_album(url: str, token: str = None) -> tuple[bool, dict | None]:
    """Скачивание всех треков из альбома по URL"""
    try:
        # Инициализация клиента с токеном или без авторизации
        if token:
            client = Client(token)
            print("Клиент Яндекс.Музыки инициализирован с авторизацией")
        else:
            client = Client()
            print("Клиент Яндекс.Музыки инициализирован без авторизации (доступны только превью треков)")
        
        client.init()
        
        # Извлечение информации об альбоме из URL
        album_info = extract_track_info(url)
        if not album_info or album_info[1] != "album":
            print("Не удалось извлечь информацию об альбоме из URL")
            return False, None
        
        album_id = album_info[0]
        print(f"Получен ID альбома: {album_id}")
        
        # Получение информации об альбоме
        try:
            album = client.albums_with_tracks(album_id)
            if not album:
                print(f"Альбом не найден: {album_id}")
                return False, None
        except Exception as e:
            error_message = str(e)
            if "Unavailable For Legal Reasons" in error_message:
                print(f"Ошибка: Альбом недоступен по юридическим причинам. Возможно, он недоступен в вашем регионе.")
            elif "Not found" in error_message or "404" in error_message:
                print(f"Ошибка: Альбом не найден. Проверьте правильность ссылки.")
            elif "Unauthorized" in error_message or "401" in error_message:
                print(f"Ошибка авторизации. Проверьте правильность токена.")
            else:
                print(f"Ошибка при запросе альбома: {e}, album_id: {album_id}")
            return False, None
        
        print(f"Альбом найден: {album.title} - {', '.join(a.name for a in album.artists)}")
        
        # Создаем директорию для альбома
        album_artist = ", ".join(a.name for a in album.artists)
        album_title = album.title
        album_dir_name = f"{album_artist} - {album_title}"
        # Удаление недопустимых символов из имени директории
        album_dir_name = re.sub(r'[\\/*?:"<>|]', "", album_dir_name)
        
        script_dir = os.path.dirname(__file__)
        album_dir = os.path.join(script_dir, album_dir_name)
        
        # Создаем директорию, если она не существует
        os.makedirs(album_dir, exist_ok=True)
        print(f"Создана директория для альбома: {album_dir}")
        
        # Получаем все треки из альбома
        all_tracks = []
        for volume in album.volumes:
            all_tracks.extend(volume)
        
        if not all_tracks:
            print(f"В альбоме нет доступных треков")
            return False, None
        
        print(f"Найдено {len(all_tracks)} треков в альбоме")
        
        # Скачиваем каждый трек
        successful_downloads = 0
        failed_downloads = 0
        downloaded_tracks_info = []
        
        for i, track in enumerate(all_tracks, 1):
            if not track.available:
                print(f"Трек {i}/{len(all_tracks)}: {track.title} - недоступен для прослушивания, пропускаем")
                failed_downloads += 1
                continue
            
            # Формируем имя файла с номером трека
            track_number = str(i).zfill(2)  # Добавляем ведущий ноль для чисел < 10
            artists = ", ".join(a.name for a in track.artists)
            filename = f"{track_number}. {artists} - {track.title}.mp3"
            # Удаление недопустимых символов из имени файла
            filename = re.sub(r'[\\/*?:"<>|]', "", filename)
            
            output_path = os.path.join(album_dir, filename)
            print(f"Скачивание трека {i}/{len(all_tracks)}: {track.title}...")
            
            try:
                track.download(output_path)
                
                # Проверка, что файл был успешно создан
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    print(f"Трек успешно скачан в файл: {os.path.abspath(output_path)}")
                    successful_downloads += 1
                    
                    # Добавляем информацию о скачанном треке
                    track_metadata = {
                        "title": track.title,
                        "artists": artists,
                        "file_path": os.path.abspath(output_path)
                    }
                    downloaded_tracks_info.append(track_metadata)
                else:
                    print(f"Не удалось скачать трек (файл не создан или пуст)")
                    failed_downloads += 1
            except Exception as e:
                error_message = str(e)
                if "Unauthorized" in error_message:
                    print(f"Ошибка авторизации при скачивании. Проверьте правильность токена.")
                elif "Not found" in error_message:
                    print(f"Файл трека не найден на сервере.")
                elif "Access denied" in error_message:
                    print(f"Доступ к треку запрещен. Возможно, трек недоступен в вашем регионе или требуется подписка.")
                else:
                    print(f"Ошибка при скачивании трека: {e}")
                failed_downloads += 1
        
        # Выводим итоговую информацию
        print(f"\nСкачивание альбома завершено.")
        print(f"Успешно скачано: {successful_downloads} из {len(all_tracks)} треков")
        if failed_downloads > 0:
            print(f"Не удалось скачать: {failed_downloads} треков")
        
        # Возвращаем информацию об альбоме и скачанных треках
        if successful_downloads > 0:
            album_metadata = {
                "title": album.title,
                "artists": ", ".join(a.name for a in album.artists),
                "tracks_total": len(all_tracks),
                "tracks_downloaded": successful_downloads,
                "album_dir": os.path.abspath(album_dir),
                "tracks": downloaded_tracks_info
            }
            return True, album_metadata
        else:
            print("Не удалось скачать ни одного трека из альбома")
            return False, None
    except Exception as e:
        print(f"Общая ошибка при обработке альбома: {e}")
        return False, None

def main():
    print("=== Программа для скачивания треков и альбомов с Яндекс.Музыки ===")
    
    # Загружаем переменные окружения из файла .env
    from dotenv import load_dotenv
    import os
    load_dotenv()
    
    # Получаем токен из переменных окружения
    default_token = os.getenv("YM_TOKEN")
    
    # Запрос токена (опционально, можно использовать предустановленный)
    token_input = input(f"Введите токен Яндекс.Музыки (оставьте пустым для использования сохраненного токена): ").strip()
    token = token_input if token_input else default_token
    
    print("Используется токен для авторизации в Яндекс.Музыке")
    
    # Запрос ссылки на трек или альбом
    audiolink = input("Введите ссылку на трек или альбом Яндекс.Музыки: ").strip()
    if not audiolink:
        audiolink = "https://music.yandex.ru/album/33447815/track/131527613?utm_medium=copy_link"
        print(f"Используется ссылка по умолчанию: {audiolink}")
    
    # Определяем тип ссылки (трек или альбом)
    link_info = extract_track_info(audiolink)
    if link_info and link_info[1] == "album":
        print(f"Обнаружена ссылка на альбом. Начинаем скачивание всех треков из альбома: {audiolink}")
    else:
        print(f"Начинаем скачивание трека по ссылке: {audiolink}")
    
    success, metadata = asyncio.run(download_track(audiolink, token=token))
    
    if success:
        # Проверяем, был ли скачан альбом или отдельный трек
        if metadata and "tracks_downloaded" in metadata:
            # Это альбом
            print(f"\nСкачивание альбома \"{metadata['title']}\" завершено успешно!")
            print(f"Скачано {metadata['tracks_downloaded']} из {metadata['tracks_total']} треков")
            print(f"Файлы сохранены в директорию: {metadata['album_dir']}")
        else:
            # Это отдельный трек
            print("Скачивание трека завершено успешно!")
    else:
        print("Произошла ошибка при скачивании.")
        if token == default_token:
            print("Примечание: Возможно, предустановленный токен устарел или недействителен.")
            print("Попробуйте получить новый токен: https://yandex-music.readthedocs.io/en/main/token.html")
        elif not token:
            print("Примечание: Для скачивания полных треков необходима авторизация с токеном.")
            print("Подробнее о получении токена: https://yandex-music.readthedocs.io/en/main/token.html")

if __name__ == "__main__":
    main()