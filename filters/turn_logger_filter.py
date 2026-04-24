"""
title: Turn Logger Filter
author: Juan Concha
version: 0.1.0
license: MIT
description: Logs each chat turn (user message, assistant reply, tool uses, model,
             user identity, timestamp) to the chat_turn_log PostgreSQL table.
             Runs in outlet() after the assistant response is complete. Dev-only
             for now (gated by ENV=dev).
"""

import json
import os
import re
from typing import Optional

import psycopg2
from pydantic import BaseModel


# Open WebUI serializes tool invocations as <details type="tool_calls" ... name="X" ...> blocks
# inside the assistant message content. Each occurrence = one tool call.
_TOOL_CALL_DETAILS_RE = re.compile(
    r'<details\s+[^>]*?type="tool_calls"[^>]*?\bname="([^"]+)"',
    re.IGNORECASE,
)


class Filter:

    class Valves(BaseModel):
        enabled: bool = True

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        if not self.valves.enabled:
            return body
        if os.getenv("ENV", "dev") != "dev":
            return body
        try:
            self._log_turn(body, __user__ or {}, __metadata__ or {})
        except Exception as e:
            print(f"turn_logger_filter: log failed: {e}")
        return body

    def _log_turn(self, body: dict, user: dict, metadata: dict) -> None:
        messages = body.get("messages", [])
        if not messages:
            return

        last_user_idx = max(
            (i for i, m in enumerate(messages) if m.get("role") == "user"),
            default=-1,
        )
        if last_user_idx < 0:
            return

        user_message = self._content_to_text(messages[last_user_idx].get("content"))

        tool_uses: dict[str, int] = {}
        assistant_message = None

        for m in messages[last_user_idx + 1:]:
            if m.get("role") != "assistant":
                continue
            content = self._content_to_text(m.get("content"))
            assistant_message = content
            if content:
                for name in _TOOL_CALL_DETAILS_RE.findall(content):
                    tool_uses[name] = tool_uses.get(name, 0) + 1

        row = (
            metadata.get("chat_id"),
            metadata.get("message_id"),
            user.get("id"),
            user.get("name"),
            body.get("model") or metadata.get("model"),
            user_message,
            assistant_message,
            json.dumps(tool_uses),
        )

        conn = self._connect()
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_turn_log
                        (chat_id, message_id, user_id, user_name, model,
                         user_message, assistant_message, tool_uses)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (chat_id, message_id) DO NOTHING
                    """,
                    row,
                )
        finally:
            conn.close()

    @staticmethod
    def _content_to_text(content) -> Optional[str]:
        if content is None:
            return None
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts) if parts else json.dumps(content)
        return str(content)

    @staticmethod
    def _connect():
        base = {
            "dbname": "toydb",
            "user": os.getenv("POSTGRES_USER", "toyuser"),
            "password": os.getenv("POSTGRES_PASSWORD", "toypass"),
        }
        container_host = os.getenv("POSTGRES_HOST", "toy-postgres")
        try:
            return psycopg2.connect(host=container_host, port="5432", **base)
        except Exception:
            pass
        env = os.getenv("ENV", "dev")
        fallback_port = "5438" if env == "prod" else "5439"
        return psycopg2.connect(host="localhost", port=fallback_port, **base)
