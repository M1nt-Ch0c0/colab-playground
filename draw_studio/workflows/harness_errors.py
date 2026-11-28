"""Error contract shared by the workflow agent's HTTP, tool and stream adapters."""
from __future__ import annotations

import re
from typing import Literal, get_args

from pydantic import BaseModel

HarnessErrorCode = Literal[
    "invalid_argument", "not_found", "revision_conflict", "shot_conflict", "busy",
    "running_locked", "draft_already_saved", "model_unconfigured", "model_error",
    "turn_stopped", "turn_timeout", "plugin_unavailable", "approval_required",
    "queue_full", "colab_unauthed", "media_invalid", "tool_limit_reached", "internal_error",
]

ERROR_DEFAULTS: dict[HarnessErrorCode, tuple[int, str]] = {
    "invalid_argument": (400, "参数有误"),
    "not_found": (404, "内容已不存在"),
    "revision_conflict": (409, "原内容已变"),
    "shot_conflict": (409, "镜头已被改动"),
    "busy": (409, "助手正忙"),
    "running_locked": (409, "工作流正在运行"),
    "draft_already_saved": (409, "草稿已存为运行记录"),
    "model_unconfigured": (400, "还没选对话模型"),
    "model_error": (502, "模型这次没有回应"),
    "turn_stopped": (200, "已停止"),
    "turn_timeout": (504, "响应超时"),
    "plugin_unavailable": (409, "插件暂不可用"),
    "approval_required": (409, "等你确认后再执行"),
    "queue_full": (409, "队列已满"),
    "colab_unauthed": (400, "还没连接算力"),
    "media_invalid": (400, "素材不可用"),
    "tool_limit_reached": (400, "工具已达上限"),
    "internal_error": (500, "出了点问题"),
}

HARNESS_ERROR_CODES = get_args(HarnessErrorCode)


class HarnessErrorBody(BaseModel):
    error: str
    code: HarnessErrorCode
    details: dict[str, object]


class HarnessError(Exception):
    def __init__(self, code: HarnessErrorCode, status: int | None = None,
                 message: str | None = None, details: dict | None = None):
        default_status, default_message = ERROR_DEFAULTS[code]
        self.code = code
        self.status = default_status if status is None else status
        self.message = default_message if message is None else message
        self.details = {} if details is None else details
        super().__init__(self.message)

    def body(self) -> dict:
        return {"error": self.message, "code": self.code, "details": self.details}

    def event(self) -> dict:
        return {"type": "error", "code": self.code, "message": self.message}


def is_agent_path(path: str) -> bool:
    return path.startswith("/api/workflows/agent/") or bool(re.fullmatch(
        r"/api/workflows/runs/[^/]+/(?:shots|steps/[^/]+/shots/rewrite)", path.rstrip("/"),
    ))
