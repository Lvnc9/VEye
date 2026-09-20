"""Where the V_1.0 index rows come from.

Two sources, decided with the user: a **mongoexport file** you produce yourself, or the
**live MongoDB** through a connection string that is read from an environment variable
*at run time* (never stored, logged or sent through the broker). V_1.0's own committed
credentials are never used — nothing in this repo contains them.

Both return a plain list of row dicts; the mapping layer takes it from there.
"""
import json
import os
from pathlib import Path

#: An index of documents is a few hundred small rows; anything near this is not one.
MAX_INDEX_FILE_BYTES = 100 * 1024 * 1024

DEFAULT_MONGO_DB = "my_database"          # V_1.0 utils.py MongoDBClient defaults
DEFAULT_MONGO_COLLECTION = "my_collection"


class SourceError(Exception):
    """A source could not be read. The message is Persian and safe to show: it never
    contains a connection string or credentials."""


def load_index_file(path) -> list:
    """A `mongoexport` file: a JSON array (`--jsonArray`) or one JSON object per line.
    Extended-JSON `_id` fields are ignored by the mapping, so they need no conversion."""
    file = Path(path)
    if not file.is_file():
        raise SourceError(f"فایل ردیف‌ها یافت نشد: {file}")
    if file.stat().st_size > MAX_INDEX_FILE_BYTES:
        raise SourceError("فایل ردیف‌ها بیش از حد بزرگ است.")
    try:
        text = file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        raise SourceError("فایل ردیف‌ها خوانده نشد (رمزگذاری UTF-8 لازم است).")

    text = text.strip()
    if not text:
        return []
    try:
        if text.startswith("["):
            data = json.loads(text)
        else:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
    except json.JSONDecodeError:
        raise SourceError("فایل ردیف‌ها JSON معتبر نیست (آرایهٔ JSON یا هر ردیف در یک خط).")
    if not isinstance(data, list):
        raise SourceError("فایل ردیف‌ها باید فهرستی از ردیف‌ها باشد.")
    return data


def load_mongo(uri_env: str, db: str = DEFAULT_MONGO_DB, collection: str = DEFAULT_MONGO_COLLECTION) -> list:
    """Read every row of the index collection from the live MongoDB.

    `uri_env` is the *name* of an environment variable holding the connection string.
    Failures are reported without the driver's message, which can echo hosts."""
    uri = os.environ.get(uri_env, "")
    if not uri:
        raise SourceError(f"متغیر محیطی «{uri_env}» تنظیم نشده است (نشانی اتصال به MongoDB).")
    try:
        from pymongo import MongoClient  # imported lazily: only this source needs it
    except ImportError:
        raise SourceError("بستهٔ pymongo نصب نیست.")

    client = None
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
        return list(client[db][collection].find({}, {"_id": 0}))
    except Exception as error:  # noqa: BLE001 — deliberately opaque, see docstring
        raise SourceError(f"اتصال به MongoDB یا خواندن از آن ناموفق بود ({type(error).__name__}).")
    finally:
        if client is not None:
            client.close()


def load_rows(options: dict) -> list:
    """Rows for an import run, from `options` (see ImportRun.options)."""
    if options.get("index_file"):
        return load_index_file(options["index_file"])
    if options.get("mongo_uri_env"):
        return load_mongo(
            options["mongo_uri_env"],
            options.get("mongo_db") or DEFAULT_MONGO_DB,
            options.get("mongo_collection") or DEFAULT_MONGO_COLLECTION,
        )
    raise SourceError("منبع داده مشخص نشده است (فایل ردیف‌ها یا MongoDB).")
