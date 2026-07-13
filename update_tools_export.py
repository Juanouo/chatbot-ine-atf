#!/usr/bin/env python3
"""
Update postgres-tool-export.json and filter-export.json with current source file contents.

Idempotent: files are only rewritten (and timestamps bumped) when the source
content actually changed, so running this repeatedly — e.g. on every
`make {dev,prod}-rebuild` — leaves a clean git tree if nothing changed.
"""

import json
import os
import time

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

now = int(time.time())

# --- Update postgres tool ---
with open('postgres_llm_tool.py', 'r', encoding='utf-8') as f:
    current_tool_content = f.read()

with open('exports/postgres-tool-export.json', 'r', encoding='utf-8') as f:
    tools_export = json.load(f)

tools_changed = False
for tool in tools_export:
    if tool['id'] == 'postgres_database_tool':
        if tool.get('content') != current_tool_content:
            tool['content'] = current_tool_content
            tool['updated_at'] = now
            tools_changed = True
            print(f"Updated tool: {tool['name']}")
            print(f"New timestamp: {tool['updated_at']}")
        else:
            print(f"Tool already up to date: {tool['name']}")
        break

if tools_changed:
    with open('exports/postgres-tool-export.json', 'w', encoding='utf-8') as f:
        json.dump(tools_export, f, indent=2)
    print("✅ exports/postgres-tool-export.json updated successfully!")
else:
    print("✅ exports/postgres-tool-export.json unchanged.")

# --- Update filter functions ---
filters_dir = os.path.join(script_dir, 'filters')

with open('exports/filter-export.json', 'r', encoding='utf-8') as f:
    filter_export = json.load(f)

filter_files = {
    'table_display_filter': os.path.join(filters_dir, 'table_display_filter.py'),
    'context_limit_filter': os.path.join(filters_dir, 'context_limit_filter.py'),
    'turn_logger_filter': os.path.join(filters_dir, 'turn_logger_filter.py'),
}

filters_changed = False
for func in filter_export:
    func_id = func.get('id')
    if func_id in filter_files:
        with open(filter_files[func_id], 'r', encoding='utf-8') as f:
            current_filter_content = f.read()
        if func.get('content') != current_filter_content:
            func['content'] = current_filter_content
            func['updated_at'] = now
            filters_changed = True
            print(f"Updated filter: {func['name']}")
        else:
            print(f"Filter already up to date: {func['name']}")
        del filter_files[func_id]  # mark as handled

if filters_changed:
    with open('exports/filter-export.json', 'w', encoding='utf-8') as f:
        json.dump(filter_export, f, indent=2)
    print("✅ exports/filter-export.json updated successfully!")
else:
    print("✅ exports/filter-export.json unchanged.")
