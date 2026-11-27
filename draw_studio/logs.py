"""Redaction and the in-memory log cursor used by the workbench."""
import collections
import re
import threading
import time


HF_TOKEN_RE = re.compile(r"hf_[A-Za-z0-9]{10,}")
PROXY_CRED_RE = re.compile(r"((?:https?|socks5h?)://)[^/\s?#]+@", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    text = HF_TOKEN_RE.sub("hf_***", text)
    return PROXY_CRED_RE.sub(r"\1***@", text)


class LogBuffer:
    def __init__(self, keep: int = 600) -> None:
        self._lock = threading.Lock()
        self._items: collections.deque[tuple[int, str]] = collections.deque(maxlen=keep)
        self._seq = 0

    def __call__(self, msg: str) -> None:
        line = time.strftime("%H:%M:%S") + "  " + redact_secrets(str(msg))
        with self._lock:
            self._seq += 1
            self._items.append((self._seq, line))
        print(line, flush=True)

    def since(self, seq: int, limit: int = 300) -> tuple[list[str], int]:
        with self._lock:
            lines = [ln for s, ln in self._items if s > seq]
            return lines[-limit:], self._seq
