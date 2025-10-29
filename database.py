import sqlite3
import logging
from datetime import datetime

class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self.connection = None
        self.init_db()
    
    def connect(self):
        try:
            self.connection = sqlite3.connect(self.db_file)
            self.connection.row_factory = sqlite3.Row
            return self.connection
        except sqlite3.Error as e:
            logging.error(f"Ошибка подключения к базе данных: {e}")
            return None
    
    def init_db(self):
        """Инициализация базы данных"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Создаем таблицу пользователей
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_admin INTEGER DEFAULT 0,
                    registered_at TIMESTAMP,
                    last_activity TIMESTAMP
                )
                """)
                
                # Создаем таблицу статистики скачиваний
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    track_title TEXT,
                    track_artist TEXT,
                    download_time TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """)
                
                conn.commit()
                logging.info("База данных инициализирована успешно")
            except sqlite3.Error as e:
                logging.error(f"Ошибка инициализации базы данных: {e}")
            finally:
                conn.close()
    
    def add_user(self, user_id, username, first_name, last_name):
        """Добавление нового пользователя или обновление информации"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                
                # Проверяем, существует ли пользователь
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
                
                current_time = datetime.now()
                
                if not user:
                    # Добавляем нового пользователя
                    cursor.execute(
                        "INSERT INTO users (user_id, username, first_name, last_name, registered_at, last_activity) VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, username, first_name, last_name, current_time, current_time)
                    )
                    logging.info(f"Добавлен новый пользователь: {user_id} ({username})")
                else:
                    # Обновляем информацию о существующем пользователе
                    cursor.execute(
                        "UPDATE users SET username = ?, first_name = ?, last_name = ?, last_activity = ? WHERE user_id = ?",
                        (username, first_name, last_name, current_time, user_id)
                    )
                    logging.info(f"Обновлена информация о пользователе: {user_id} ({username})")
                
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Ошибка при добавлении/обновлении пользователя: {e}")
                return False
            finally:
                conn.close()
        return False
    
    def update_user_activity(self, user_id):
        """Обновление времени последней активности пользователя"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                current_time = datetime.now()
                cursor.execute(
                    "UPDATE users SET last_activity = ? WHERE user_id = ?",
                    (current_time, user_id)
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Ошибка при обновлении активности пользователя: {e}")
                return False
            finally:
                conn.close()
        return False
    
    def add_download(self, user_id, track_title, track_artist):
        """Добавление записи о скачивании трека"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                current_time = datetime.now()
                cursor.execute(
                    "INSERT INTO downloads (user_id, track_title, track_artist, download_time) VALUES (?, ?, ?, ?)",
                    (user_id, track_title, track_artist, current_time)
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Ошибка при добавлении записи о скачивании: {e}")
                return False
            finally:
                conn.close()
        return False
    
    def get_all_users(self):
        """Получение списка всех пользователей"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users ORDER BY last_activity DESC")
                return cursor.fetchall()
            except sqlite3.Error as e:
                logging.error(f"Ошибка при получении списка пользователей: {e}")
                return []
            finally:
                conn.close()
        return []
    
    def get_user(self, user_id):
        """Получение информации о пользователе"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                return cursor.fetchone()
            except sqlite3.Error as e:
                logging.error(f"Ошибка при получении информации о пользователе: {e}")
                return None
            finally:
                conn.close()
        return None
    
    def is_admin(self, user_id):
        """Проверка, является ли пользователь администратором"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()
                return user and user['is_admin'] == 1
            except sqlite3.Error as e:
                logging.error(f"Ошибка при проверке статуса администратора: {e}")
                return False
            finally:
                conn.close()
        return False
    
    def set_admin(self, user_id, is_admin=True):
        """Установка или снятие статуса администратора"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                admin_value = 1 if is_admin else 0
                cursor.execute(
                    "UPDATE users SET is_admin = ? WHERE user_id = ?",
                    (admin_value, user_id)
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logging.error(f"Ошибка при изменении статуса администратора: {e}")
                return False
            finally:
                conn.close()
        return False
    
    def get_user_stats(self, user_id):
        """Получение статистики скачиваний пользователя"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) as total FROM downloads WHERE user_id = ?",
                    (user_id,)
                )
                result = cursor.fetchone()
                return result['total'] if result else 0
            except sqlite3.Error as e:
                logging.error(f"Ошибка при получении статистики пользователя: {e}")
                return 0
            finally:
                conn.close()
        return 0
    
    def get_total_stats(self):
        """Получение общей статистики"""
        conn = self.connect()
        if conn:
            try:
                cursor = conn.cursor()
                stats = {}
                
                # Общее количество пользователей
                cursor.execute("SELECT COUNT(*) as total FROM users")
                result = cursor.fetchone()
                stats['total_users'] = result['total'] if result else 0
                
                # Общее количество скачиваний
                cursor.execute("SELECT COUNT(*) as total FROM downloads")
                result = cursor.fetchone()
                stats['total_downloads'] = result['total'] if result else 0
                
                # Активные пользователи за последние 7 дней
                cursor.execute(
                    "SELECT COUNT(DISTINCT user_id) as active FROM users WHERE last_activity >= datetime('now', '-7 days')"
                )
                result = cursor.fetchone()
                stats['active_users_week'] = result['active'] if result else 0
                
                return stats
            except sqlite3.Error as e:
                logging.error(f"Ошибка при получении общей статистики: {e}")
                return {}
            finally:
                conn.close()
        return {}