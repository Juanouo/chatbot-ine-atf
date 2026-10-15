"""
title: Context Limit Filter
author: Juan Concha
version: 0.1.0
license: MIT
description: Limits the conversation history sent to the LLM to a configurable
             number of turns, preventing context bloat. System messages are always
             preserved. Orphan tool/assistant messages at the cut boundary are
             dropped to avoid broken tool-call sequences.
"""

from pydantic import BaseModel
from typing import Optional


class Filter:

    class Valves(BaseModel):
        max_turns: int = 5

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        messages = body.get("messages", [])
        if not messages:
            return body

        # Separate system messages (always preserved) from the rest
        system_msgs = [m for m in messages if m.get("role") == "system"]
        rest = [m for m in messages if m.get("role") != "system"]

        # A turn = 1 user msg + 1 assistant msg (possibly with tool calls in between).
        # +1 to include the current (incoming) user message.
        max_messages = self.valves.max_turns * 2 + 1
        rest = rest[-max_messages:]

        # Drop any leading messages that are not role="user" to avoid orphan
        # tool or assistant messages at the start of the truncated history.
        while rest and rest[0].get("role") != "user":
            rest.pop(0)

        body["messages"] = system_msgs + rest
        return body
