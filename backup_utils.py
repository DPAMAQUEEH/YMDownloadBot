import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, TypedDict

from database import Database

BACKUP_VERSION = 1


class BackupFile(TypedDict):
    path: Path
    count: int


class BackupError(Exception):
    """Ошибка при работе с резервными копиями."""


def _serialize(table: str, rows: List[dict]) -> dict:
    return {
        "table": table,
        "version": BACKUP_VERSION,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "rows": rows,
    }


def export_backup(db: Database, output_dir: Path | None = None) -> Dict[str, BackupFile]:
    """
    Экспортирует пользователей и скачивания в JSON-файлы.

    Возвращает словарь с ключами 'users' и 'downloads' и путями к созданным файлам.
    """
    if output_dir is None:
        base_dir = Path(tempfile.mkdtemp(prefix="ym_backup_"))
    else:
        base_dir = Path(output_dir)
        base_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    users_path = base_dir / f"users_backup_{timestamp}.json"
    downloads_path = base_dir / f"downloads_backup_{timestamp}.json"

    users = db.export_users()
    downloads = db.export_downloads()

    users_payload = _serialize("users", users)
    downloads_payload = _serialize("downloads", downloads)

    users_path.write_text(json.dumps(users_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    downloads_path.write_text(json.dumps(downloads_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "users": {"path": users_path, "count": len(users)},
        "downloads": {"path": downloads_path, "count": len(downloads)},
    }


def cleanup_backup(files: Dict[str, BackupFile]) -> None:
    """Удаляет временные файлы резервной копии и их директорию."""
    if not files:
        return

    directories = {item["path"].parent for item in files.values()}
    for item in files.values():
        path = item["path"]
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    for directory in directories:
        try:
            shutil.rmtree(directory)
        except OSError:
            pass


def load_backup_file(path: Path, expected_table: str) -> List[dict]:
    """Читает JSON-файл резервной копии и проверяет, что таблица совпадает."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupError(f"Не удалось разобрать JSON-файл {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise BackupError(f"Некорректный формат файла {path}: ожидался JSON-объект.")

    table = payload.get("table")
    if table != expected_table:
        raise BackupError(f"Файл {path} предназначен для таблицы '{table}', ожидалось '{expected_table}'.")

    rows = payload.get("rows")
    if rows is None:
        raise BackupError(f"В файле {path} отсутствует ключ 'rows'.")

    if not isinstance(rows, list):
        raise BackupError(f"В файле {path} ключ 'rows' должен содержать список.")

    return rows


def restore_users(db: Database, rows: List[dict]) -> int:
    """Полностью заменяет таблицу users предоставленными строками."""
    if rows is None:
        raise BackupError("Отсутствуют данные для восстановления пользователей.")

    if not db.clear_users():
        raise BackupError("Не удалось очистить таблицу пользователей.")

    inserted = db.bulk_insert_users(rows)
    return inserted


def restore_downloads(db: Database, rows: List[dict]) -> int:
    """Полностью заменяет таблицу downloads предоставленными строками."""
    if rows is None:
        raise BackupError("Отсутствуют данные для восстановления скачиваний.")

    if not db.clear_downloads():
        raise BackupError("Не удалось очистить таблицу скачиваний.")

    inserted = db.bulk_insert_downloads(rows)
    return inserted
