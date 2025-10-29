#!/usr/bin/env python3
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(BASE_DIR))

from aiogram import Bot  # type: ignore  # pylint: disable=import-error
from aiogram.types import FSInputFile  # type: ignore  # pylint: disable=import-error

from backup_utils import export_backup, cleanup_backup
from database import Database

TABLE_TITLES = {
    "users": "Пользователи",
    "downloads": "Скачивания",
}


async def main() -> int:
    logging.basicConfig(level=logging.INFO)

    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    bot_token = os.getenv("BOT_TOKEN")
    admin_id_raw = os.getenv("ADMIN_ID")

    if not bot_token or not admin_id_raw:
        logging.error("Не заданы переменные окружения BOT_TOKEN или ADMIN_ID.")
        return 1

    try:
        admin_id = int(admin_id_raw)
    except ValueError:
        logging.error("ADMIN_ID должен быть числом, получено: %s", admin_id_raw)
        return 1

    db_path = BASE_DIR / "data" / "bot_database.db"
    if not db_path.exists():
        logging.error("Файл базы данных не найден: %s", db_path)
        return 1

    db = Database(str(db_path))

    try:
        files = export_backup(db)
    except Exception as exc:
        logging.exception("Не удалось создать резервную копию: %s", exc)
        return 1

    async with Bot(token=bot_token) as bot:
        for table_key, meta in files.items():
            caption = (
                "📦 Еженедельный резервный бэкап\n"
                f"Таблица: {TABLE_TITLES.get(table_key, table_key)}\n"
                f"Записей: {meta['count']}"
            )
            await bot.send_document(
                chat_id=admin_id,
                document=FSInputFile(str(meta["path"])),
                caption=caption
            )

    cleanup_backup(files)
    logging.info("Резервные копии успешно отправлены админу %s.", admin_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
