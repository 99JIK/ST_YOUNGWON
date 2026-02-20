"""유저 CRUD 서비스."""

from __future__ import annotations

from typing import Optional

import bcrypt

from backend.app.database import get_db


class UserService:
    """SQLite 기반 유저 관리."""

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        """자격 증명을 확인합니다. 성공 시 유저 dict, 실패 시 None."""
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()
            if row and bcrypt.checkpw(password.encode(), row["hashed_password"].encode()):
                return dict(row)
            return None
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[dict]:
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_users(self) -> list[dict]:
        conn = get_db()
        try:
            rows = conn.execute(
                "SELECT id, username, display_name, role, is_active, created_at FROM users ORDER BY id"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def create_user(
        self, username: str, display_name: str, password: str, role: str = "user"
    ) -> dict:
        conn = get_db()
        try:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                "INSERT INTO users (username, display_name, hashed_password, role) VALUES (?, ?, ?, ?)",
                (username, display_name, hashed, role),
            )
            conn.commit()
            return self.get_user_by_username(username)
        finally:
            conn.close()

    def update_user(
        self,
        user_id: int,
        display_name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> bool:
        fields = []
        values = []
        if display_name is not None:
            fields.append("display_name = ?")
            values.append(display_name)
        if role is not None:
            fields.append("role = ?")
            values.append(role)
        if is_active is not None:
            fields.append("is_active = ?")
            values.append(1 if is_active else 0)
        if not fields:
            return False
        values.append(user_id)
        conn = get_db()
        try:
            conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def reset_password(self, user_id: int, new_password: str) -> bool:
        conn = get_db()
        try:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            conn.execute(
                "UPDATE users SET hashed_password = ? WHERE id = ?", (hashed, user_id)
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def delete_user(self, user_id: int) -> bool:
        conn = get_db()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()
