"""
title: Table Display Filter
author: Juan Concha
version: 0.4.2
license: MIT
description: Intercepts tool outputs containing __SHOW_TABLE__ sentinel and replaces
             the LLM response with the deterministic table content, bypassing any
             LLM-generated commentary or hallucination.
"""

from typing import Optional


class Filter:

    def __init__(self):
        # chat_id -> {"table": str, "done": bool}
        # "done" True means the table was already emitted on the first stream cycle.
        # OpenRouter triggers two stream cycles per turn (unlike Ollama which triggers one).
        # Keeping the entry alive (instead of popping) lets us suppress the second cycle.
        # Entries are cleaned up in outlet().
        self._pending_tables: dict[str, dict] = {}

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def stream(self, event: dict, __metadata__: Optional[dict] = None, __body__: Optional[dict] = None) -> dict:
        """
        On the first chunk of a streaming response, check __body__["messages"] for a tool
        message containing __SHOW_TABLE__. If found, suppress all LLM content and emit
        the table on the final chunk instead.

        OpenRouter calls stream() TWICE per turn (two complete cycles). The "done" flag
        prevents re-emitting the table on the second cycle.
        """
        chat_id = (__metadata__ or {}).get("chat_id", "default")

        # Register only if this chat_id is not yet tracked at all.
        # Only look at messages AFTER the last user message — those belong to the current turn.
        if chat_id not in self._pending_tables and __body__:
            messages = __body__.get("messages", [])
            last_user_idx = max(
                (i for i, m in enumerate(messages) if m.get("role") == "user"),
                default=-1,
            )
            for message in messages[last_user_idx + 1:]:
                if message.get("role") == "tool":
                    content = message.get("content", "")
                    if isinstance(content, str) and "__SHOW_TABLE__" in content:
                        parts = content.split("__SHOW_TABLE__\n", 1)
                        table = parts[1] if len(parts) > 1 else content
                        self._pending_tables[chat_id] = {
                            "table": "Estos son los resultados encontrados:\n\n" + table + "\n\n¿Quieres obtener información respecto a otro indicador?",
                            "done": False,
                        }
                        print(f"Table Display Filter: detected __SHOW_TABLE__ for chat {chat_id}, {len(table)} chars")
                        break

        entry = self._pending_tables.get(chat_id)

        # No pending table — pass through normally
        if entry is None:
            return event

        choices = event.get("choices", [])
        if not choices:
            return event

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        # Second (or later) stream cycle: table already emitted, suppress everything
        if entry["done"]:
            if "content" in delta:
                event["choices"][0]["delta"]["content"] = ""
            return event

        # Let reasoning_content chunks through unchanged (no "content" key, no finish_reason)
        if "content" not in delta and finish_reason is None:
            return event

        if finish_reason is not None:
            table = entry["table"]
            entry["done"] = True  # Mark done — keep entry so second cycle is suppressed
            print(f"Table Display Filter: emitting table ({len(table)} chars) for chat {chat_id}")
            event["choices"][0]["delta"]["content"] = table
            return event

        # Suppress intermediate content chunks
        event["choices"][0]["delta"]["content"] = ""
        return event

    def outlet(self, body: dict, __user__: Optional[dict] = None, __metadata__: Optional[dict] = None) -> dict:
        """
        Clean up per-chat state and ensure the stored assistant message matches what was
        streamed (guards against models that echo the table in their own response).
        """
        chat_id = (__metadata__ or {}).get("chat_id")
        if chat_id and chat_id in self._pending_tables:
            del self._pending_tables[chat_id]

        messages = body.get("messages", [])
        last_user_idx = max(
            (i for i, m in enumerate(messages) if m.get("role") == "user"),
            default=-1,
        )

        table_content = None
        for message in messages[last_user_idx + 1:]:
            if message.get("role") == "tool":
                content = message.get("content", "")
                if isinstance(content, str) and "__SHOW_TABLE__" in content:
                    parts = content.split("__SHOW_TABLE__\n", 1)
                    table = parts[1] if len(parts) > 1 else content
                    table_content = (
                        "Estos son los resultados encontrados:\n\n"
                        + table
                        + "\n\n¿Quieres obtener información respecto a otro indicador?"
                    )
                    break

        if table_content:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "assistant":
                    messages[i]["content"] = table_content
                    break

        return body
