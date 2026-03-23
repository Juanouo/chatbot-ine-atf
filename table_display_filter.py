"""
title: Table Display Filter
author: Juan Concha
version: 0.4.0
license: MIT
description: Intercepts tool outputs containing __SHOW_TABLE__ sentinel and replaces
             the LLM response with the deterministic table content, bypassing any
             LLM-generated commentary or hallucination.
"""

from typing import Optional


class Filter:

    def __init__(self):
        # chat_id -> table markdown, populated on first stream chunk when __SHOW_TABLE__ detected in __body__
        self._pending_tables: dict[str, str] = {}

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def stream(self, event: dict, __metadata__: Optional[dict] = None, __body__: Optional[dict] = None) -> dict:
        """
        On the first chunk of a streaming response, check __body__["messages"] for a tool
        message containing __SHOW_TABLE__. If found, suppress all LLM content and emit
        the table on the final chunk instead.
        """
        chat_id = (__metadata__ or {}).get("chat_id", "default")

        # On first chunk (chat_id not yet registered), scan __body__ for tool messages
        if chat_id not in self._pending_tables and __body__:
            for message in __body__.get("messages", []):
                if message.get("role") == "tool":
                    content = message.get("content", "")
                    if isinstance(content, str) and "__SHOW_TABLE__" in content:
                        parts = content.split("__SHOW_TABLE__\n", 1)
                        table = parts[1] if len(parts) > 1 else content
                        self._pending_tables[chat_id] = table + '\n\n y así es la vida WALALALA'
                        print(f"Table Display Filter: detected __SHOW_TABLE__ in __body__ for chat {chat_id}, {len(table)} chars")
                        break

        # No pending table — pass through normally
        if chat_id not in self._pending_tables:
            return event

        choices = event.get("choices", [])
        if not choices:
            return event

        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        # Let reasoning_content chunks through unchanged
        if "content" not in delta and finish_reason is None:
            return event

        if finish_reason is not None: # Significa que es el último chunk, emitimos la tabla
            table = self._pending_tables.pop(chat_id)
            print(f"Table Display Filter: emitting table ({len(table)} chars) for chat {chat_id}")
            event["choices"][0]["delta"]["content"] = table
            return event

        # Suppress intermediate content chunks
        event["choices"][0]["delta"]["content"] = ""
        return event

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
