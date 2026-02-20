"""SQLite 데이터베이스 초기화 및 연결 관리."""

from __future__ import annotations

import logging
import sqlite3

from backend.app.config import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.data_dir / "users.db"


def get_db() -> sqlite3.Connection:
    """SQLite 연결을 반환합니다."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """테이블 생성 및 기본 admin 계정 시드."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL DEFAULT '',
                hashed_password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        if row["cnt"] == 0:
            import bcrypt as _bcrypt

            hashed = _bcrypt.hashpw(
                settings.admin_password.encode(), _bcrypt.gensalt()
            ).decode()
            conn.execute(
                "INSERT INTO users (username, display_name, hashed_password, role) VALUES (?, ?, ?, ?)",
                ("admin", "관리자", hashed, "admin"),
            )
            conn.commit()
            logger.info("기본 관리자 계정 생성: admin / %s", settings.admin_password)
    finally:
        conn.close()
