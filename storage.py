"""Хранилище связки «клиент ↔ тема (topic) в группе».

Используем SQLite, чтобы связка переживала перезапуск бота.
Логика простая: у каждого клиента одна тема в группе.
  user_id      — chat_id клиента (в личке с ботом он равен user.id)
  thread_id    — message_thread_id темы в супергруппе
"""
import sqlite3
from typing import Optional


class Storage:
    def __init__(self, path: str) -> None:
        # check_same_thread=False — aiogram работает в одном event loop,
        # но на всякий случай разрешаем доступ из разных потоков.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                user_id    INTEGER PRIMARY KEY,
                thread_id  INTEGER UNIQUE,
                username   TEXT,
                full_name  TEXT
            )
            """
        )
        self._conn.commit()

    def link(self, user_id: int, thread_id: int, username: str, full_name: str) -> None:
        self._conn.execute(
            """
            INSERT INTO clients (user_id, thread_id, username, full_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                thread_id = excluded.thread_id,
                username  = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, thread_id, username, full_name),
        )
        self._conn.commit()

    def thread_by_user(self, user_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT thread_id FROM clients WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else None

    def user_by_thread(self, thread_id: int) -> Optional[int]:
        row = self._conn.execute(
            "SELECT user_id FROM clients WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        return row[0] if row else None

    def forget_thread(self, thread_id: int) -> None:
        """Удаляем связку (например, когда тема закрыта/удалена)."""
        self._conn.execute("DELETE FROM clients WHERE thread_id = ?", (thread_id,))
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
