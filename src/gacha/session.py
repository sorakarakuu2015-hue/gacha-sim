import secrets
import threading

from cachetools import TTLCache

from gacha.models import SessionState
from gacha.settings import settings


class SessionStore:
    """TTLキャッシュベースのインメモリセッション管理。スレッドセーフ。"""

    def __init__(self) -> None:
        self._cache: TTLCache[str, SessionState] = TTLCache(
            maxsize=settings.session_max_size,
            ttl=settings.session_ttl,
        )
        self._lock = threading.Lock()

    def create(self, banner_id: str) -> str:
        """新しいセッションを生成してIDを返す。"""
        session_id = secrets.token_urlsafe(32)
        state = SessionState(banner_id=banner_id)
        with self._lock:
            self._cache[session_id] = state
        return session_id

    def get(self, session_id: str) -> SessionState | None:
        """セッションを取得する。存在しない場合はNoneを返す。"""
        with self._lock:
            return self._cache.get(session_id)

    def update(self, session_id: str, state: SessionState) -> None:
        """セッション状態を更新する。"""
        with self._lock:
            self._cache[session_id] = state

    def delete(self, session_id: str) -> None:
        """セッションを削除する。"""
        with self._lock:
            self._cache.pop(session_id, None)

    def create_with_state(self, state: SessionState) -> str:
        """指定されたstateでセッションを生成してIDを返す。"""
        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._cache[session_id] = state
        return session_id

    def regenerate(self, old_id: str, banner_id: str) -> str:
        """セッション固定攻撃対策: 旧IDを削除して新IDを発行する。"""
        self.delete(old_id)
        return self.create(banner_id)

    def regenerate_with_state(self, old_id: str, state: SessionState) -> str:
        """セッション固定攻撃対策: 旧IDを削除して新IDを発行し、stateを引き継ぐ。"""
        self.delete(old_id)
        return self.create_with_state(state)
