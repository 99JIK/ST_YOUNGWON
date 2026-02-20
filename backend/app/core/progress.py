from __future__ import annotations

import threading
from typing import Optional

_progress: dict[str, dict] = {}
_lock = threading.Lock()


def update_progress(task_id: str, step: str, percent: int, detail: str = "") -> None:
    """작업 진행률을 업데이트합니다."""
    with _lock:
        _progress[task_id] = {
            "step": step,
            "percent": min(percent, 100),
            "detail": detail,
        }


def get_progress(task_id: str) -> Optional[dict]:
    """작업 진행률을 조회합니다."""
    with _lock:
        return _progress.get(task_id, {}).copy() if task_id in _progress else None


def clear_progress(task_id: str) -> None:
    """완료된 작업의 진행률을 제거합니다."""
    with _lock:
        _progress.pop(task_id, None)
