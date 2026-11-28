"""Persistent provider selection and native chat/model-list adapters for ColabReel."""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import requests

from .errors import LlmError
from .proxy import is_local_or_private_host


def base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    try:
        url = urlsplit(value)
        valid = (url.scheme in {"http", "https"} and url.hostname and url.username is None
                 and not url.query and not url.fragment and not any(c.isspace() for c in value))
        # Accessing port also validates its syntax and range.
        _ = url.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("BASE_URL 必须是完整的 HTTP(S) 地址，不能包含凭据、查询参数或片段")
    return value


def clean_models(kind: str, names: list[str]) -> list[str]:
    models = []
    for name in names:
        value = name.strip()
        if kind == "gemini":
            value = value.removeprefix("models/")
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("模型名称不能为空或含有控制字符")
        models.append(value)
    return list(dict.fromkeys(models))


@dataclass(frozen=True)
class Provider:
    id: str
    kind: str
    name: str
    base: str
    key: str = field(repr=False)
    models: list[str]
    revision: int
    legacy: bool
    enhanced_rewrite: bool

    @classmethod
    def read(cls, row: sqlite3.Row) -> Provider:
        return cls(row["id"], row["kind"], row["name"], row["base_url"], row["api_key"],
                   json.loads(row["models"]), row["revision"], bool(row["legacy"]), bool(row["enhanced_rewrite"]))


class Providers:
    def __init__(self, root: Path):
        directory = root / "private"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "llm.sqlite3"
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with self._db(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, base_url TEXT NOT NULL,
                api_key TEXT NOT NULL, models TEXT NOT NULL, fetched INTEGER,
                revision INTEGER NOT NULL DEFAULT 0, legacy INTEGER NOT NULL DEFAULT 0,
                enhanced_rewrite INTEGER NOT NULL DEFAULT 0
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS settings (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), provider_id TEXT REFERENCES providers(id)
                ON DELETE SET NULL, model TEXT
            )""")
            if "enhanced_rewrite" not in {r["name"] for r in db.execute("PRAGMA table_info(providers)")}:
                db.execute("ALTER TABLE providers ADD COLUMN enhanced_rewrite INTEGER NOT NULL DEFAULT 0")
                db.execute("UPDATE providers SET enhanced_rewrite=1 WHERE legacy=1")
            db.execute("INSERT OR IGNORE INTO settings(singleton) VALUES(1)")

    @staticmethod
    def _new_id() -> str:
        return "llm_" + uuid.uuid4().hex

    @contextmanager
    def _db(self, *, write: bool = False):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _get(db, provider_id: str) -> Provider:
        row = db.execute("SELECT * FROM providers WHERE id=?", (provider_id,)).fetchone()
        if row is None:
            raise LlmError(404, "服务商不存在")
        return Provider.read(row)

    @staticmethod
    def _state(db) -> dict:
        providers = []
        for row in db.execute("SELECT * FROM providers ORDER BY rowid"):
            key = row["api_key"]
            providers.append({
                "id": row["id"], "kind": row["kind"], "name": row["name"], "base_url": row["base_url"],
                "key_set": bool(key), "key_masked": ("…" + key[-4:] if len(key) > 6 else "••••") if key else "",
                "models": json.loads(row["models"]), "models_fetched_at": row["fetched"],
                "enhanced_rewrite": bool(row["enhanced_rewrite"]), "legacy_template": bool(row["legacy"]),
            })
        current = db.execute("SELECT provider_id, model FROM settings").fetchone()
        return {"providers": providers, "active": dict(current) if current["provider_id"] else None}

    @staticmethod
    def _repair_active(db) -> None:
        current = db.execute("SELECT provider_id, model FROM settings").fetchone()
        first = (None, None)
        for row in db.execute("SELECT id, models FROM providers WHERE api_key != '' ORDER BY rowid"):
            models = json.loads(row["models"])
            if row["id"] == current["provider_id"] and current["model"] in models:
                return
            if first[0] is None and models:
                first = (row["id"], models[0])
        db.execute("UPDATE settings SET provider_id=?, model=?", first)

    def state(self) -> dict:
        with self._db() as db:
            return self._state(db)

    def save(self, *, kind: str, name: str, base_url_value: str, api_key: str = "",
             models: list[str] | None = None, provider_id: str | None = None,
             enhanced_rewrite: bool | None = None) -> dict:
        if kind not in {"openai", "anthropic", "gemini"} or not name.strip():
            raise ValueError("请填写名称并选择支持的服务商类型")
        url = base_url(base_url_value)
        key = api_key.strip()
        if any(ord(c) < 32 or ord(c) > 126 for c in key):
            raise ValueError("API Key 含有无效字符")
        with self._db(write=True) as db:
            if provider_id is None:
                if not key:
                    raise ValueError("新服务商需要填写 API Key")
                db.execute("""INSERT INTO providers(id,kind,name,base_url,api_key,models,enhanced_rewrite)
                              VALUES(?,?,?,?,?,?,?)""", (self._new_id(), kind, name.strip(), url, key,
                                                        json.dumps(clean_models(kind, models or [])), bool(enhanced_rewrite)))
            else:
                old = self._get(db, provider_id)
                same_endpoint = (old.base, old.kind) == (url, kind)
                names = clean_models(kind, models if models is not None else old.models)
                enhanced = old.enhanced_rewrite if enhanced_rewrite is None else enhanced_rewrite
                db.execute("""UPDATE providers SET kind=?, name=?, base_url=?, api_key=?, models=?,
                              fetched=CASE WHEN ? THEN fetched ELSE NULL END,
                              revision=revision+1, legacy=?, enhanced_rewrite=? WHERE id=?""",
                           (kind, name.strip(), url, key or old.key, json.dumps(names),
                            same_endpoint and names == old.models, same_endpoint and old.legacy,
                            enhanced, old.id))
            self._repair_active(db)
            return self._state(db)

    def delete(self, provider_id: str) -> dict:
        with self._db(write=True) as db:
            self._get(db, provider_id)
            db.execute("DELETE FROM providers WHERE id=?", (provider_id,))
            self._repair_active(db)
            return self._state(db)

    @staticmethod
    def _check(p: Provider, model: str) -> str:
        if not p.key:
            raise ValueError("请先填写服务商的 API Key")
        if model not in p.models:
            raise ValueError("请选择该服务商已保存的模型")
        return model

    def active(self, provider_id: str, model: str) -> dict:
        with self._db(write=True) as db:
            self._check(self._get(db, provider_id), model)
            db.execute("UPDATE settings SET provider_id=?, model=?", (provider_id, model))
            return self._state(db)

    def resolve(self, provider_id: str | None = None, model: str | None = None) -> tuple[Provider, str]:
        with self._db() as db:
            if provider_id is None and model is None:
                provider_id, model = db.execute("SELECT provider_id, model FROM settings").fetchone()
                if not provider_id:
                    raise ValueError("还没有配置改写模型，去设置里添加")
            if not provider_id or not model:
                raise ValueError("请同时指定服务商和模型")
            p = self._get(db, provider_id)
            return p, self._check(p, model)

    def refresh(self, provider_id: str) -> dict:
        with self._db() as db:
            p = self._get(db, provider_id)
        models = list_models(p)
        with self._db(write=True) as db:
            current = self._get(db, provider_id)
            if current.revision != p.revision:
                raise LlmError(409, "拉取期间配置已变化，请重新拉取")
            db.execute("UPDATE providers SET models=?, fetched=?, revision=revision+1 WHERE id=?",
                       (json.dumps(models), int(time.time()), p.id))
            self._repair_active(db)
            return self._state(db)

    def test(self, provider_id: str, model: str | None) -> dict:
        with self._db() as db:
            p = self._get(db, provider_id)
            chosen = self._check(p, model or next(iter(p.models), ""))
        start = time.monotonic()
        error = ""
        try:
            chat(p, chosen, [{"role": "user", "content": "Reply with OK."}], max_tokens=128, timeout=20)
        except LlmError as exc:
            error = str(exc)
        return {"ok": not error, "ms": round((time.monotonic() - start) * 1000),
                "model": chosen, "error": error}


def _request(p: Provider, path: str, *, payload: dict | None = None, params: dict | None = None,
             timeout: int = 30) -> dict:
    if not p.key:
        raise ValueError("请先填写服务商的 API Key")
    headers = {"openai": {"Authorization": "Bearer " + p.key},
               "anthropic": {"x-api-key": p.key, "anthropic-version": "2023-06-01"},
               "gemini": {"x-goog-api-key": p.key}}[p.kind]
    try:
        with requests.Session() as session:
            session.trust_env = not is_local_or_private_host(urlsplit(p.base).hostname or "")
            with session.request("GET" if payload is None else "POST", p.base + path, headers=headers,
                                 json=payload, params=params, timeout=(10, timeout), allow_redirects=False,
                                 stream=True) as response:
                if not 200 <= response.status_code < 300:
                    raise LlmError(502, f"模型服务商返回 HTTP {response.status_code}，请检查地址、密钥和模型权限")
                buffer = bytearray()
                for chunk in response.iter_content(65536):
                    buffer.extend(chunk)
                    if len(buffer) > 8 * 1024 * 1024:
                        raise LlmError(502, "模型服务商响应过大")
                result = json.loads(buffer)
    except requests.RequestException as exc:
        raise LlmError(502, "连接模型服务商失败或超时") from exc
    except (ValueError, UnicodeError) as exc:
        raise LlmError(502, "模型服务商没有返回有效 JSON") from exc
    if not isinstance(result, dict):
        raise LlmError(502, "模型服务商响应格式错误")
    return result


def list_models(p: Provider) -> list[str]:
    path = {"openai": "/models", "anthropic": "/v1/models", "gemini": "/v1beta/models"}[p.kind]
    names: list[str] = []
    seen = set()
    params = {}
    while True:
        page = _request(p, path, params=params)
        try:
            if p.kind == "gemini":
                # An empty Google API list may omit the repeated field.
                if "models" not in page and set(page) - {"nextPageToken"}:
                    raise ValueError
                rows = page.get("models", [])
                if not isinstance(rows, list):
                    raise ValueError
                names.extend(row["name"] for row in rows if "generateContent" in row.get("supportedGenerationMethods", []))
                cursor = page.get("nextPageToken")
                params = {"pageToken": cursor}
            else:
                if not isinstance(page["data"], list):
                    raise ValueError
                names.extend(row["id"] for row in page["data"])
                cursor = None
                if p.kind == "anthropic" and page.get("has_more"):
                    cursor = page.get("last_id")
                    if not cursor:
                        raise ValueError
                params = {"after_id": cursor}
            if not cursor:
                return clean_models(p.kind, names)
            if not isinstance(cursor, str) or cursor in seen or len(seen) >= 100:
                raise ValueError
            seen.add(cursor)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise LlmError(502, "服务商返回的模型列表格式错误") from exc


def _parts(content: Any, kind: str) -> list[dict]:
    source = [{"type": "text", "text": content}] if isinstance(content, str) else content
    parts = []
    for part in source:
        if part["type"] == "text":
            parts.append({"type": "text", "text": part["text"]} if kind == "anthropic" else {"text": part["text"]})
        else:
            head, data = part["image_url"]["url"].split(",", 1)
            mime = head.removeprefix("data:").removesuffix(";base64")
            if kind == "anthropic":
                parts.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}})
            else:
                parts.append({"inlineData": {"mimeType": mime, "data": data}})
    return parts


def chat(p: Provider, model: str, messages: list[dict], *, max_tokens: int, timeout: int,
         temperature: float | None = None) -> str:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    turns = [m for m in messages if m["role"] != "system"]
    if p.kind == "openai":
        path = "/chat/completions"
        payload = {"model": model, "messages": messages}
        if urlsplit(p.base).hostname == "api.openai.com":
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
        if p.legacy and temperature is not None:
            payload["temperature"] = temperature
    elif p.kind == "anthropic":
        path = "/v1/messages"
        payload = {"model": model, "max_tokens": max_tokens, "messages": [
            {"role": m["role"], "content": _parts(m["content"], p.kind)} for m in turns]}
        if system:
            payload["system"] = system
    else:
        path = f"/v1beta/models/{quote(model, safe='')}:generateContent"
        payload = {"generationConfig": {"maxOutputTokens": max_tokens}, "contents": [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": _parts(m["content"], p.kind)}
            for m in turns]}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
    data = _request(p, path, payload=payload, timeout=timeout)
    try:
        if p.kind == "openai":
            msg = data["choices"][0]["message"]
            if msg.get("refusal"):
                raise LlmError(502, "模型拒绝了这次请求")
            content = msg["content"]
            if isinstance(content, list):
                content = "".join(part["text"] for part in content if part.get("type") == "text")
        elif p.kind == "anthropic":
            content = "".join(part["text"] for part in data["content"] if part["type"] == "text")
        else:
            parts = data["candidates"][0]["content"]["parts"]
            content = "".join(part["text"] for part in parts if "text" in part and not part.get("thought"))
        if not isinstance(content, str) or not content.strip():
            raise ValueError
        return content.strip()
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
        raise LlmError(502, "模型没有返回可用文本") from exc
